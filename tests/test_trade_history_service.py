import pytest


pytest.importorskip("sqlalchemy")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from services.llm_router.types import LLMResponse
from shared.database.base import Base
from shared.models import trade_history  # noqa: F401
from shared.services.trade_attribution_service import get_trade_attribution_metrics
from shared.services.trade_import_service import (
    import_trade_history,
    is_leveraged_instrument,
    list_import_batches,
    list_realized_trades,
    list_trade_fills,
    parse_schwab_statement,
)


def make_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return session_factory()


def schwab_fixture() -> bytes:
    return (
        "\ufeff現金餘額\n"
        "日期,時間,類型,參考號,說明,雜項費用,佣金及費用,數額,餘額\n"
        '6/1/26,09:31:00,TRD,"=""1001""","BOT +300 UUUU @ multiple",-0.02,-1.30,"-3,878.30","10,000.00"\n'
        '6/6/26,10:01:00,TRD,"=""1002""","SLD -350 UUUU @ close",-0.03,-1.40,"4,000.00","14,000.00"\n'
        "賬戶訂單歷史\n"
        "執行時間,狀態,代號\n"
        "6/1/26 09:00:00,已取消,IGNORED\n"
        "賬戶交易歷史\n"
        ",\u200b執行時間,價差,市場方,數量,倉位影響,代號,到期日,行使價,類型,價格,淨價,訂單類型\n"
        ",6/1/26 09:30:00,,買入,+100,開倉,UUUU,,,股票,10.00,10.00,LMT\n"
        ",6/2/26 09:30:00,,買入,+100,開倉,UUUU,,,股票,8.00,8.00,LMT\n"
        ",6/3/26 09:30:00,,買入,+100,開倉,UUUU,,,股票,7.00,7.00,LMT\n"
        ",6/4/26 10:00:00,,賣出,-150,平倉,UUUU,,,股票,12.00,12.00,LMT\n"
        ",6/5/26 10:00:00,,賣出,-200,平倉,UUUU,,,股票,6.00,6.00,LMT\n"
        ",6/7/26 09:30:00,,賣出,-10,開倉,TSLL,,,ETF,20.00,20.00,LMT\n"
        ",6/7/26 09:30:00,,賣出,-5,開倉,TSLL,,,ETF,22.00,22.00,LMT\n"
        ",6/8/26 10:00:00,,買入,+12,平倉,TSLL,,,ETF,18.00,18.00,LMT\n"
        ",6/9/26 10:00:00,,買入,+1,開倉,OPT,6/19/26,100,股票,1.00,1.00,LMT\n"
        "股票\n"
        "Symbol,Description\n"
        "IGNORED,Ignored position section\n"
    ).encode("utf-8")


def test_schwab_parser_handles_sections_headers_and_cash_rows():
    parsed = parse_schwab_statement(schwab_fixture())

    assert len(parsed["fills"]) == 8
    assert len(parsed["cash_transactions"]) == 2
    assert parsed["fills"][0].executed_at_raw == "6/1/26 09:30:00"
    assert parsed["fills"][0].side == "buy"
    assert parsed["fills"][0].position_effect == "open"
    assert parsed["cash_transactions"][0].ref_no == "1001"
    assert str(parsed["cash_transactions"][0].amount) == "-3878.30"
    assert parsed["warnings"] == ["row 18: option-like row skipped for OPT"]


def test_import_rebuilds_fifo_realized_trades_and_is_idempotent():
    session = make_session()

    first = import_trade_history(session, source="schwab", file_bytes=schwab_fixture())
    second = import_trade_history(session, source="schwab", file_bytes=schwab_fixture())
    trades = list_realized_trades(session)

    assert first.created is True
    assert second.created is False
    assert first.batch.id == second.batch.id
    assert len(list_import_batches(session)) == 1
    assert len(list_trade_fills(session)) == 8
    assert len(trades) == 3
    assert [(trade.symbol, trade.direction, str(trade.quantity), str(trade.gross_pnl)) for trade in trades] == [
        ("UUUU", "long", "150.0000", "400.00"),
        ("UUUU", "long", "150.0000", "-200.00"),
        ("TSLL", "short", "12.0000", "28.00"),
    ]
    assert str(trades[0].avg_entry) == "9.333333"
    assert any("unmatched closing quantity" in warning for warning in first.warnings)


def test_metrics_detect_averaging_down_leveraged_flags_and_mocked_narrative(monkeypatch):
    session = make_session()
    import_trade_history(session, source="schwab", file_bytes=schwab_fixture())

    def mock_chat(self, request):
        return LLMResponse(
            provider_id="deepseek",
            model="deepseek-reasoner",
            content='{"narrative":"Losses cluster in averaged-down UUUU trades; TSLL was profitable."}',
            dry_run=False,
            metadata={},
        )

    monkeypatch.setattr("shared.services.trade_attribution_service.DeepSeekProvider.chat", mock_chat)

    metrics = get_trade_attribution_metrics(session)

    assert metrics["trade_count"] == 3
    assert metrics["gross_pnl"] == "228.00"
    assert metrics["win_rate"] == pytest.approx(0.6667)
    assert metrics["expectancy"] == "76.00"
    assert metrics["max_consecutive_losses"] == 1
    assert metrics["averaging_down"] == [
        {"symbol": "UUUU", "direction": "long", "prices": ["10.000000", "8.000000", "7.000000"]}
    ]
    assert "TSLL" in metrics["leveraged_symbols"]
    assert is_leveraged_instrument("ABC", "UltraPro 3X Bull ETF") is True
    assert metrics["narrative"]["llm_backed"] is True
    assert "averaged-down" in metrics["narrative"]["text"]


def test_metrics_narrative_falls_back_when_provider_fails(monkeypatch):
    session = make_session()
    import_trade_history(session, source="schwab", file_bytes=schwab_fixture())

    def mock_chat(self, request):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr("shared.services.trade_attribution_service.DeepSeekProvider.chat", mock_chat)

    metrics = get_trade_attribution_metrics(session)

    assert metrics["narrative"] == {
        "text": "Narrative unavailable; deterministic metrics are still available.",
        "llm_backed": False,
        "llm_provider": None,
        "llm_model": None,
        "fallback_reason": "provider_error",
    }
