from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from services.llm_router.providers.deepseek import DeepSeekProvider
from services.llm_router.types import LLMRequest, ModelRole
from shared.models.knowledge import KnowledgeDocument, KnowledgeSourceType, StorageBackend
from shared.models.point_wallet import PointProgram
from shared.models.route_advisor import DestRegion, RouteSweetSpot
from shared.services.point_wallet_service import PointWalletError, PointWalletNotFoundError
from shared.services.seats_aero_service import airport_code, normalize_cabin, seats_source_slug


MILEAGE_GUIDE_TAG = "mileage_guide"
MILEAGE_PARSED_TAG = "mileage_parsed"
SHA256_TAG_PREFIX = "sha256:"
ALLOWED_STATUSES = {"未確認", "已確認", "已否決"}
STATUS_TRANSITIONS = {"未確認": {"已確認", "已否決"}, "已確認": {"已否決"}, "已否決": set()}
GUIDE_PREFIX = re.compile(r"^[0-9a-f-]{36}-\d+_\d+(?:-\d+)?-", re.IGNORECASE)


class RouteAdvisorError(PointWalletError):
    pass


@dataclass(frozen=True)
class GuideImportCandidate:
    filename: str
    title: str
    sha256: str
    content: str


@dataclass(frozen=True)
class GuideImportSkip:
    filename: str
    reason: str


@dataclass(frozen=True)
class GuideImportResult:
    scanned: int
    candidates: tuple[GuideImportCandidate, ...]
    created: tuple[KnowledgeDocument, ...]
    skipped: tuple[GuideImportSkip, ...]


@dataclass(frozen=True)
class SweetSpotParseResult:
    candidates: tuple[dict[str, Any], ...]
    created: tuple[RouteSweetSpot, ...]
    warnings: tuple[str, ...]
    successful_documents: int
    failed_documents: int
    skipped_documents: int


def import_mileage_guides(
    session: Session,
    *,
    guide_dir: Path,
    commit: bool = False,
) -> GuideImportResult:
    known_hashes = _guide_hashes(session)
    candidates: list[GuideImportCandidate] = []
    skipped: list[GuideImportSkip] = []
    files = sorted((path for path in guide_dir.iterdir() if path.is_file()), key=lambda item: item.name)
    for path in files:
        if path.suffix.casefold() != ".txt":
            skipped.append(GuideImportSkip(filename=path.name, reason="副檔名不是 .txt"))
            continue
        try:
            content = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as exc:
            skipped.append(GuideImportSkip(filename=path.name, reason=f"無法讀取 UTF-8 文字：{exc}"))
            continue
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if digest in known_hashes:
            skipped.append(GuideImportSkip(filename=path.name, reason="內容雜湊已匯入"))
            continue
        candidates.append(
            GuideImportCandidate(
                filename=path.name,
                title=_guide_title(path),
                sha256=digest,
                content=content,
            )
        )
        known_hashes.add(digest)
    created: list[KnowledgeDocument] = []
    if commit:
        for candidate in candidates:
            document = KnowledgeDocument(
                title=candidate.title,
                content=candidate.content,
                source_type=KnowledgeSourceType.IMPORT,
                tags=f"{MILEAGE_GUIDE_TAG},{SHA256_TAG_PREFIX}{candidate.sha256}",
                storage_backend=StorageBackend.LOCAL,
                file_path=candidate.filename,
            )
            session.add(document)
            created.append(document)
        session.commit()
        for document in created:
            session.refresh(document)
    return GuideImportResult(
        scanned=len(files),
        candidates=tuple(candidates),
        created=tuple(created),
        skipped=tuple(skipped),
    )


