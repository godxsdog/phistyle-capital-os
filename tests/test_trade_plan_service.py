from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

pytest.importorskip("sqlalchemy")

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from shared.database.base import Base
from shared.models import decision_request, knowledge, market_data, trade_plan  # noqa: F401
from shared.models.decision_request import DecisionRequest
from shared.models.knowledge import DecisionLog, DecisionStatus
from shared.models.market_data import MarketDailyBar
from shared.models.trade_plan import PlanMark, TradePlan
from shared.services.trade_plan_service import (
    TradePlanError,
    close_trade_plan,
    create_trade_plan,
    evaluate_risk_checks,
    mark_open_trade_plans,
    trade_plan_stats,
)


def make_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()


def test_risk_rules_pass_and_each_violation_forces_high():
    passed = evaluate_risk_checks(
        market="taifex",
        symbol="TX",
        direction="long",
        planned_entry=Decimal("20000"),
        stop_price=Decimal("19980"),
        quantity=Decimal("1"),
        declared_capital_twd=Decimal("500000"),
    )
    assert passed.passed is True
    assert passed.forced_risk_level == "medium"

    r1 = evaluate_risk_checks(
        market="taifex",
        symbol="TX",
        direction="long",
        planned_entry=Decimal("20000"),
        stop_price=Decimal("19900"),
        quantity=Decimal("1"),
        declared_capital_twd=Decimal("500000"),
    )
    assert r1.passed is False
    assert r1.forced_risk_level == "high"
    assert next(check for check in r1.checks if check["rule"] == "R1")["passed"] is False

    r2 = evaluate_risk_checks(
        market="us",
        symbol="AAPL",
        direction="short",
        planned_entry=Decimal("200"),
        stop_price=Decimal("190"),
        quantity=Decimal("1"),
        declared_capital_twd=Decimal("500000"),
    )
    assert next(check for check in r2.checks if check["rule"] == "R2")["passed"] is False

    r3 = evaluate_risk_checks(
        market="us",
        symbol="AAPL",
        direction="long",
        planned_entry=Decimal("200"),
        stop_price=Decimal("190"),
        quantity=Decimal("0"),
        declared_capital_twd=Decimal("500000"),
    )
    assert next(check for check in r3.checks if check["rule"] == "R3")["passed"] is False


def test_create_trade_plan_violation_creates_high_risk_decision_request():
    session = make_session()

    plan = create_trade_plan(
        session,
        market="taifex",
        symbol="TX",
        direction="long",
        planned_entry=Decimal("20000"),
        stop_price=Decimal("19900"),
        target_price=Decimal("20200"),
        quantity=Decimal("1"),
        declared_capital_twd=Decimal("500000"),
        thesis="synthetic plan",
        created_by="Kaichang",
    )

    request = session.get(DecisionRequest, plan.decision_request_id)
    assert request is not None
    assert request.risk_level.value == "high"
    assert request.status.value == "submitted"


def test_create_trade_plan_rolls_back_decision_request_when_plan_write_fails(monkeypatch):
    session = make_session()

    def fail_flush_once():
        if session.new and any(isinstance(row, TradePlan) for row in session.new):
            raise RuntimeError("synthetic trade plan write failure")
        return original_flush()

    original_flush = session.flush
    monkeypatch.setattr(session, "flush", fail_flush_once)

    with pytest.raises(RuntimeError):
        create_trade_plan(
            session,
            market="taifex",
            symbol="TX",
            direction="long",
            planned_entry=Decimal("20000"),
            stop_price=Decimal("19980"),
            target_price=None,
            quantity=Decimal("1"),
            declared_capital_twd=Decimal("500000"),
            thesis="synthetic plan",
            created_by="Kaichang",
        )

    assert session.query(DecisionRequest).count() == 0
    assert session.query(TradePlan).count() == 0


def test_mtm_is_idempotent_and_missing_bar_records_ingest_warning():
    session = make_session()
    plan = create_approved_plan(session, symbol="TX")
    session.add(
        MarketDailyBar(
            market="taifex",
            symbol="TX",
            bar_date=date(2026, 7, 9),
            open=Decimal("20000"),
            high=Decimal("20100"),
            low=Decimal("19950"),
            close=Decimal("20080"),
            volume=1,
            open_interest=1,
            source="fixture",
        )
    )
    session.commit()

    first = mark_open_trade_plans(session, mark_date=date(2026, 7, 9))
    second = mark_open_trade_plans(session, mark_date=date(2026, 7, 9))
    missing = mark_open_trade_plans(session, mark_date=date(2026, 7, 10))

    assert first.inserted == 1
    assert second.inserted == 0
    assert second.skipped == 1
    assert missing.warnings
    assert session.query(PlanMark).filter(PlanMark.trade_plan_id == plan.id).count() == 1


def test_close_outcome_and_stats_are_split_by_currency():
    session = make_session()
    twd_plan = create_approved_plan(session, symbol="TX", market="taifex", entry=Decimal("20000"))
    usd_plan = create_approved_plan(session, symbol="AAPL", market="us", entry=Decimal("200"))

    twd = close_trade_plan(session, plan_id=twd_plan.id, exit_price=Decimal("20050"), exit_at=datetime(2026, 7, 10, tzinfo=timezone.utc))
    usd = close_trade_plan(session, plan_id=usd_plan.id, exit_price=Decimal("210"), exit_at=datetime(2026, 7, 10, tzinfo=timezone.utc))
    stats = trade_plan_stats(session)

    assert twd.gross_pnl == Decimal("10000.00")
    assert twd.currency == "TWD"
    assert usd.gross_pnl == Decimal("10.00")
    assert usd.currency == "USD"
    assert {row["currency"] for row in stats["by_currency"]} == {"TWD", "USD"}


def create_approved_plan(
    session,
    *,
    symbol: str,
    market: str = "taifex",
    entry: Decimal = Decimal("20000"),
):
    stop = entry - Decimal("20") if market == "taifex" else entry - Decimal("10")
    plan = create_trade_plan(
        session,
        market=market,
        symbol=symbol,
        direction="long",
        planned_entry=entry,
        stop_price=stop,
        target_price=None,
        quantity=Decimal("1"),
        declared_capital_twd=Decimal("500000"),
        thesis="synthetic plan",
        created_by="Kaichang",
    )
    session.add(
        DecisionLog(
            title="approved",
            decision="approve",
            rationale="fixture",
            status=DecisionStatus.APPROVED,
            related_request_id=str(plan.decision_request_id),
        )
    )
    session.commit()
    return plan
