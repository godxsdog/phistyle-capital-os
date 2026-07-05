from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from services.llm_router.providers.deepseek import DeepSeekProvider
from services.llm_router.types import LLMRequest, ModelRole
from shared.models.trade_history import CashTransaction, RealizedTrade, TradeFill
from shared.services.trade_import_service import (
    is_leveraged_instrument,
    list_cash_transactions,
    list_realized_trades,
    list_trade_fills,
    symbol_from_cash_description,
)


@dataclass(frozen=True)
class AttributionNarrative:
    text: str
    llm_backed: bool
    llm_provider: str | None
    llm_model: str | None
    fallback_reason: str | None


def get_trade_attribution_metrics(session: Session) -> dict[str, Any]:
    trades = list_realized_trades(session)
    fills = list_trade_fills(session)
    cash_transactions = list_cash_transactions(session)
    metrics = _deterministic_metrics(trades, fills, cash_transactions)
    narrative = generate_trade_attribution_narrative(metrics)
    metrics["narrative"] = {
        "text": narrative.text,
        "llm_backed": narrative.llm_backed,
        "llm_provider": narrative.llm_provider,
        "llm_model": narrative.llm_model,
        "fallback_reason": narrative.fallback_reason,
    }
    return metrics


def generate_trade_attribution_narrative(metrics: dict[str, Any]) -> AttributionNarrative:
    prompt = (
        "You are writing a concise loss-attribution narrative from deterministic trading metrics.\n"
        "Return strict JSON only: {\"narrative\":\"string\"}.\n"
        "Do not calculate new numbers, do not recommend trades, and do not claim future profitability.\n\n"
        f"Metrics:\n{json.dumps(_metrics_for_prompt(metrics), ensure_ascii=True)}"
    )
    try:
        response = DeepSeekProvider().chat(LLMRequest(role=ModelRole.DEEP_REASONER, prompt=prompt))
    except Exception:
        return _fallback_narrative("provider_error")
    if response.dry_run:
        return _fallback_narrative("no_api_key", provider=response.provider_id, model=response.model)
    try:
        parsed = json.loads(response.content)
    except json.JSONDecodeError:
        return _fallback_narrative("invalid_json", provider=response.provider_id, model=response.model)
    narrative = parsed.get("narrative") if isinstance(parsed, dict) else None
    if not isinstance(narrative, str) or not narrative.strip():
        return _fallback_narrative("schema_invalid", provider=response.provider_id, model=response.model)
    return AttributionNarrative(
        text=narrative,
        llm_backed=True,
        llm_provider=response.provider_id,
        llm_model=response.model,
        fallback_reason=None,
    )


def _deterministic_metrics(
    trades: list[RealizedTrade],
    fills: list[TradeFill],
    cash_transactions: list[CashTransaction],
) -> dict[str, Any]:
    gross_pnl = sum((trade.gross_pnl for trade in trades), Decimal("0"))
    wins = [trade for trade in trades if trade.gross_pnl > 0]
    losses = [trade for trade in trades if trade.gross_pnl < 0]
    by_symbol: dict[str, dict[str, Any]] = {}
    by_direction: dict[str, dict[str, Any]] = {}
    by_holding_period: dict[str, dict[str, Any]] = {}
    by_entry_weekday: dict[str, dict[str, Any]] = {}
    by_entry_hour: dict[str, dict[str, Any]] = {}
    instrument_by_symbol = _instrument_type_by_symbol(fills)
    by_instrument_type: dict[str, dict[str, Any]] = {}
    for trade in trades:
        _add_bucket(by_symbol, trade.symbol, trade.gross_pnl)
        _add_bucket(by_direction, trade.direction, trade.gross_pnl)
        _add_bucket(by_holding_period, _holding_period_bucket(trade.holding_period_seconds), trade.gross_pnl)
        _add_bucket(by_instrument_type, instrument_by_symbol.get(trade.symbol, "unknown"), trade.gross_pnl)
        if trade.opened_at is not None:
            _add_bucket(by_entry_weekday, trade.opened_at.strftime("%A"), trade.gross_pnl)
            _add_bucket(by_entry_hour, f"{trade.opened_at.hour:02d}:00", trade.gross_pnl)
    symbol_fees = _fees_by_symbol_month(cash_transactions)
    leveraged_symbols = sorted({fill.symbol for fill in fills if is_leveraged_instrument(fill.symbol)})
    return {
        "trade_count": len(trades),
        "gross_pnl": _money(gross_pnl),
        "win_rate": 0 if not trades else round(len(wins) / len(trades), 4),
        "expectancy": _money(gross_pnl / Decimal(len(trades))) if trades else "0.00",
        "max_consecutive_losses": _max_consecutive_losses(trades),
        "by_symbol": _bucket_list(by_symbol, fees=symbol_fees),
        "by_direction": _bucket_list(by_direction),
        "by_instrument_type": _bucket_list(by_instrument_type),
        "by_holding_period": _bucket_list(by_holding_period),
        "by_entry_weekday": _bucket_list(by_entry_weekday),
        "by_entry_hour": _bucket_list(by_entry_hour),
        "averaging_down": detect_averaging_down(fills),
        "leveraged_symbols": leveraged_symbols,
    }


