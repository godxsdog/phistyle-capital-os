import json
import importlib
from datetime import UTC, datetime
from decimal import Decimal

import pytest


pytest.importorskip("sqlalchemy")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from services.llm_router.types import LLMResponse
from shared.database.base import Base
from shared.models import knowledge, point_wallet, route_advisor  # noqa: F401
from shared.models.route_advisor import DestRegion, RouteSweetSpot
from shared.services.point_wallet_service import create_program
from shared.services.route_advisor_service import (
    RouteAdvisorError,
    find_route_recommendations,
    generate_route_advice,
    import_mileage_guides,
    parse_mileage_guides,
    transition_sweet_spot_status,
    update_pending_sweet_spot,
)


class StubProvider:
    def __init__(self, content: str):
        self.content = content
        self.calls = 0
        self.requests = []

    def chat(self, request):
        self.calls += 1
        self.requests.append(request)
        return LLMResponse(
            provider_id="deepseek",
            model="mock",
            content=self.content,
            dry_run=False,
            metadata={},
        )


def test_guide_import_is_idempotent_by_content_hash(tmp_path):
    session = make_session()
    guide_dir = tmp_path / "guides"
    guide_dir.mkdir()
    (guide_dir / "00000000-0000-0000-0000-000000000000-123_1-合成攻略.txt").write_text(
        "這是測試用合成攻略。", encoding="utf-8"
    )

    preview = import_mileage_guides(session, guide_dir=guide_dir)
    first = import_mileage_guides(session, guide_dir=guide_dir, commit=True)
    second = import_mileage_guides(session, guide_dir=guide_dir, commit=True)

    assert preview.candidates[0].title == "合成攻略"
    assert len(first.created) == 1
    assert first.created[0].source_type.value == "import"
    assert "mileage_guide,sha256:" in first.created[0].tags
    assert first.created[0].file_path.endswith("合成攻略.txt")
    assert len(second.created) == 0
    assert second.skipped == 1


def test_parse_uses_mock_llm_creates_only_unconfirmed_and_handles_invalid_json(tmp_path):
    session = make_session()
    program = create_program(session, name="ANA", kind="airline")
    document = import_document(session, tmp_path)
    provider = StubProvider(
        json.dumps(
            {
                "sweet_spots": [
                    {
                        "program": "ANA",
                        "origin_tag": "TPE",
                        "dest_tag": "日本",
                        "cabin": "business",
                        "miles_cost": 45000,
                        "tip": "合成甜點。",
                        "caveats": None,
                    }
                ]
            }
        )
    )

    preview = parse_mileage_guides(session, provider=provider)
    committed = parse_mileage_guides(session, provider=provider, commit=True)
    rerun = parse_mileage_guides(session, provider=provider, commit=True)

    assert preview.candidates[0]["program_id"] == program.id
    assert len(committed.created) == 1
    assert committed.created[0].status == "未確認"
    assert committed.created[0].source_doc_id == document.id
    assert rerun.skipped_documents == 1
    assert len(rerun.created) == 0

    other_document = knowledge.KnowledgeDocument(
        title="格式錯誤合成攻略",
        content="synthetic",
        source_type=knowledge.KnowledgeSourceType.IMPORT,
        tags="mileage_guide,sha256:invalid-json",
        storage_backend=knowledge.StorageBackend.LOCAL,
        file_path="synthetic-invalid.txt",
    )
    session.add(other_document)
    session.commit()
    invalid = parse_mileage_guides(session, provider=StubProvider("not json"), commit=True)
    assert any("不是有效 JSON" in warning for warning in invalid.warnings)
    assert len(invalid.created) == 0


def test_matching_direct_region_and_unconfirmed_exclusion():
    session = make_session()
    ana = create_program(session, name="ANA", kind="airline")
    document = synthetic_document(session)
    session.add(DestRegion(airport="NRT", region="日本"))
    direct = add_spot(session, ana.id, document.id, "NRT", "30000", "已確認")
    regional = add_spot(session, ana.id, document.id, "日本", "45000", "已確認")
    add_spot(session, ana.id, document.id, "NRT", "10000", "未確認")
    session.commit()

    matches = find_route_recommendations(session, destination="nrt")

    assert [row.id for row in matches] == [direct.id, regional.id]
    assert [row.miles_cost for row in matches] == [Decimal("30000"), Decimal("45000")]