def parse_mileage_guides(
    session: Session,
    *,
    commit: bool = False,
    provider: DeepSeekProvider | None = None,
    progress: Callable[[str], None] | None = None,
) -> SweetSpotParseResult:
    provider = provider or DeepSeekProvider(timeout_seconds=90)
    documents = _mileage_guide_documents(session)
    parsed_doc_ids = set(session.scalars(select(RouteSweetSpot.source_doc_id).distinct()))
    parsed_doc_ids.update(document.id for document in documents if _has_tag(document.tags, MILEAGE_PARSED_TAG))
    programs = list(session.scalars(select(PointProgram).order_by(PointProgram.name)))
    program_by_slug = {seats_source_slug(program.name): program for program in programs}
    candidates: list[dict[str, Any]] = []
    created: list[RouteSweetSpot] = []
    warnings: list[str] = []
    successful_documents = 0
    failed_documents = 0
    skipped_documents = 0
    total_documents = len(documents)
    for position, document in enumerate(documents, start=1):
        filename = document.file_path or document.title
        if document.id in parsed_doc_ids:
            skipped_documents += 1
            _report_progress(progress, f"[{position}/{total_documents}] 跳過:{filename} 原因=已成功解析")
            continue
        _report_progress(progress, f"[{position}/{total_documents}] 解析中:{filename}")
        try:
            response = provider.chat(
                LLMRequest(
                    role=ModelRole.FAST_WORKER,
                    prompt=_parse_prompt(document),
                )
            )
        except Exception as exc:
            reason = "逾時（90 秒）" if isinstance(exc, TimeoutError) else f"DeepSeek 呼叫失敗：{exc}"
            warnings.append(f"{document.title}: {reason}")
            failed_documents += 1
            _report_progress(progress, f"[{position}/{total_documents}] 失敗:{filename} 原因={reason}")
            continue
        if response.dry_run:
            reason = "缺少 DeepSeek API key"
            warnings.append(f"{document.title}: {reason}")
            failed_documents += 1
            _report_progress(progress, f"[{position}/{total_documents}] 失敗:{filename} 原因={reason}")
            continue
        try:
            payload = json.loads(response.content)
        except json.JSONDecodeError:
            reason = "回應不是有效 JSON"
            warnings.append(f"{document.title}: {reason}")
            failed_documents += 1
            _report_progress(progress, f"[{position}/{total_documents}] 失敗:{filename} 原因={reason}")
            continue
        rows = payload.get("sweet_spots") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            reason = "JSON 缺少 sweet_spots 陣列"
            warnings.append(f"{document.title}: {reason}")
            failed_documents += 1
            _report_progress(progress, f"[{position}/{total_documents}] 失敗:{filename} 原因={reason}")
            continue
        document_candidates: list[dict[str, Any]] = []
        document_created: list[RouteSweetSpot] = []
        for index, row in enumerate(rows, start=1):
            normalized = _normalize_candidate(row, document=document, program_by_slug=program_by_slug)
            if isinstance(normalized, str):
                warnings.append(f"{document.title} 第 {index} 筆：{normalized}")
                continue
            document_candidates.append(normalized)
            if commit:
                sweet_spot = RouteSweetSpot(
                    program_id=normalized["program_id"],
                    origin_tag=normalized["origin_tag"],
                    dest_tag=normalized["dest_tag"],
                    cabin=normalized["cabin"],
                    miles_cost=normalized["miles_cost"],
                    tip=normalized["tip"],
                    caveats=normalized["caveats"],
                    source_doc_id=document.id,
                    status="未確認",
                )
                session.add(sweet_spot)
                document_created.append(sweet_spot)
        if commit:
            document.tags = _append_tag(document.tags, MILEAGE_PARSED_TAG)
            try:
                session.commit()
            except Exception as exc:
                session.rollback()
                reason = f"資料庫寫入失敗：{exc}"
                warnings.append(f"{document.title}: {reason}")
                failed_documents += 1
                _report_progress(progress, f"[{position}/{total_documents}] 失敗:{filename} 原因={reason}")
                continue
            for sweet_spot in document_created:
                session.refresh(sweet_spot)
        candidates.extend(document_candidates)
        created.extend(document_created)
        successful_documents += 1
        _report_progress(
            progress,
            f"[{position}/{total_documents}] 解析中:{filename} → 候選 {len(document_candidates)} 筆",
        )
    return SweetSpotParseResult(
        candidates=tuple(candidates),
        created=tuple(created),
        warnings=tuple(warnings),
        successful_documents=successful_documents,
        failed_documents=failed_documents,
        skipped_documents=skipped_documents,
    )


def list_sweet_spots(session: Session, *, status: str | None = None) -> list[RouteSweetSpot]:
    statement = select(RouteSweetSpot).order_by(RouteSweetSpot.created_at.desc(), RouteSweetSpot.id.desc())
    if status is not None:
        if status not in ALLOWED_STATUSES:
            raise RouteAdvisorError("未知的甜點狀態")
        statement = statement.where(RouteSweetSpot.status == status)
    return list(session.scalars(statement))


