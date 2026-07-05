from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from shared.models.trade_history import CashTransaction, ImportBatch, RealizedTrade, TradeFill


class TradeImportError(Exception):
    pass


class UnsupportedTradeImportSourceError(TradeImportError):
    pass


@dataclass(frozen=True)
class TradeImportResult:
    batch: ImportBatch
    created: bool
    warnings: list[str]


@dataclass(frozen=True)
class ParsedFill:
    executed_at_raw: str
    executed_at: datetime | None
    symbol: str
    side: str
    quantity: Decimal
    position_effect: str
    instrument_type: str | None
    price: Decimal
    net_price: Decimal | None
    order_type: str | None
    file_order: int


@dataclass(frozen=True)
class ParsedCashTransaction:
    txn_date: date
    txn_time: str | None
    ref_no: str | None
    description: str
    misc_fees: Decimal | None
    commissions_fees: Decimal | None
    amount: Decimal | None


@dataclass
class OpenLot:
    quantity: Decimal
    price: Decimal
    opened_at: datetime | None


SUPPORTED_SECTIONS = {
    "現金餘額",
    "期貨概覽",
    "外匯概覽",
    "加密貨幣…賬戶概覽",
    "賬戶訂單歷史",
    "賬戶交易歷史",
    "股票",
    "盈虧",
}
LEVERAGED_SYMBOLS = {"TSLL", "TSMX", "NVDX", "TQQQ", "SQQQ"}
LEVERAGED_DESCRIPTION_PATTERN = re.compile(r"(2X|3X|BULL|BEAR|ULTRAPRO)", re.IGNORECASE)


def import_trade_history(
    session: Session,
    *,
    source: str,
    file_bytes: bytes,
) -> TradeImportResult:
    if source != "schwab":
        raise UnsupportedTradeImportSourceError("Only source=schwab is supported in Phase 16")
    content_hash = hashlib.sha256(file_bytes).hexdigest()
    existing = get_import_batch_by_hash(session, content_hash)
    if existing is not None:
        return TradeImportResult(batch=existing, created=False, warnings=_decode_warnings(existing.warnings))

    parsed = parse_schwab_statement(file_bytes)
    batch = ImportBatch(
        source=source,
        content_hash=content_hash,
        fill_count=len(parsed["fills"]),
        cash_row_count=len(parsed["cash_transactions"]),
        warning_count=len(parsed["warnings"]),
        warnings=json.dumps(parsed["warnings"], ensure_ascii=False),
    )
    try:
        session.add(batch)
        session.flush()
        for fill in parsed["fills"]:
            session.add(
                TradeFill(
                    import_batch_id=batch.id,
                    executed_at_raw=fill.executed_at_raw,
                    executed_at=fill.executed_at,
                    symbol=fill.symbol,
                    side=fill.side,
                    quantity=fill.quantity,
                    position_effect=fill.position_effect,
                    instrument_type=fill.instrument_type,
                    price=fill.price,
                    net_price=fill.net_price,
                    order_type=fill.order_type,
                    currency="USD",
                )
            )
        for cash in parsed["cash_transactions"]:
            session.add(
                CashTransaction(
                    import_batch_id=batch.id,
                    txn_date=cash.txn_date,
                    txn_time=cash.txn_time,
                    ref_no=cash.ref_no,
                    description=cash.description,
                    misc_fees=cash.misc_fees,
                    commissions_fees=cash.commissions_fees,
                    amount=cash.amount,
                    currency="USD",
                )
            )
        session.flush()
        rebuild_realized_trades(session, batch.id, warnings=parsed["warnings"])
        session.refresh(batch)
        return TradeImportResult(batch=batch, created=True, warnings=_decode_warnings(batch.warnings))
    except IntegrityError as exc:
        session.rollback()
        existing = get_import_batch_by_hash(session, content_hash)
        if existing is not None:
            return TradeImportResult(batch=existing, created=False, warnings=_decode_warnings(existing.warnings))
        raise TradeImportError("Trade import failed") from exc
    except Exception:
        session.rollback()
        raise


def parse_schwab_statement(file_bytes: bytes) -> dict[str, Any]:
    text = file_bytes.decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        raise TradeImportError("Uploaded CSV is empty")

    current_section: str | None = None
    headers_by_section: dict[str, list[str]] = {}
    fills: list[ParsedFill] = []
    cash_transactions: list[ParsedCashTransaction] = []
    warnings: list[str] = []

    for index, raw_row in enumerate(rows):
        row = [_clean_cell(cell) for cell in raw_row]
        if not any(row):
            continue
        first = row[0]
        if _is_section_header(first):
            current_section = first
            headers_by_section.pop(current_section, None)
            continue
        if current_section == "賬戶交易歷史":
            if current_section not in headers_by_section:
                headers_by_section[current_section] = row
                continue
            fill = _parse_fill(row, headers_by_section[current_section], index, warnings)
            if fill is not None:
                fills.append(fill)
        elif current_section == "現金餘額":
            if current_section not in headers_by_section:
                headers_by_section[current_section] = row
                continue
            cash = _parse_cash_transaction(row, headers_by_section[current_section], index, warnings)
            if cash is not None:
                cash_transactions.append(cash)

    if "賬戶交易歷史" not in headers_by_section:
        raise TradeImportError("Schwab transaction section was not found")
    return {
        "fills": fills,
        "cash_transactions": cash_transactions,
        "warnings": warnings,
    }


