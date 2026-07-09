from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.models.decision_request import DecisionRequestStatus
from shared.models.knowledge import DecisionLog, DecisionStatus
from shared.models.market_data import IngestRun, MarketDailyBar
from shared.models.trade_plan import PlanMark, PlanOutcome, TradePlan
from shared.services.capital_decision_support_service import create_capital_decision_request


POINT_VALUES_TWD = {"TX": Decimal("200"), "MTX": Decimal("50"), "TMF": Decimal("10")}
US_PLACEHOLDER_FX_TWD = Decimal("32")


class TradePlanError(ValueError):
    pass


class TradePlanNotFoundError(TradePlanError):
    pass


class TradePlanOutcomeExistsError(TradePlanError):
    pass


@dataclass(frozen=True)
class RiskCheckResult:
    passed: bool
    forced_risk_level: str
    checks: list[dict[str, Any]]
    risk_amount: str
    risk_currency: str
    risk_amount_twd: str
    max_allowed_twd: str


@dataclass(frozen=True)
class MtmResult:
    inserted: int
    skipped: int
    warnings: list[str]


def create_trade_plan(
    session: Session,
    *,
    market: str,
    symbol: str,
    direction: str,
    planned_entry: Decimal,
    stop_price: Decimal,
    target_price: Decimal | None,
    quantity: Decimal,
    declared_capital_twd: Decimal,
    thesis: str,
    strategy_spec_id: int | None = None,
    is_paper: bool = True,
    created_by: str | None = None,
) -> TradePlan:
    normalized_market = _normalize_market(market)
    normalized_symbol = _normalize_symbol(normalized_market, symbol)
    normalized_direction = _normalize_direction(direction)
    normalized_thesis = _required(thesis, "thesis")
    risk_check = evaluate_risk_checks(
        market=normalized_market,
        symbol=normalized_symbol,
        direction=normalized_direction,
        planned_entry=planned_entry,
        stop_price=stop_price,
        quantity=quantity,
        declared_capital_twd=declared_capital_twd,
    )
    question, context, options = _compose_decision_text(
        market=normalized_market,
        symbol=normalized_symbol,
        direction=normalized_direction,
        planned_entry=planned_entry,
        stop_price=stop_price,
        target_price=target_price,
        quantity=quantity,
        declared_capital_twd=declared_capital_twd,
        thesis=normalized_thesis,
        risk_check=risk_check,
    )
    try:
        decision_request = create_capital_decision_request(
            session,
            question=question,
            context=context,
            options=options,
            risk_level=risk_check.forced_risk_level,
            created_by=created_by or "trade-plan",
            commit=False,
        )
        plan = TradePlan(
            decision_request_id=decision_request.id,
            market=normalized_market,
            symbol=normalized_symbol,
            direction=normalized_direction,
            planned_entry=planned_entry,
            stop_price=stop_price,
            target_price=target_price,
            quantity=quantity,
            declared_capital_twd=declared_capital_twd,
            thesis=normalized_thesis,
            strategy_spec_id=strategy_spec_id,
            is_paper=is_paper,
            risk_check=json.dumps(risk_check.__dict__, ensure_ascii=False),
        )
        session.add(plan)
        session.commit()
        session.refresh(plan)
        return plan
    except Exception:
        session.rollback()
        raise


def evaluate_risk_checks(
    *,
    market: str,
    symbol: str,
    direction: str,
    planned_entry: Decimal,
    stop_price: Decimal,
    quantity: Decimal,
    declared_capital_twd: Decimal,
) -> RiskCheckResult:
    checks: list[dict[str, Any]] = []
    risk_amount, risk_currency, risk_amount_twd = _risk_amount(
        market=market,
        symbol=symbol,
        planned_entry=planned_entry,
        stop_price=stop_price,
        quantity=quantity,
    )
    max_allowed_twd = declared_capital_twd * Decimal("0.01") if declared_capital_twd > 0 else Decimal("0")
    r1_pass = risk_amount_twd <= max_allowed_twd and declared_capital_twd > 0
    r2_pass = (direction == "long" and stop_price < planned_entry) or (direction == "short" and stop_price > planned_entry)
    r3_pass = quantity > 0 and declared_capital_twd > 0
    checks.append({"rule": "R1", "passed": r1_pass, "message": "每筆風險需小於等於宣告資本 1%"})
    checks.append({"rule": "R2", "passed": r2_pass, "message": "停損價必須在虧損方向"})
    checks.append({"rule": "R3", "passed": r3_pass, "message": "數量與宣告資本必須大於 0"})
    passed = all(bool(check["passed"]) for check in checks)
    return RiskCheckResult(
        passed=passed,
        forced_risk_level="medium" if passed else "high",
        checks=checks,
        risk_amount=str(_money(risk_amount)),
        risk_currency=risk_currency,
        risk_amount_twd=str(_money(risk_amount_twd)),
        max_allowed_twd=str(_money(max_allowed_twd)),
    )