def get_sweet_spot(session: Session, sweet_spot_id: int) -> RouteSweetSpot:
    row = session.get(RouteSweetSpot, sweet_spot_id)
    if row is None:
        raise PointWalletNotFoundError(f"Unknown route_sweet_spot_id: {sweet_spot_id}")
    return row


def update_pending_sweet_spot(
    session: Session,
    *,
    sweet_spot_id: int,
    program_id: int,
    origin_tag: str,
    dest_tag: str,
    cabin: str,
    miles_cost: Decimal | None,
    tip: str,
    caveats: str | None,
) -> RouteSweetSpot:
    row = get_sweet_spot(session, sweet_spot_id)
    if row.status != "未確認":
        raise RouteAdvisorError("只有未確認甜點可以編輯；已確認資料請先否決後另建新筆")
    if session.get(PointProgram, program_id) is None:
        raise PointWalletNotFoundError(f"Unknown program_id: {program_id}")
    row.program_id = program_id
    row.origin_tag = airport_code(origin_tag)
    row.dest_tag = _normalize_dest_tag(dest_tag)
    row.cabin = normalize_cabin(cabin)
    row.miles_cost = _nonnegative_miles(miles_cost)
    row.tip = _required_text(tip, "tip")
    row.caveats = _optional_text(caveats)
    session.commit()
    session.refresh(row)
    return row


def transition_sweet_spot_status(
    session: Session,
    *,
    sweet_spot_id: int,
    status: str,
) -> RouteSweetSpot:
    row = get_sweet_spot(session, sweet_spot_id)
    if status not in ALLOWED_STATUSES or status not in STATUS_TRANSITIONS[row.status]:
        raise RouteAdvisorError(f"不允許的狀態轉換：{row.status} → {status}")
    row.status = status
    session.commit()
    session.refresh(row)
    return row


def find_route_recommendations(session: Session, *, destination: str) -> list[RouteSweetSpot]:
    airport = airport_code(destination)
    region = session.get(DestRegion, airport)
    tags = [airport]
    if region is not None:
        tags.append(region.region)
    statement = (
        select(RouteSweetSpot)
        .where(
            RouteSweetSpot.status == "已確認",
            RouteSweetSpot.origin_tag == "TPE",
            or_(*(RouteSweetSpot.dest_tag == tag for tag in tags)),
        )
        .order_by(RouteSweetSpot.miles_cost.asc().nulls_last(), RouteSweetSpot.id)
    )
    return list(session.scalars(statement))


def list_dest_regions(session: Session) -> list[DestRegion]:
    return list(session.scalars(select(DestRegion).order_by(DestRegion.region, DestRegion.airport)))


def upsert_dest_region(session: Session, *, airport: str, region: str) -> DestRegion:
    airport = airport_code(airport)
    region = _required_text(region, "region")
    row = session.get(DestRegion, airport)
    if row is None:
        row = DestRegion(airport=airport, region=region)
        session.add(row)
    else:
        row.region = region
    session.commit()
    session.refresh(row)
    return row


def generate_route_advice(
    session: Session,
    *,
    destination: str,
    recommendations: list[RouteSweetSpot],
    provider: DeepSeekProvider | None = None,
) -> str | None:
    if not recommendations:
        return None
    provider = provider or DeepSeekProvider()
    document_ids = {row.source_doc_id for row in recommendations}
    documents = list(
        session.scalars(select(KnowledgeDocument).where(KnowledgeDocument.id.in_(document_ids)))
    )
    excerpts = [_document_excerpt(document, destination=destination, recommendations=recommendations) for document in documents]
    prompt = (
        "你是里程攻略整理助手。僅根據下方提供文本回答，不得補充外部知識。\n"
        "用繁體中文給出精簡建議，且每個主張以【攻略檔名】標注來源。\n\n"
        + "\n\n".join(excerpts)
    )
    try:
        response = provider.chat(LLMRequest(role=ModelRole.SUMMARIZER, prompt=prompt))
    except Exception:
        return None
    if response.dry_run or not response.content.strip():
        return None
    return response.content.strip()


def _guide_hashes(session: Session) -> set[str]:
    hashes: set[str] = set()
    for tags in session.scalars(select(KnowledgeDocument.tags).where(KnowledgeDocument.tags.is_not(None))):
        for tag in str(tags).split(","):
            if tag.startswith(SHA256_TAG_PREFIX):
                hashes.add(tag.removeprefix(SHA256_TAG_PREFIX))
    return hashes


