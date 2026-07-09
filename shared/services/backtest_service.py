from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.models.backtest import BacktestRun, StrategySpec
from shared.models.market_data import InstitutionalPosition, MarketDailyBar


POINT_VALUES_TWD = {"TX": Decimal("200"), "MTX": Decimal("50"), "TMF": Decimal("10")}
FUTURES_FEE_TWD_PER_CONTRACT_SIDE = Decimal("50")
FUTURES_TAX_RATE = Decimal("0.00002")
FUTURES_TAX_SOURCE_URL = "https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=G0380175"
US_SLIPPAGE_RATE_PER_SIDE = Decimal("0.0005")
FUTURES_SLIPPAGE_TICKS_PER_SIDE = Decimal("1")


class BacktestError(ValueError):
    pass


@dataclass(frozen=True)
class BacktestExecution:
    strategy_spec: StrategySpec
    backtest_run: BacktestRun
    created: bool


def list_strategy_specs(session: Session) -> list[StrategySpec]:
    return list(session.scalars(select(StrategySpec).order_by(StrategySpec.id.desc())))


def list_backtest_runs(session: Session) -> list[BacktestRun]:
    return list(session.scalars(select(BacktestRun).order_by(BacktestRun.id.desc())))


def get_backtest_run(session: Session, run_id: int) -> BacktestRun | None:
    return session.get(BacktestRun, run_id)