def rebuild_realized_trades(
    session: Session,
    import_batch_id: int,
    *,
    warnings: list[str] | None = None,
) -> list[RealizedTrade]:
    batch = session.get(ImportBatch, import_batch_id)
    if batch is None:
        raise TradeImportError(f"Unknown import_batch_id: {import_batch_id}")
    warning_list = list(warnings or _decode_warnings(batch.warnings))
    session.execute(delete(RealizedTrade).where(RealizedTrade.import_batch_id == import_batch_id))
    fills = list(
        session.scalars(
            select(TradeFill)
            .where(TradeFill.import_batch_id == import_batch_id)
            .order_by(TradeFill.executed_at.asc().nulls_last(), TradeFill.id.asc())
        )
    )
    open_lots: dict[tuple[str, str], list[OpenLot]] = {}
    realized: list[RealizedTrade] = []
    for fill in fills:
        direction = _direction_for_fill(fill.side, fill.position_effect)
        if fill.position_effect == "open":
            open_lots.setdefault((fill.symbol, direction), []).append(
                OpenLot(quantity=fill.quantity, price=fill.price, opened_at=fill.executed_at)
            )
            continue
        lots = open_lots.setdefault((fill.symbol, direction), [])
        consumed, avg_entry, opened_at, excess = _consume_lots(lots, fill.quantity)
        if excess > 0:
            warning_list.append(
                f"row {fill.id}: unmatched closing quantity {excess} for {fill.symbol}"
            )
        if consumed <= 0:
            continue
        gross_pnl = _gross_pnl(direction, avg_entry, fill.price, consumed)
        holding_period_seconds = None
        if opened_at is not None and fill.executed_at is not None:
            holding_period_seconds = int((fill.executed_at - opened_at).total_seconds())
        trade = RealizedTrade(
            import_batch_id=import_batch_id,
            symbol=fill.symbol,
            direction=direction,
            opened_at=opened_at,
            closed_at=fill.executed_at,
            quantity=consumed,
            avg_entry=avg_entry,
            avg_exit=fill.price,
            gross_pnl=gross_pnl,
            currency=fill.currency,
            holding_period_seconds=holding_period_seconds,
        )
        session.add(trade)
        realized.append(trade)
    batch.warning_count = len(warning_list)
    batch.warnings = json.dumps(warning_list, ensure_ascii=False)
    session.commit()
    for trade in realized:
        session.refresh(trade)
    session.refresh(batch)
    return realized


def list_import_batches(session: Session) -> list[ImportBatch]:
    return list(session.scalars(select(ImportBatch).order_by(ImportBatch.id)))


def list_trade_fills(session: Session, import_batch_id: int | None = None) -> list[TradeFill]:
    statement = select(TradeFill).order_by(TradeFill.id)
    if import_batch_id is not None:
        statement = statement.where(TradeFill.import_batch_id == import_batch_id)
    return list(session.scalars(statement))


def list_cash_transactions(session: Session, import_batch_id: int | None = None) -> list[CashTransaction]:
    statement = select(CashTransaction).order_by(CashTransaction.id)
    if import_batch_id is not None:
        statement = statement.where(CashTransaction.import_batch_id == import_batch_id)
    return list(session.scalars(statement))


def list_realized_trades(session: Session, import_batch_id: int | None = None) -> list[RealizedTrade]:
    statement = select(RealizedTrade).order_by(RealizedTrade.id)
    if import_batch_id is not None:
        statement = statement.where(RealizedTrade.import_batch_id == import_batch_id)
    return list(session.scalars(statement))


def get_import_batch_by_hash(session: Session, content_hash: str) -> ImportBatch | None:
    return session.scalars(select(ImportBatch).where(ImportBatch.content_hash == content_hash)).first()


def warnings_for_batch(batch: ImportBatch) -> list[str]:
    return _decode_warnings(batch.warnings)


def _parse_fill(
    row: list[str],
    headers: list[str],
    file_order: int,
    warnings: list[str],
) -> ParsedFill | None:
    values = _row_dict(headers, row)
    if not values.get("執行時間") or not values.get("代號"):
        return None
    if values.get("到期日") or values.get("行使價"):
        warnings.append(f"row {file_order + 1}: option-like row skipped for {values.get('代號', 'unknown')}")
        return None
    try:
        side = _parse_side(values.get("市場方", ""))
        position_effect = _parse_position_effect(values.get("倉位影響", ""))
        return ParsedFill(
            executed_at_raw=values["執行時間"],
            executed_at=_parse_datetime(values["執行時間"]),
            symbol=values["代號"].upper(),
            side=side,
            quantity=abs(_parse_decimal(values.get("數量", "0"))),
            position_effect=position_effect,
            instrument_type=values.get("類型") or None,
            price=_parse_decimal(values.get("價格", "0")),
            net_price=_parse_optional_decimal(values.get("淨價")),
            order_type=values.get("訂單類型") or None,
            file_order=file_order,
        )
    except (ValueError, ArithmeticError) as exc:
        warnings.append(f"row {file_order + 1}: fill skipped: {exc}")
        return None


