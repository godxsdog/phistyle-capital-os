from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

pytest.importorskip("sqlalchemy")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from shared.database.base import Base
from shared.models import backtest, market_data  # noqa: F401
from shared.models.backtest import BacktestRun
from shared.models.market_data import InstitutionalPosition, MarketDailyBar
from shared.services.backtest_service import BacktestError, run_backtest


def make_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()


def seed_sma_fixture(session) -> None:
    closes = [
        Decimal("10"),
        Decimal("10"),
        Decimal("10"),
        Decimal("12"),
        Decimal("14"),
        Decimal("13"),
        Decimal("12"),
        Decimal("11"),
        Decimal("10"),
        Decimal("9"),
    ]
    for offset, close in enumerate(closes):
        session.add(
            MarketDailyBar(
                market="taifex",
                symbol="TX",
                bar_date=date(2026, 1, 1) + timedelta(days=offset),
                open=close,
                high=close,
                low=close,
                close=close,
                volume=100,
                open_interest=1000,
                source="fixture",
            )
        )
    session.commit()


def sma_spec() -> dict:
    return {
        "name": "fixture sma cross",
        "market": "taifex",
        "symbol": "TX",
        "direction": "long",
        "entry": {"type": "sma_cross", "fast": 2, "slow": 3},
        "exit": {"target_pct": 0.1, "opposite_signal": False},
    }


def test_sma_cross_fixture_trades_and_net_pnl_are_hand_calculated_to_cents():
    session = make_session()
    seed_sma_fixture(session)

    result = run_backtest(session, sma_spec())

    payload = result.backtest_run.results_json
    import json

    parsed = json.loads(payload)
    trades = parsed["full"]["trades"]
    metrics = parsed["full"]["metrics"]

    assert len(trades) == 1
    assert trades[0] == {
        "entry_date": "2026-01-04",
        "exit_date": "2026-01-05",
        "entry_price": "12.000000",
        "exit_price": "14.000000",
        "gross_pnl": "400.00",
        "fee": "100.00",
        "tax": "0.10",
        "slippage": "400.00",
        "net_pnl": "-100.10",
        "currency": "TWD",
    }
    assert metrics["trade_count"] == 1
    assert metrics["net_pnl"] == "-100.10"
    assert metrics["max_drawdown"] == "100.10"
    assert metrics["win_rate"] == 0
    assert metrics["expectancy"] == "-100.10"
    assert parsed["split"]["decay_ratio"] == "n/a"
    assert parsed["in_sample"]["metrics"]["net_pnl"] == "-100.10"
    assert parsed["out_of_sample"]["metrics"]["trade_count"] == 0


def test_run_hash_is_idempotent_and_market_tables_are_read_only():
    session = make_session()
    seed_sma_fixture(session)

    first = run_backtest(session, sma_spec())
    second = run_backtest(session, sma_spec())

    assert first.created is True
    assert second.created is False
    assert first.backtest_run.id == second.backtest_run.id
    assert session.query(BacktestRun).count() == 1
    assert session.query(MarketDailyBar).count() == 10
    assert session.query(InstitutionalPosition).count() == 0


def test_insufficient_market_data_is_rejected():
    session = make_session()
    session.add(
        MarketDailyBar(
            market="taifex",
            symbol="TX",
            bar_date=date(2026, 1, 1),
            open=Decimal("10"),
            high=Decimal("10"),
            low=Decimal("10"),
            close=Decimal("10"),
            volume=100,
            open_interest=1000,
            source="fixture",
        )
    )
    session.commit()

    with pytest.raises(BacktestError, match="not enough"):
        run_backtest(session, sma_spec())
