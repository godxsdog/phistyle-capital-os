from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

import pytest

pytest.importorskip("sqlalchemy")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from shared.database.base import Base
from shared.models import market_data  # noqa: F401
from shared.models.market_data import IngestRun, MarketDailyBar, SettlementCalendar
from shared.services.market_data_service import (
    DailyBarInput,
    count_business_day_gaps,
    ingest_manual_bars,
    parse_taifex_daily_csv,
    parse_taifex_institutional_html,
    parse_yahoo_chart_json,
)


def make_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return factory()


def test_parse_yahoo_chart_json_uses_raw_ohlcv_only():
    payload = {
        "chart": {
            "result": [
                {
                    "timestamp": [1783296000],
                    "indicators": {
                        "quote": [
                            {
                                "open": [100.0],
                                "high": [110.0],
                                "low": [90.0],
                                "close": [105.0],
                                "volume": [123456],
                            }
                        ],
                        "adjclose": [{"adjclose": [99.0]}],
                    },
                }
            ],
            "error": None,
        }
    }

    bars = parse_yahoo_chart_json(json.dumps(payload), "aapl.us")

    assert len(bars) == 1
    assert bars[0].symbol == "AAPL"
    assert bars[0].close == Decimal("105.0")
    assert bars[0].open_interest is None
    assert bars[0].source == "yahoo"


def test_parse_taifex_daily_csv_and_settlement_contracts():
    csv_text = (
        "交易日期,商品,到期月份(週別),開盤價,最高價,最低價,收盤價,漲跌價,漲跌%,成交量,結算價,未沖銷契約量,最後最佳買價,最後最佳賣價,歷史最高價,歷史最低價,是否因訊息面暫停交易,交易時段,價差對單式委託成交量\n"
        "2026/07/01,TX,202607  ,47516,47695,46895,47231,452,0.97%,58097,47221,105030,47204,47232,49240,36972,,一般,,\n"
        "2026/07/01,TX,202607  ,46684,47520,46365,47428,649,1.39%,39982,-,-,47424,47430,49240,36972,,盤後,,\n"
    )

    bars, settlements = parse_taifex_daily_csv(csv_text)

    assert len(bars) == 1
    assert bars[0].market == "taifex"
    assert bars[0].symbol == "TX"
    assert bars[0].open_interest == 105030
    assert settlements == [market_data_service_settlement("TX", "202607", date(2026, 7, 1))]


def test_parse_taifex_institutional_html_extracts_open_interest_columns():
    html = """
    <table>
      <tr><td>1</td><td>臺股期貨</td><td>自營商</td><td>1</td><td>2</td><td>3</td><td>4</td><td>5</td><td>6</td><td>1,000</td><td>10</td><td>700</td><td>7</td><td>300</td><td>3</td></tr>
      <tr><td>2</td><td>臺股期貨</td><td>投信</td><td>1</td><td>2</td><td>3</td><td>4</td><td>5</td><td>6</td><td>500</td><td>5</td><td>800</td><td>8</td><td>-300</td><td>-3</td></tr>
      <tr><td>3</td><td>臺股期貨</td><td>外資及陸資</td><td>1</td><td>2</td><td>3</td><td>4</td><td>5</td><td>6</td><td>2,000</td><td>20</td><td>1,200</td><td>12</td><td>800</td><td>8</td></tr>
    </table>
    """

    rows = parse_taifex_institutional_html(html, "TX", date(2026, 7, 8))

    assert [(row.identity, row.long_contracts, row.short_contracts, row.net_contracts) for row in rows] == [
        ("dealer", 1000, 700, 300),
        ("trust", 500, 800, -300),
        ("foreign", 2000, 1200, 800),
    ]


def test_idempotent_ingest_never_mutates_existing_bar_and_records_correction():
    session = make_session()
    first = DailyBarInput(
        market="us",
        symbol="AAPL",
        bar_date=date(2026, 7, 6),
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("90"),
        close=Decimal("105"),
        volume=1000,
        open_interest=None,
        source="yahoo",
    )
    changed = DailyBarInput(**{**first.__dict__, "close": Decimal("106")})

    ingest_manual_bars(session, "yahoo", [first])
    ingest_manual_bars(session, "yahoo", [first])
    ingest_manual_bars(session, "yahoo", [changed])

    bars = session.query(MarketDailyBar).all()
    corrections = session.query(IngestRun).filter(IngestRun.status == "correction_detected").all()
    assert len(bars) == 1
    assert bars[0].close == Decimal("105.000000")
    assert len(corrections) == 1
    assert "old=" in (corrections[0].detail or "")


def test_gap_detection_counts_missing_business_days():
    session = make_session()
    bars = [
        DailyBarInput("us", "AAPL", date(2026, 7, 6), Decimal("1"), Decimal("1"), Decimal("1"), Decimal("1"), 1, None, "yahoo"),
        DailyBarInput("us", "AAPL", date(2026, 7, 8), Decimal("1"), Decimal("1"), Decimal("1"), Decimal("1"), 1, None, "yahoo"),
    ]
    ingest_manual_bars(session, "yahoo", bars)

    assert count_business_day_gaps(session, "us", "AAPL") == 1


def test_settlement_calendar_is_inserted_from_taifex_contract_months():
    session = make_session()
    csv_text = (
        "交易日期,商品,到期月份(週別),開盤價,最高價,最低價,收盤價,成交量,未沖銷契約量,交易時段\n"
        "2026/07/01,TX,202607,1,2,1,2,100,200,一般\n"
    )
    bars, settlements = parse_taifex_daily_csv(csv_text)
    ingest_manual_bars(session, "taifex", bars)
    for settlement in settlements:
        session.add(SettlementCalendar(**settlement.__dict__))
    session.commit()

    row = session.query(SettlementCalendar).one()
    assert row.contract == "202607"
    assert row.last_trading_date == date(2026, 7, 1)


def market_data_service_settlement(product: str, contract: str, last_trading_date: date):
    from shared.services.market_data_service import SettlementCalendarInput

    return SettlementCalendarInput(product=product, contract=contract, last_trading_date=last_trading_date)