def detect_averaging_down(fills: list[TradeFill]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    current: dict[tuple[str, str], list[Decimal]] = {}
    for fill in sorted(fills, key=lambda item: (item.executed_at or item.id, item.id)):
        direction = _open_direction(fill)
        if fill.position_effect == "close":
            current.pop((fill.symbol, "long"), None)
            current.pop((fill.symbol, "short"), None)
            continue
        prices = current.setdefault((fill.symbol, direction), [])
        prices.append(fill.price)
        if len(prices) >= 3:
            last_three = prices[-3:]
            if direction == "long" and last_three[0] > last_three[1] > last_three[2]:
                results.append({"symbol": fill.symbol, "direction": direction, "prices": [str(price) for price in last_three]})
            if direction == "short" and last_three[0] < last_three[1] < last_three[2]:
                results.append({"symbol": fill.symbol, "direction": direction, "prices": [str(price) for price in last_three]})
    return results


def _fallback_narrative(
    reason: str,
    *,
    provider: str | None = None,
    model: str | None = None,
) -> AttributionNarrative:
    return AttributionNarrative(
        text="Narrative unavailable; deterministic metrics are still available.",
        llm_backed=False,
        llm_provider=provider,
        llm_model=model,
        fallback_reason=reason,
    )


def _metrics_for_prompt(metrics: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in metrics.items() if key != "narrative"}


def _add_bucket(buckets: dict[str, dict[str, Any]], key: str, pnl: Decimal) -> None:
    bucket = buckets.setdefault(key, {"count": 0, "gross_pnl": Decimal("0")})
    bucket["count"] += 1
    bucket["gross_pnl"] += pnl


def _bucket_list(
    buckets: dict[str, dict[str, Any]],
    *,
    fees: dict[str, dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    rows = []
    for key, value in sorted(buckets.items()):
        row = {
            "key": key,
            "count": value["count"],
            "gross_pnl": _money(value["gross_pnl"]),
        }
        if fees:
            row["fees_by_month"] = fees.get(key, {})
        rows.append(row)
    return rows


def _fees_by_symbol_month(cash_transactions: list[CashTransaction]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, Decimal]] = {}
    for txn in cash_transactions:
        symbol = symbol_from_cash_description(txn.description)
        if symbol is None:
            continue
        month = txn.txn_date.strftime("%Y-%m")
        fees = (txn.misc_fees or Decimal("0")) + (txn.commissions_fees or Decimal("0"))
        result.setdefault(symbol, {}).setdefault(month, Decimal("0"))
        result[symbol][month] += fees
    return {
        symbol: {month: _money(value) for month, value in months.items()}
        for symbol, months in result.items()
    }


def _instrument_type_by_symbol(fills: list[TradeFill]) -> dict[str, str]:
    result: dict[str, str] = {}
    for fill in fills:
        if fill.instrument_type and fill.symbol not in result:
            result[fill.symbol] = fill.instrument_type
    return result


def _max_consecutive_losses(trades: list[RealizedTrade]) -> int:
    longest = 0
    current = 0
    for trade in sorted(trades, key=lambda item: (item.closed_at or item.id, item.id)):
        if trade.gross_pnl < 0:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def _holding_period_bucket(seconds: int | None) -> str:
    if seconds is None:
        return "unknown"
    days = seconds / 86400
    if days < 1:
        return "intraday"
    if days <= 5:
        return "1-5d"
    if days <= 20:
        return "6-20d"
    return "20d+"


def _open_direction(fill: TradeFill) -> str:
    return "long" if fill.side == "buy" else "short"


def _money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01")))