def test_status_machine_and_edit_guard_are_enforced():
    session = make_session()
    ana = create_program(session, name="ANA", kind="airline")
    document = synthetic_document(session)
    row = add_spot(session, ana.id, document.id, "日本", "45000", "未確認")
    session.commit()

    edited = update_pending_sweet_spot(
        session,
        sweet_spot_id=row.id,
        program_id=ana.id,
        origin_tag="TPE",
        dest_tag="NRT",
        cabin="business",
        miles_cost=Decimal("40000"),
        tip="人工確認前修正。",
        caveats=None,
    )
    assert edited.miles_cost == Decimal("40000")
    transition_sweet_spot_status(session, sweet_spot_id=row.id, status="已確認")
    with pytest.raises(RouteAdvisorError, match="只有未確認甜點可以編輯"):
        update_pending_sweet_spot(
            session,
            sweet_spot_id=row.id,
            program_id=ana.id,
            origin_tag="TPE",
            dest_tag="NRT",
            cabin="business",
            miles_cost=Decimal("39000"),
            tip="不可修改",
            caveats=None,
        )
    transition_sweet_spot_status(session, sweet_spot_id=row.id, status="已否決")
    with pytest.raises(RouteAdvisorError, match="不允許的狀態轉換"):
        transition_sweet_spot_status(session, sweet_spot_id=row.id, status="已確認")


def test_ai_advice_is_grounded_in_document_and_fails_silently():
    session = make_session()
    ana = create_program(session, name="ANA", kind="airline")
    document = synthetic_document(session)
    row = add_spot(session, ana.id, document.id, "日本", "45000", "已確認")
    session.commit()
    provider = StubProvider("【合成攻略】僅引用測試內容。")

    advice = generate_route_advice(session, destination="NRT", recommendations=[row], provider=provider)

    assert advice == "【合成攻略】僅引用測試內容。"
    assert "不得補充外部知識" in provider.requests[0].prompt
    assert "【合成攻略】" in provider.requests[0].prompt

    class FailingProvider:
        def chat(self, request):
            raise RuntimeError("synthetic provider failure")

    assert generate_route_advice(session, destination="NRT", recommendations=[row], provider=FailingProvider()) is None


def test_migration_seed_contains_all_binding_airports_once():
    migration = importlib.import_module("migrations.versions.0020_pw8_route_advisor")
    airports = [row["airport"] for row in migration.DEST_REGION_ROWS]

    assert len(airports) == 54
    assert len(set(airports)) == 54
    assert {"NRT", "HKG", "SIN", "MLE", "LHR", "LAX", "SYD", "DXB"}.issubset(airports)


def import_document(session, tmp_path):
    guide_dir = tmp_path / "guides"
    guide_dir.mkdir()
    (guide_dir / "00000000-0000-0000-0000-000000000000-123_1-合成攻略.txt").write_text(
        "synthetic", encoding="utf-8"
    )
    return import_mileage_guides(session, guide_dir=guide_dir, commit=True).created[0]


def synthetic_document(session):
    document = knowledge.KnowledgeDocument(
        title="合成攻略",
        content="synthetic",
        source_type=knowledge.KnowledgeSourceType.IMPORT,
        tags="mileage_guide,sha256:synthetic",
        storage_backend=knowledge.StorageBackend.LOCAL,
        file_path="synthetic.txt",
    )
    session.add(document)
    session.commit()
    return document


def add_spot(session, program_id, document_id, dest_tag, miles, status):
    row = RouteSweetSpot(
        program_id=program_id,
        origin_tag="TPE",
        dest_tag=dest_tag,
        cabin="business",
        miles_cost=Decimal(miles),
        tip="合成甜點",
        source_doc_id=document_id,
        status=status,
        created_at=datetime.now(UTC),
    )
    session.add(row)
    session.flush()
    return row


def make_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()
