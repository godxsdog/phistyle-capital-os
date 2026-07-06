from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.models.point_wallet import CostLot, LedgerTransaction, PointAccount, PointProgram, PurchaseOffer, TransferRule
from shared.services.point_wallet_service import (
    create_purchase_offer,
    create_transfer_rule,
    get_or_create_account,
    get_or_create_program,
)


OWNER_MAP = {"kai": "kent", "wife": "wife"}


@dataclass(frozen=True)
class LegacyImportResult:
    created: dict[str, int]
    warnings: list[str]


def import_legacy_point_wallet_data(
    session: Session,
    *,
    data_dir: Path,
    import_date: date | None = None,
) -> LegacyImportResult:
    import_date = import_date or date.today()
    wallet = _read_json(data_dir / "points_wallet.json")
    pingan = _read_json(data_dir / "pingan_wanlitong_rules.json")
    official = _read_json(data_dir / "official_purchase_costs.json")
    warnings: list[str] = []
    created = {
        "programs": 0,
        "accounts": 0,
        "ledger_transactions": 0,
        "cost_lots": 0,
        "transfer_rules": 0,
        "purchase_offers": 0,
    }
    _reject_credential_like_keys(wallet, "points_wallet.json")
    _reject_credential_like_keys(pingan, "pingan_wanlitong_rules.json")
    _reject_credential_like_keys(official, "official_purchase_costs.json")

    accounts = wallet.get("accounts")
    if not isinstance(accounts, dict):
        raise ValueError("points_wallet.json accounts must be an owner-keyed object")
    for legacy_owner, rows in accounts.items():
        owner = OWNER_MAP.get(legacy_owner)
        if owner is None:
            warnings.append(f"unmapped owner skipped: {legacy_owner}")
            continue
        if not isinstance(rows, list):
            warnings.append(f"owner {legacy_owner}: accounts value is not a list")
            continue
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                warnings.append(f"owner {legacy_owner} row {index}: account row is not an object")
                continue
            program_name = _string(row.get("program"))
            if not program_name:
                warnings.append(f"owner {legacy_owner} row {index}: missing program")
                continue
            program_exists = session.scalar(select(PointProgram).where(PointProgram.name == program_name)) is not None
            program = get_or_create_program(session, name=program_name, kind=_program_kind(row.get("category")))
            created["programs"] += int(not program_exists)
            account_exists = session.scalar(
                select(PointAccount).where(PointAccount.owner == owner, PointAccount.program_id == program.id)
            ) is not None
            account = get_or_create_account(
                session,
                owner=owner,
                program=program,
                account_ref=_string(row.get("id")),
                notes=_string(row.get("note")) or "legacy_import",
            )
            created["accounts"] += int(not account_exists)
            quantity = _decimal(row.get("balance"))
            cost_per_point = _decimal(row.get("costPerPoint"))
            expiry = _parse_date(_string(row.get("expiryDate")))
            stable_hash = _stable_hash({"owner": owner, "account": row})
            note = f"legacy_import hash={stable_hash}"
            if expiry is not None:
                note = f"{note} expires_at={expiry.isoformat()}"
            if quantity <= 0:
                warnings.append(f"{owner}/{program_name}: non-positive balance skipped")
                continue
            existing = session.scalar(select(LedgerTransaction).where(LedgerTransaction.note.like(f"%hash={stable_hash}%")))
            if existing is not None:
                continue
            transaction = LedgerTransaction(
                account_id=account.id,
                kind="adjustment",
                quantity=quantity,
                occurred_at=import_date,
                cost_total=(quantity * cost_per_point).quantize(Decimal("0.01")),
                cost_currency="TWD",
                note=note,
            )
            session.add(transaction)
            session.flush()
            session.add(
                CostLot(
                    account_id=account.id,
                    source_transaction_id=transaction.id,
                    quantity=quantity,
                    remaining_quantity=quantity,
                    total_cost_twd=transaction.cost_total or Decimal("0"),
                    cost_per_point_twd=cost_per_point.quantize(Decimal("0.000001")),
                    acquired_at=import_date,
                )
            )
            created["ledger_transactions"] += 1
            created["cost_lots"] += 1

    wanlitong = get_or_create_program(session, name="平安萬里通", kind="bank")
    pingan_programs = pingan.get("programs", [])
    if not isinstance(pingan_programs, list):
        raise ValueError("pingan_wanlitong_rules.json programs must be a list")
    for index, row in enumerate(pingan_programs):
        if not isinstance(row, dict):
            warnings.append(f"pingan row {index}: row is not an object")
            continue
        target_name = _string(row.get("program"))
        ratio_from = _decimal(row.get("wanlitongPerMile"))
        if not target_name or ratio_from <= 0:
            warnings.append(f"pingan row {index}: missing program or ratio")
            continue
        target = get_or_create_program(session, name=target_name, kind="airline")
        bonus_pct = ((_decimal(row.get("bonusMultiplier")) - Decimal("1")) * Decimal("100")).quantize(Decimal("0.01"))
        stable_hash = _stable_hash({"pingan": row})
        exists = session.scalar(
            select(TransferRule).where(
                TransferRule.from_program_id == wanlitong.id,
                TransferRule.to_program_id == target.id,
                TransferRule.transfer_days_note.like(f"%hash={stable_hash}%"),
            )
        )
        if exists is not None:
            continue
        create_transfer_rule(
            session,
            from_program_id=wanlitong.id,
            to_program_id=target.id,
            ratio_from=ratio_from,
            ratio_to=Decimal("1"),
            bonus_pct=bonus_pct,
            min_transfer=None,
            transfer_days_note=f"legacy_import hash={stable_hash}; {_string(row.get('formula'))}",
            valid_from=import_date,
        )
        created["transfer_rules"] += 1

    official_programs = official.get("programs", [])
    if not isinstance(official_programs, list):
        raise ValueError("official_purchase_costs.json programs must be a list")
    for index, row in enumerate(official_programs):
        if not isinstance(row, dict):
            warnings.append(f"official row {index}: row is not an object")
            continue
        program_name = _string(row.get("program"))
        cost_per_mile = _decimal(row.get("costPerMile"))
        if not program_name or cost_per_mile <= 0:
            warnings.append(f"official row {index}: missing program or costPerMile")
            continue
        program = get_or_create_program(session, name=program_name, kind="airline")
        stable_hash = _stable_hash({"official": row})
        exists = session.scalar(
            select(PurchaseOffer).where(
                PurchaseOffer.program_id == program.id,
                PurchaseOffer.source_note.like(f"%hash={stable_hash}%"),
            )
        )
        if exists is not None:
            continue
        create_purchase_offer(
            session,
            program_id=program.id,
            kind="official",
            base_price=cost_per_mile,
            currency="TWD",
            bonus_pct=_decimal(row.get("bonusPercent")),
            start_date=import_date,
            end_date=_parse_date(_string(row.get("endsAt"))),
            source_note=f"legacy_import hash={stable_hash}; vendor={_string(row.get('vendor'))}; {_string(row.get('note'))}",
        )
        created["purchase_offers"] += 1
    session.commit()
    return LegacyImportResult(created=created, warnings=warnings)


def _read_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(str(path))
    return json.loads(path.read_text(encoding="utf-8"))


def _reject_credential_like_keys(payload: Any, filename: str) -> None:
    blocked = ("password", "secret", "token", "credential", "login")
    stack = [payload]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            for key, value in item.items():
                if any(part in str(key).lower() for part in blocked):
                    raise ValueError(f"credential-like field found in {filename}: {key}")
                stack.append(value)
        elif isinstance(item, list):
            stack.extend(item)


def _stable_hash(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _string(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _decimal(value: Any) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    return Decimal(str(value))


def _parse_date(value: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _program_kind(value: Any) -> str:
    raw = _string(value).lower()
    if "air" in raw or "航空" in raw:
        return "airline"
    if "hotel" in raw or "飯店" in raw:
        return "hotel"
    if "bank" in raw or "credit" in raw or "銀行" in raw:
        return "bank"
    return "other"