def _has_tag(tags: str | None, expected: str) -> bool:
    return expected in {tag.strip() for tag in str(tags or "").split(",") if tag.strip()}


def _append_tag(tags: str | None, tag: str) -> str:
    values = [value.strip() for value in str(tags or "").split(",") if value.strip()]
    if tag not in values:
        values.append(tag)
    return ",".join(values)


def _report_progress(progress: Callable[[str], None] | None, message: str) -> None:
    if progress is not None:
        progress(message)


def _guide_title(path: Path) -> str:
    stripped = GUIDE_PREFIX.sub("", path.stem).strip()
    return stripped or path.stem


def _mileage_guide_documents(session: Session) -> list[KnowledgeDocument]:
    return list(
        session.scalars(
            select(KnowledgeDocument)
            .where(
                KnowledgeDocument.source_type == KnowledgeSourceType.IMPORT,
                KnowledgeDocument.tags.contains(MILEAGE_GUIDE_TAG),
            )
            .order_by(KnowledgeDocument.id)
        )
    )


def _parse_prompt(document: KnowledgeDocument) -> str:
    return (
        "Extract mileage sweet spots from this guide. Return strict JSON only with this schema:\n"
        '{"sweet_spots":[{"program":"existing program name","origin_tag":"TPE",'
        '"dest_tag":"airport or Chinese region","cabin":"economy|premium|business|first",'
        '"miles_cost":12345|null,"tip":"one concise sentence","caveats":"text or null"}]}\n'
        "Do not infer missing numbers. Use null when mileage is not explicit.\n\n"
        f"Guide title: {document.title}\nGuide content:\n{document.content}"
    )


def _normalize_candidate(
    row: Any,
    *,
    document: KnowledgeDocument,
    program_by_slug: dict[str, PointProgram],
) -> dict[str, Any] | str:
    if not isinstance(row, dict):
        return "候選不是物件"
    program_name = _optional_text(row.get("program"))
    program = program_by_slug.get(seats_source_slug(program_name or ""))
    if program is None:
        return f"找不到計畫：{program_name or '空白'}"
    try:
        origin_tag = airport_code(str(row.get("origin_tag") or "TPE"))
        dest_tag = _normalize_dest_tag(row.get("dest_tag"))
        cabin = normalize_cabin(str(row.get("cabin") or ""))
        miles_cost = _parse_miles(row.get("miles_cost"))
        tip = _required_text(row.get("tip"), "tip")
    except (PointWalletError, RouteAdvisorError) as exc:
        return str(exc)
    return {
        "program_id": program.id,
        "program_name": program.name,
        "origin_tag": origin_tag,
        "dest_tag": dest_tag,
        "cabin": cabin,
        "miles_cost": miles_cost,
        "tip": tip,
        "caveats": _optional_text(row.get("caveats")),
        "source_doc_id": document.id,
        "source_title": document.title,
        "status": "未確認",
    }


def _normalize_dest_tag(value: Any) -> str:
    text = _required_text(value, "dest_tag")
    return text.upper() if len(text) == 3 and text.isascii() and text.isalpha() else text


def _parse_miles(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        miles = Decimal(str(value))
    except InvalidOperation as exc:
        raise RouteAdvisorError("miles_cost 必須是數字或 null") from exc
    return _nonnegative_miles(miles)


def _nonnegative_miles(value: Decimal | None) -> Decimal | None:
    if value is not None and value < 0:
        raise RouteAdvisorError("miles_cost 不可小於零")
    return value


def _required_text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise RouteAdvisorError(f"{field} 不可空白")
    return text


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _document_excerpt(
    document: KnowledgeDocument,
    *,
    destination: str,
    recommendations: list[RouteSweetSpot],
) -> str:
    terms = {destination.upper()}
    terms.update(row.dest_tag for row in recommendations if row.source_doc_id == document.id)
    terms.update(row.program.name for row in recommendations if row.source_doc_id == document.id)
    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n", document.content) if paragraph.strip()]
    matched = [paragraph for paragraph in paragraphs if any(term.lower() in paragraph.lower() for term in terms)]
    selected = (matched or paragraphs)[:3]
    return f"【{document.title}】\n" + "\n".join(selected)
