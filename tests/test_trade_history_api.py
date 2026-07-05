import pytest


pytest.importorskip("sqlalchemy")
fastapi = pytest.importorskip("fastapi")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.main import app, get_session
from services.llm_router.types import LLMResponse
from shared.database.base import Base
from shared.models import trade_history  # noqa: F401


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
    ).encode("utf-8")


def make_client():
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
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    def override_session():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = override_session
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def mocked_narrative(monkeypatch):
    def mock_chat(self, request):
        return LLMResponse(
            provider_id="deepseek",
            model="deepseek-reasoner",
            content='{"narrative":"Synthetic trade history narrative."}',
            dry_run=False,
            metadata={},
        )

    monkeypatch.setattr("shared.services.trade_attribution_service.DeepSeekProvider.chat", mock_chat)


def upload(client):
    return client.post(
        "/capital/trade-imports",
        data={"source": "schwab"},
        files={"file": ("synthetic-schwab.csv", schwab_fixture(), "text/csv")},
    )


def test_trade_import_upload_returns_counts_and_warnings():
    client = make_client()

    response = upload(client)

    assert response.status_code == 200
    body = response.json()
    assert body["created"] is True
    assert body["fill_count"] == 8
    assert body["cash_row_count"] == 2
    assert body["warning_count"] == 2
    assert any("option-like row skipped" in warning for warning in body["warnings"])
    assert any("unmatched closing quantity" in warning for warning in body["warnings"])


def test_trade_import_upload_is_idempotent_by_content_hash():
    client = make_client()

    first = upload(client).json()
    second = upload(client).json()
    batches = client.get("/capital/trade-imports").json()

    assert first["created"] is True
    assert second["created"] is False
    assert second["batch_id"] == first["batch_id"]
    assert len(batches) == 1


def test_trade_history_read_endpoints_return_imported_records():
    client = make_client()
    upload(client)

    fills = client.get("/capital/trade-fills").json()
    cash = client.get("/capital/cash-transactions").json()
    trades = client.get("/capital/realized-trades").json()
    metrics = client.get("/capital/trade-attribution").json()

    assert len(fills) == 8
    assert len(cash) == 2
    assert [trade["gross_pnl"] for trade in trades] == ["400.00", "-200.00", "28.00"]
    assert metrics["trade_count"] == 3
    assert metrics["gross_pnl"] == "228.00"
    assert metrics["narrative"]["llm_backed"] is True


def test_trade_import_rejects_unsupported_source():
    client = make_client()

    response = client.post(
        "/capital/trade-imports",
        data={"source": "kgi"},
        files={"file": ("synthetic-kgi.csv", b"not supported", "text/csv")},
    )

    assert response.status_code == 422
    assert "Only source=schwab" in response.json()["detail"]