def run_backtest(session: Session, spec: dict[str, Any]) -> BacktestExecution:
    normalized = normalize_spec(spec)
    bars = _load_bars(session, normalized)
    if len(bars) < 2:
        raise BacktestError("not enough market_daily_bars for backtest")
    range_start = _parse_optional_date(normalized.get("start_date")) or bars[0].bar_date
    range_end = _parse_optional_date(normalized.get("end_date")) or bars[-1].bar_date
    bars = [bar for bar in bars if range_start <= bar.bar_date <= range_end]
    if len(bars) < 2:
        raise BacktestError("selected date range has fewer than 2 bars")
    split_index = int(len(bars) * Decimal("0.7"))
    if split_index <= 0 or split_index >= len(bars):
        raise BacktestError("walk-forward requires both in-sample and out-of-sample bars")
    cost_params = default_cost_params(normalized["market"], normalized["symbol"])
    run_hash = compute_run_hash(normalized, range_start, range_end, cost_params)
    existing = session.scalars(select(BacktestRun).where(BacktestRun.run_hash == run_hash)).first()
    strategy = _get_or_create_strategy_spec(session, normalized)
    if existing is not None:
        return BacktestExecution(strategy_spec=strategy, backtest_run=existing, created=False)
    institutional = _load_institutional_positions(session, normalized, range_start, range_end)
    full_result = _run_window(normalized, bars, institutional, cost_params)
    in_sample_result = _run_window(normalized, bars[:split_index], institutional, cost_params)
    out_sample_result = _run_window(normalized, bars[split_index:], institutional, cost_params)
    results = {
        "cost_disclaimer": "期貨手續費為預設值 TWD 50/口/邊；尚未套用凱基實際費率",
        "tax_source_url": FUTURES_TAX_SOURCE_URL if normalized["market"] == "taifex" else None,
        "known_limitations": [
            "訊號以 t 日收盤計算",
            "stop/target 以後續每日 close 檢查，不看盤中高低",
            "US 結果不做 TWD 匯率換算",
            "不建模保證金",
        ],
        "split": {
            "in_sample_start": bars[0].bar_date.isoformat(),
            "in_sample_end": bars[split_index - 1].bar_date.isoformat(),
            "out_sample_start": bars[split_index].bar_date.isoformat(),
            "out_sample_end": bars[-1].bar_date.isoformat(),
            "decay_ratio": _decay_ratio(in_sample_result["metrics"]["expectancy"], out_sample_result["metrics"]["expectancy"]),
        },
        "full": full_result,
        "in_sample": in_sample_result,
        "out_of_sample": out_sample_result,
    }
    run = BacktestRun(
        strategy_spec_id=strategy.id,
        range_start=range_start,
        range_end=range_end,
        spec_snapshot_json=json.dumps(normalized, ensure_ascii=False, sort_keys=True),
        cost_params_json=json.dumps(cost_params, ensure_ascii=False, sort_keys=True),
        results_json=json.dumps(results, ensure_ascii=False, sort_keys=True),
        run_hash=run_hash,
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return BacktestExecution(strategy_spec=strategy, backtest_run=run, created=True)


def normalize_spec(spec: dict[str, Any]) -> dict[str, Any]:
    required = {"name", "market", "symbol", "direction", "entry", "exit"}
    missing = required - set(spec)
    if missing:
        raise BacktestError(f"missing spec fields: {', '.join(sorted(missing))}")
    normalized = {
        "name": str(spec["name"]).strip(),
        "market": str(spec["market"]).strip().lower(),
        "symbol": str(spec["symbol"]).strip().upper().removesuffix(".US"),
        "direction": str(spec["direction"]).strip().lower(),
        "entry": spec["entry"],
        "exit": spec["exit"],
    }
    if spec.get("start_date"):
        normalized["start_date"] = str(spec["start_date"])
    if spec.get("end_date"):
        normalized["end_date"] = str(spec["end_date"])
    if normalized["market"] not in {"taifex", "us"}:
        raise BacktestError("market must be taifex or us")
    if normalized["market"] == "taifex" and normalized["symbol"] not in POINT_VALUES_TWD:
        raise BacktestError("TAIFEX symbol must be TX, MTX, or TMF")
    if normalized["direction"] not in {"long", "short"}:
        raise BacktestError("direction must be long or short")
    validate_rule(normalized["entry"], market=normalized["market"])
    validate_exit(normalized["exit"])
    return normalized


def validate_rule(rule: dict[str, Any], *, market: str) -> None:
    if not isinstance(rule, dict):
        raise BacktestError("entry rule must be an object")
    rule_type = rule.get("type")
    if rule_type == "sma_cross":
        _positive_int(rule.get("fast"), "fast")
        _positive_int(rule.get("slow"), "slow")
        if int(rule["fast"]) >= int(rule["slow"]):
            raise BacktestError("sma_cross fast must be smaller than slow")
    elif rule_type == "price_vs_sma":
        _positive_int(rule.get("n"), "n")
        if rule.get("side") not in {"above", "below"}:
            raise BacktestError("price_vs_sma side must be above or below")
    elif rule_type == "breakout":
        _positive_int(rule.get("n"), "n")
    elif rule_type == "inst_net":
        if market != "taifex":
            raise BacktestError("inst_net is only allowed for taifex")
        if rule.get("product") not in {"TX", "MTX", "TMF"}:
            raise BacktestError("inst_net product must be TX, MTX, or TMF")
        if rule.get("identity") not in {"foreign", "trust", "dealer"}:
            raise BacktestError("inst_net identity must be foreign, trust, or dealer")
        if rule.get("op") not in {">", "<"}:
            raise BacktestError("inst_net op must be > or <")
        int(rule.get("threshold"))
    else:
        raise BacktestError("unsupported entry rule type")


def validate_exit(exit_rule: dict[str, Any]) -> None:
    if not isinstance(exit_rule, dict):
        raise BacktestError("exit must be an object")
    for key in ("stop_pct", "target_pct"):
        if exit_rule.get(key) is not None and Decimal(str(exit_rule[key])) <= 0:
            raise BacktestError(f"{key} must be positive")
    if exit_rule.get("time_exit_days") is not None and int(exit_rule["time_exit_days"]) <= 0:
        raise BacktestError("time_exit_days must be positive")
    if "opposite_signal" in exit_rule and not isinstance(exit_rule["opposite_signal"], bool):
        raise BacktestError("opposite_signal must be boolean")


def compute_run_hash(spec: dict[str, Any], range_start: date, range_end: date, cost_params: dict[str, Any]) -> str:
    payload = {
        "spec_snapshot": spec,
        "range_start": range_start.isoformat(),
        "range_end": range_end.isoformat(),
        "cost_params": cost_params,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def default_cost_params(market: str, symbol: str) -> dict[str, Any]:
    if market == "taifex":
        return {
            "currency": "TWD",
            "point_value": str(POINT_VALUES_TWD[symbol]),
            "fee_per_contract_per_side": str(FUTURES_FEE_TWD_PER_CONTRACT_SIDE),
            "fee_is_placeholder": True,
            "futures_tax_rate": str(FUTURES_TAX_RATE),
            "futures_tax_source_url": FUTURES_TAX_SOURCE_URL,
            "slippage_ticks_per_side": str(FUTURES_SLIPPAGE_TICKS_PER_SIDE),
            "slippage_value_per_side": str(POINT_VALUES_TWD[symbol]),
        }
    return {"currency": "USD", "commission": "0", "slippage_rate_per_side": str(US_SLIPPAGE_RATE_PER_SIDE), "twd_conversion_applied": False}


def _run_window(
    spec: dict[str, Any],
    bars: list[MarketDailyBar],
    institutional: dict[tuple[date, str, str], int],
    cost_params: dict[str, Any],
) -> dict[str, Any]:
    trades = []
    equity_curve = []
    position = None
    equity = Decimal("0")
    for index, bar in enumerate(bars):
        signal = _entry_signal(spec, bars, index, institutional)
        if position is None and signal:
            position = {"entry_index": index, "entry_date": bar.bar_date, "entry_price": Decimal(bar.close)}
            continue
        if position is not None and _should_exit(spec, bars, index, position, signal):
            trade = _close_trade(spec, position, bar, cost_params)
            trades.append(trade)
            equity += Decimal(trade["net_pnl"])
            equity_curve.append({"date": bar.bar_date.isoformat(), "equity": str(_money(equity))})
            position = None
    metrics = _metrics(trades, equity_curve)
    return {"trades": trades, "equity_curve": equity_curve, "metrics": metrics}


def _entry_signal(spec: dict[str, Any], bars: list[MarketDailyBar], index: int, institutional: dict[tuple[date, str, str], int]) -> bool:
    rule = spec["entry"]
    direction = spec["direction"]
    if rule["type"] == "sma_cross":
        fast = int(rule["fast"])
        slow = int(rule["slow"])
        if index < slow:
            return False
        prev_fast = _sma(bars, index - 1, fast)
        prev_slow = _sma(bars, index - 1, slow)
        curr_fast = _sma(bars, index, fast)
        curr_slow = _sma(bars, index, slow)
        return curr_fast > curr_slow and prev_fast <= prev_slow if direction == "long" else curr_fast < curr_slow and prev_fast >= prev_slow
    if rule["type"] == "price_vs_sma":
        n = int(rule["n"])
        if index < n:
            return False
        prev_close = Decimal(bars[index - 1].close)
        curr_close = Decimal(bars[index].close)
        prev_sma = _sma(bars, index - 1, n)
        curr_sma = _sma(bars, index, n)
        return prev_close <= prev_sma and curr_close > curr_sma if rule["side"] == "above" else prev_close >= prev_sma and curr_close < curr_sma
    if rule["type"] == "breakout":
        n = int(rule["n"])
        if index < n:
            return False
        previous = bars[index - n : index]
        close = Decimal(bars[index].close)
        return close > max(Decimal(row.high) for row in previous) if direction == "long" else close < min(Decimal(row.low) for row in previous)
    if rule["type"] == "inst_net":
        value = institutional.get((bars[index].bar_date, rule["product"], rule["identity"]))
        if value is None:
            return False
        threshold = int(rule["threshold"])
        return value > threshold if rule["op"] == ">" else value < threshold
    return False


def _should_exit(spec: dict[str, Any], bars: list[MarketDailyBar], index: int, position: dict[str, Any], signal: bool) -> bool:
    if index <= position["entry_index"]:
        return False
    close = Decimal(bars[index].close)
    entry = Decimal(position["entry_price"])
    exit_rule = spec["exit"]
    direction = spec["direction"]
    if exit_rule.get("stop_pct") is not None:
        stop_pct = Decimal(str(exit_rule["stop_pct"]))
        if direction == "long" and close <= entry * (Decimal("1") - stop_pct):
            return True
        if direction == "short" and close >= entry * (Decimal("1") + stop_pct):
            return True
    if exit_rule.get("target_pct") is not None:
        target_pct = Decimal(str(exit_rule["target_pct"]))
        if direction == "long" and close >= entry * (Decimal("1") + target_pct):
            return True
        if direction == "short" and close <= entry * (Decimal("1") - target_pct):
            return True
    if exit_rule.get("time_exit_days") is not None and index - position["entry_index"] >= int(exit_rule["time_exit_days"]):
        return True
    return bool(exit_rule.get("opposite_signal")) and signal


def _close_trade(spec: dict[str, Any], position: dict[str, Any], exit_bar: MarketDailyBar, cost_params: dict[str, Any]) -> dict[str, str]:
    entry_price = Decimal(position["entry_price"])
    exit_price = Decimal(exit_bar.close)
    quantity = Decimal("1")
    sign = Decimal("1") if spec["direction"] == "long" else Decimal("-1")
    if spec["market"] == "taifex":
        point_value = Decimal(cost_params["point_value"])
        gross = (exit_price - entry_price) * point_value * quantity * sign
        fee = Decimal(cost_params["fee_per_contract_per_side"]) * quantity * Decimal("2")
        tax = ((entry_price + exit_price) * point_value * quantity * Decimal(cost_params["futures_tax_rate"]))
        slippage = Decimal(cost_params["slippage_value_per_side"]) * quantity * Decimal("2")
        currency = "TWD"
    else:
        gross = (exit_price - entry_price) * quantity * sign
        fee = Decimal("0")
        tax = Decimal("0")
        slippage = (entry_price + exit_price) * quantity * Decimal(cost_params["slippage_rate_per_side"])
        currency = "USD"
    net = gross - fee - tax - slippage
    return {
        "entry_date": position["entry_date"].isoformat(),
        "exit_date": exit_bar.bar_date.isoformat(),
        "entry_price": str(entry_price),
        "exit_price": str(exit_price),
        "gross_pnl": str(_money(gross)),
        "fee": str(_money(fee)),
        "tax": str(_money(tax)),
        "slippage": str(_money(slippage)),
        "net_pnl": str(_money(net)),
        "currency": currency,
    }


def _metrics(trades: list[dict[str, str]], equity_curve: list[dict[str, str]]) -> dict[str, Any]:
    pnl = [Decimal(row["net_pnl"]) for row in trades]
    total = sum(pnl, Decimal("0"))
    count = len(pnl)
    wins = sum(1 for value in pnl if value > 0)
    return {
        "trade_count": count,
        "net_pnl": str(_money(total)),
        "max_drawdown": str(_money(_max_drawdown(equity_curve))),
        "win_rate": wins / count if count else 0,
        "expectancy": str(_money(total / count)) if count else "0.00",
        "exposure_days": sum(_days(row["entry_date"], row["exit_date"]) for row in trades),
    }


def _load_bars(session: Session, spec: dict[str, Any]) -> list[MarketDailyBar]:
    return list(
        session.scalars(
            select(MarketDailyBar)
            .where(MarketDailyBar.market == spec["market"], MarketDailyBar.symbol == spec["symbol"])
            .order_by(MarketDailyBar.bar_date)
        )
    )


def _load_institutional_positions(session: Session, spec: dict[str, Any], range_start: date, range_end: date) -> dict[tuple[date, str, str], int]:
    if spec["entry"]["type"] != "inst_net":
        return {}
    rows = session.scalars(
        select(InstitutionalPosition).where(
            InstitutionalPosition.trade_date >= range_start,
            InstitutionalPosition.trade_date <= range_end,
        )
    )
    return {(row.trade_date, row.product, row.identity): row.net_contracts for row in rows}


def _get_or_create_strategy_spec(session: Session, spec: dict[str, Any]) -> StrategySpec:
    existing = session.scalars(select(StrategySpec).where(StrategySpec.name == spec["name"])).first()
    spec_json = json.dumps(spec, ensure_ascii=False, sort_keys=True)
    if existing is not None:
        if existing.spec_json != spec_json:
            raise BacktestError("strategy spec name already exists with a different definition")
        return existing
    row = StrategySpec(name=spec["name"], market=spec["market"], symbol=spec["symbol"], direction=spec["direction"], spec_json=spec_json)
    session.add(row)
    session.flush()
    return row


def _sma(bars: list[MarketDailyBar], index: int, n: int) -> Decimal:
    window = bars[index - n + 1 : index + 1]
    return sum((Decimal(row.close) for row in window), Decimal("0")) / Decimal(n)


def _max_drawdown(equity_curve: list[dict[str, str]]) -> Decimal:
    peak = Decimal("0")
    max_dd = Decimal("0")
    for point in equity_curve:
        equity = Decimal(point["equity"])
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return max_dd


def _decay_ratio(is_expectancy: str, oos_expectancy: str) -> str:
    is_value = Decimal(is_expectancy)
    if is_value <= 0:
        return "n/a"
    return str((Decimal(oos_expectancy) / is_value).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def _parse_optional_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def _positive_int(value: object, name: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise BacktestError(f"{name} must be positive")
    return parsed


def _days(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