def _parse_cash_transaction(
    row: list[str],
    headers: list[str],
    file_order: int,
    warnings: list[str],
) -> ParsedCashTransaction | None:
    values = _row_dict(headers, row)
    if values.get("類型") != "TRD":
        return None
    try:
        return ParsedCashTransaction(
            txn_date=_parse_date(values.get("日期", "")),
            txn_time=values.get("時間") or None,
            ref_no=_clean_ref_no(values.get("參考號", "")) or None,
            description=values.get("說明", ""),
            misc_fees=_parse_optional_decimal(values.get("雜項費用")),
            commissions_fees=_parse_optional_decimal(values.get("佣金及費用")),
            amount=_parse_optional_decimal(values.get("數額")),
        )
    except ValueError as exc:
        warnings.append(f"row {file_order + 1}: cash row skipped: {exc}")
        return None


def _consume_lots(lots: list[OpenLot], quantity: Decimal) -> tuple[Decimal, Decimal, datetime | None, Decimal]:
    remaining = quantity
    consumed = Decimal("0")
    weighted_entry = Decimal("0")
    opened_at: datetime | None = None
    while lots and remaining > 0:
        lot = lots[0]
        take = min(lot.quantity, remaining)
        if opened_at is None:
            opened_at = lot.opened_at
        consumed += take
        weighted_entry += take * lot.price
        lot.quantity -= take
        remaining -= take
        if lot.quantity == 0:
            lots.pop(0)
    avg_entry = Decimal("0") if consumed == 0 else (weighted_entry / consumed).quantize(Decimal("0.000001"))
    return consumed, avg_entry, opened_at, remaining


def _gross_pnl(direction: str, avg_entry: Decimal, avg_exit: Decimal, quantity: Decimal) -> Decimal:
    if direction == "long":
        value = (avg_exit - avg_entry) * quantity
    else:
        value = (avg_entry - avg_exit) * quantity
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _direction_for_fill(side: str, position_effect: str) -> str:
    if position_effect == "open":
        return "long" if side == "buy" else "short"
    return "long" if side == "sell" else "short"


def _parse_side(value: str) -> str:
    if value == "買入":
        return "buy"
    if value == "賣出":
        return "sell"
    raise ValueError(f"unknown side: {value}")


def _parse_position_effect(value: str) -> str:
    if value == "開倉":
        return "open"
    if value == "平倉":
        return "close"
    raise ValueError(f"unknown position effect: {value}")


def _parse_datetime(value: str) -> datetime:
    return datetime.strptime(value.strip(), "%m/%d/%y %H:%M:%S")


def _parse_date(value: str) -> date:
    return datetime.strptime(value.strip(), "%m/%d/%y").date()


def _parse_decimal(value: str | None) -> Decimal:
    normalized = _money_text(value)
    if normalized == "":
        raise ValueError("missing decimal")
    return Decimal(normalized)


def _parse_optional_decimal(value: str | None) -> Decimal | None:
    normalized = _money_text(value)
    if normalized == "":
        return None
    return Decimal(normalized)


def _money_text(value: str | None) -> str:
    if value is None:
        return ""
    text = value.strip().replace(",", "").replace("$", "")
    if text.startswith("(") and text.endswith(")"):
        text = f"-{text[1:-1]}"
    return text


def _clean_ref_no(value: str) -> str:
    text = value.strip()
    if text.startswith('="') and text.endswith('"'):
        return text[2:-1]
    return text


def _clean_cell(value: str) -> str:
    return value.replace("\ufeff", "").replace("\u200b", "").strip()


def _is_section_header(value: str) -> bool:
    if value in SUPPORTED_SECTIONS:
        return True
    return value.startswith("加密貨幣") and value.endswith("賬戶概覽")


def _row_dict(headers: list[str], row: list[str]) -> dict[str, str]:
    padded = row + [""] * max(0, len(headers) - len(row))
    return {header: padded[index] for index, header in enumerate(headers) if header}


def _decode_warnings(value: str | None) -> list[str]:
    if not value:
        return []
    parsed = json.loads(value)
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, str)]


def symbol_from_cash_description(description: str) -> str | None:
    match = re.search(r"\b(?:BOT|SLD)\s+[+-]?\d+(?:\.\d+)?\s+([A-Z.]+)\b", description.upper())
    return match.group(1) if match else None


def is_leveraged_instrument(symbol: str, description: str | None = None) -> bool:
    if symbol.upper() in LEVERAGED_SYMBOLS:
        return True
    return bool(description and LEVERAGED_DESCRIPTION_PATTERN.search(description))