def list_trade_plans(session: Session) -> list[TradePlan]:
    return list(session.scalars(select(TradePlan).order_by(TradePlan.id.desc())))


def get_trade_plan(session: Session, plan_id: int) -> TradePlan:
    plan = session.get(TradePlan, plan_id)
    if plan is None:
        raise TradePlanNotFoundError(f"Unknown trade_plan_id: {plan_id}")
    return plan


def close_trade_plan(
    session: Session,
    *,
    plan_id: int,
    exit_price: Decimal,
    exit_at: datetime,
    notes: str | None = None,
) -> PlanOutcome:
    plan = get_trade_plan(session, plan_id)
    existing = session.scalars(select(PlanOutcome).where(PlanOutcome.trade_plan_id == plan.id)).first()
    if existing is not None:
        raise TradePlanOutcomeExistsError("plan outcome already exists")
    gross_pnl, currency = compute_gross_pnl(plan, exit_price)
    holding_days = (exit_at.date() - plan.created_at.date()).days if plan.created_at is not None else None
    stop_respected = _stop_respected(plan, exit_price)
    planned_vs_actual = {
        "planned_entry": str(plan.planned_entry),
        "stop_price": str(plan.stop_price),
        "target_price": str(plan.target_price) if plan.target_price is not None else None,
        "exit_price": str(exit_price),
        "stop_respected": stop_respected,
    }
    outcome = PlanOutcome(
        trade_plan_id=plan.id,
        exit_price=exit_price,
        exit_at=exit_at,
        gross_pnl=gross_pnl,
        stop_respected=stop_respected,
        notes=notes,
        holding_days=holding_days,
        planned_vs_actual=json.dumps(planned_vs_actual, ensure_ascii=False),
        currency=currency,
    )
    session.add(outcome)
    session.commit()
    session.refresh(outcome)
    return outcome


def mark_open_trade_plans(session: Session, mark_date: date | None = None) -> MtmResult:
    target_date = mark_date or date.today()
    inserted = 0
    skipped = 0
    warnings: list[str] = []
    for plan in _open_approved_plans(session):
        existing = session.scalars(
            select(PlanMark).where(PlanMark.trade_plan_id == plan.id, PlanMark.mark_date == target_date)
        ).first()
        if existing is not None:
            skipped += 1
            continue
        bar = session.scalars(
            select(MarketDailyBar).where(
                MarketDailyBar.market == plan.market,
                MarketDailyBar.symbol == plan.symbol,
                MarketDailyBar.bar_date == target_date,
            )
        ).first()
        if bar is None:
            skipped += 1
            warning = f"missing bar for trade_plan_id={plan.id} {plan.market}/{plan.symbol} {target_date.isoformat()}"
            warnings.append(warning)
            session.add(
                IngestRun(
                    source="trade_plan_mtm",
                    run_date=target_date,
                    status="missing_bar",
                    detail=warning,
                    finished_at=datetime.now(timezone.utc),
                )
            )
            continue
        session.add(PlanMark(trade_plan_id=plan.id, mark_date=target_date, close_price=bar.close))
        inserted += 1
    session.commit()
    return MtmResult(inserted=inserted, skipped=skipped, warnings=warnings)


def trade_plan_stats(session: Session) -> dict[str, Any]:
    outcomes = list(session.scalars(select(PlanOutcome).order_by(PlanOutcome.currency, PlanOutcome.id)))
    plans_by_id = {plan.id: plan for plan in session.scalars(select(TradePlan))}
    by_currency: dict[str, dict[str, Any]] = {}
    for outcome in outcomes:
        bucket = by_currency.setdefault(
            outcome.currency,
            {"currency": outcome.currency, "closed_plan_count": 0, "wins": 0, "gross_pnl": Decimal("0"), "stop_respected": 0, "risk_passed": 0},
        )
        bucket["closed_plan_count"] += 1
        bucket["gross_pnl"] += outcome.gross_pnl
        if outcome.gross_pnl > 0:
            bucket["wins"] += 1
        if outcome.stop_respected:
            bucket["stop_respected"] += 1
        plan = plans_by_id.get(outcome.trade_plan_id)
        if plan and json.loads(plan.risk_check).get("passed"):
            bucket["risk_passed"] += 1
    result = []
    for bucket in by_currency.values():
        count = bucket["closed_plan_count"]
        result.append(
            {
                "currency": bucket["currency"],
                "closed_plan_count": count,
                "win_rate": bucket["wins"] / count if count else 0,
                "expectancy": str(_money(bucket["gross_pnl"] / count)) if count else "0.00",
                "gross_pnl": str(_money(bucket["gross_pnl"])),
                "plan_adherence_rate": (bucket["stop_respected"] + bucket["risk_passed"]) / (count * 2) if count else 0,
            }
        )
    return {"by_currency": result, "total_closed_plan_count": len(outcomes)}


def compute_gross_pnl(plan: TradePlan, exit_price: Decimal) -> tuple[Decimal, str]:
    direction_sign = Decimal("1") if plan.direction == "long" else Decimal("-1")
    if plan.market == "taifex":
        point_value = POINT_VALUES_TWD.get(plan.symbol)
        if point_value is None:
            raise TradePlanError(f"unsupported TAIFEX symbol: {plan.symbol}")
        pnl = (exit_price - plan.planned_entry) * point_value * plan.quantity * direction_sign
        return _money(pnl), "TWD"
    pnl = (exit_price - plan.planned_entry) * plan.quantity * direction_sign
    return _money(pnl), "USD"


def _risk_amount(
    *,
    market: str,
    symbol: str,
    planned_entry: Decimal,
    stop_price: Decimal,
    quantity: Decimal,
) -> tuple[Decimal, str, Decimal]:
    distance = abs(planned_entry - stop_price)
    if market == "taifex":
        point_value = POINT_VALUES_TWD.get(symbol)
        if point_value is None:
            raise TradePlanError("TAIFEX symbol must be TX, MTX, or TMF")
        amount = distance * point_value * quantity
        return amount, "TWD", amount
    amount = distance * quantity
    return amount, "USD", amount * US_PLACEHOLDER_FX_TWD


def _open_approved_plans(session: Session) -> list[TradePlan]:
    outcome_plan_ids = select(PlanOutcome.trade_plan_id)
    approved_request_ids = {
        int(row)
        for row in session.scalars(select(DecisionLog.related_request_id).where(DecisionLog.status == DecisionStatus.APPROVED))
        if row is not None and str(row).isdigit()
    }
    if not approved_request_ids:
        return []
    return list(
        session.scalars(
            select(TradePlan)
            .where(TradePlan.decision_request_id.in_(approved_request_ids))
            .where(TradePlan.id.not_in(outcome_plan_ids))
            .order_by(TradePlan.id)
        )
    )


def _compose_decision_text(
    *,
    market: str,
    symbol: str,
    direction: str,
    planned_entry: Decimal,
    stop_price: Decimal,
    target_price: Decimal | None,
    quantity: Decimal,
    declared_capital_twd: Decimal,
    thesis: str,
    risk_check: RiskCheckResult,
) -> tuple[str, str, str]:
    question = f"交易計畫審查：{market.upper()} {symbol} {direction}"
    context = "\n".join(
        [
            f"市場: {market}",
            f"標的: {symbol}",
            f"方向: {direction}",
            f"計畫進場: {planned_entry}",
            f"停損: {stop_price}",
            f"目標: {target_price if target_price is not None else '未填'}",
            f"數量: {quantity}",
            f"宣告資本 TWD: {declared_capital_twd}",
            f"論點: {thesis}",
            f"風控結果 JSON: {json.dumps(risk_check.__dict__, ensure_ascii=False)}",
        ]
    )
    options = "approve paper plan | reject | revise as new plan"
    return question, context, options


def _normalize_market(value: str) -> str:
    market = value.strip().lower()
    if market not in {"taifex", "us"}:
        raise TradePlanError("market must be taifex or us")
    return market


def _normalize_symbol(market: str, value: str) -> str:
    symbol = value.strip().upper().removesuffix(".US")
    if not symbol:
        raise TradePlanError("symbol is required")
    if market == "taifex" and symbol not in POINT_VALUES_TWD:
        raise TradePlanError("TAIFEX symbol must be TX, MTX, or TMF")
    return symbol


def _normalize_direction(value: str) -> str:
    direction = value.strip().lower()
    if direction not in {"long", "short"}:
        raise TradePlanError("direction must be long or short")
    return direction


def _required(value: str | None, field_name: str) -> str:
    if value is None or not value.strip():
        raise TradePlanError(f"{field_name} is required")
    return value.strip()


def _stop_respected(plan: TradePlan, exit_price: Decimal) -> bool:
    if plan.direction == "long":
        return exit_price >= plan.stop_price
    return exit_price <= plan.stop_price


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
