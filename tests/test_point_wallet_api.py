from datetime import date

import pytest


pytest.importorskip("sqlalchemy")
pytest.importorskip("fastapi")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.main import app, get_session
from shared.database.base import Base
from shared.models import point_wallet  # noqa: F401


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


def test_wallet_routes_create_account_lot_and_portfolio():
    client = make_client()
    program = client.post("/wallet/programs", json={"name": "Aeroplan", "kind": "airline"}).json()
    account = client.post(
        "/wallet/accounts",
        json={"owner": "kent", "program_id": program["id"], "account_ref": "123456789"},
    ).json()
    response = client.post(
        "/wallet/ledger",
        json={
            "account_id": account["id"],
            "kind": "buy",
            "quantity": "10000",
            "occurred_at": "2026-07-06",
            "cost_total": "3100",
            "cost_currency": "TWD",
            "create_lot": True,
        },
    )

    assert response.status_code == 200
    portfolio = client.get("/wallet/portfolio?owner=kent").json()
    assert portfolio["total_real_cost_basis_twd"] == "3100.00"
    assert portfolio["accounts"][0]["balance"] == "10000.00"
    assert client.get("/wallet/accounts").json()[0]["account_ref"] == "***6789"


def test_wallet_transfer_rule_offer_fx_and_registry_contract(monkeypatch):
    client = make_client()
    wanlitong = client.post("/wallet/programs", json={"name": "平安萬里通", "kind": "bank"}).json()
    aeroplan = client.post("/wallet/programs", json={"name": "Aeroplan", "kind": "airline"}).json()

    rule = client.post(
        "/wallet/transfer-rules",
        json={
            "from_program_id": wanlitong["id"],
            "to_program_id": aeroplan["id"],
            "ratio_from": "3",
            "ratio_to": "1",
            "bonus_pct": "25",
            "valid_from": "2026-07-06",
            "source_url": "https://example.test/transfer",
        },
    )
    offer = client.post(
        "/wallet/purchase-offers",
        json={
            "program_id": aeroplan["id"],
            "kind": "official",
            "base_price": "0.5",
            "currency": "TWD",
            "bonus_pct": "25",
            "start_date": "2026-07-06",
            "source_url": "https://example.test/offer",
        },
    )

    def fail_fetch():
        raise TimeoutError("synthetic timeout")

    monkeypatch.setattr("shared.services.exchange_rate_service._fetch_open_er_api_rates", fail_fetch)
    fx = client.post("/wallet/fx-rates/refresh")
    apps = client.get("/apps").json()
    wallet = next(app for app in apps if app["id"] == "points-wallet")

    assert rule.status_code == 200
    assert rule.json()["source_url"] == "https://example.test/transfer"
    assert offer.json()["effective_cpp"] == "0.400000"
    assert offer.json()["source_url"] == "https://example.test/offer"
    assert fx.json()["source"] == "fallback"
    assert wallet["status"] == "scaffold-active"
    assert wallet["route"] == "/wallet"


def test_wallet_transfer_rule_update_delete_and_ai_preview(monkeypatch):
    client = make_client()
    wanlitong = client.post("/wallet/programs", json={"name": "平安萬里通", "kind": "bank"}).json()
    aeroplan = client.post("/wallet/programs", json={"name": "Aeroplan", "kind": "airline"}).json()
    rule = client.post(
        "/wallet/transfer-rules",
        json={
            "from_program_id": wanlitong["id"],
            "to_program_id": aeroplan["id"],
            "ratio_from": "3",
            "ratio_to": "1",
            "valid_from": "2026-07-06",
        },
    ).json()

    updated = client.patch(
        f"/wallet/transfer-rules/{rule['id']}",
        json={
            "from_program_id": wanlitong["id"],
            "to_program_id": aeroplan["id"],
            "ratio_from": "35",
            "ratio_to": "1",
            "bonus_pct": "0",
            "valid_from": "2026-07-06",
            "source_url": "https://example.test/verified",
        },
    )

    def fake_parse(source_program_name, pasted_text):
        assert source_program_name == "平安萬里通"
        assert "加贈" in pasted_text
        return {
            "from_program_name": "平安萬里通",
            "to_program_name": "Aeroplan",
            "ratio_from": "30000",
            "ratio_to": "10000",
            "bonus_pct": "20",
            "min_transfer": None,
            "rule_kind": "linear",
            "block_size": None,
            "block_bonus_points": None,
            "valid_until": "2026-08-31",
            "source_url": "https://example.test/promo",
            "note": None,
        }

    monkeypatch.setattr("backend.app.main._parse_wallet_rule_with_deepseek", fake_parse)
    preview = client.post(
        "/wallet/ai-parse-rule",
        json={"source_program_name": "平安萬里通", "pasted_text": "Aeroplan 轉點加贈 20%"},
    )
    deleted = client.delete(f"/wallet/transfer-rules/{rule['id']}")

    assert updated.status_code == 200
    assert updated.json()["ratio_from"] == "35.00"
    assert updated.json()["source_url"] == "https://example.test/verified"
    assert preview.status_code == 200
    assert preview.json()["status"] == "preview"
    assert preview.json()["preview"]["note"] == "AI解析-待確認"
    assert deleted.status_code == 200
    assert client.get("/wallet/transfer-rules").json() == []


def test_wallet_award_quote_evaluate_endpoint_is_read_only_for_lots():
    client = make_client()
    wanlitong = client.post("/wallet/programs", json={"name": "平安萬里通", "kind": "bank"}).json()
    aeroplan = client.post("/wallet/programs", json={"name": "Aeroplan", "kind": "airline"}).json()
    account = client.post("/wallet/accounts", json={"owner": "kent", "program_id": wanlitong["id"]}).json()
    client.post(
        "/wallet/ledger",
        json={
            "account_id": account["id"],
            "kind": "buy",
            "quantity": "100000",
            "occurred_at": "2026-07-01",
            "cost_total": "10000",
            "cost_currency": "TWD",
            "create_lot": True,
        },
    )
    client.post(
        "/wallet/transfer-rules",
        json={
            "from_program_id": wanlitong["id"],
            "to_program_id": aeroplan["id"],
            "ratio_from": "2",
            "ratio_to": "1",
            "valid_from": "2026-01-01",
        },
    )
    quote = client.post(
        "/wallet/award-quotes",
        json={
            "origin": "TPE",
            "destination": "TYO",
            "program_id": aeroplan["id"],
            "miles_required": "30000",
            "taxes_amount": "1000",
            "taxes_currency": "TWD",
            "cash_price_twd": "50000",
        },
    ).json()
    before = client.get("/wallet/cost-lots").json()

    response = client.post(f"/wallet/award-quotes/{quote['id']}/evaluate", json={"evaluation_date": "2026-07-07"})

    after = client.get("/wallet/cost-lots").json()
    assert response.status_code == 200
    assert after == before
    scenarios = response.json()
    assert scenarios[0]["method"] == "transfer_chain"
    assert scenarios[0]["total_cash_cost_twd"] == "7000.00"
    assert scenarios[0]["points_consumed"] == "60000.00"


def test_wallet_award_watch_snapshot_promote_and_expiry_routes(monkeypatch):
    client = make_client()
    aeroplan = client.post("/wallet/programs", json={"name": "aeroplan", "kind": "airline"}).json()
    account = client.post("/wallet/accounts", json={"owner": "kent", "program_id": aeroplan["id"]}).json()
    client.post(
        "/wallet/ledger",
        json={
            "account_id": account["id"],
            "kind": "earn",
            "quantity": "12000",
            "occurred_at": "2026-01-01",
            "note": "manual expires_at=2026-10-06",
        },
    )
    watch = client.post(
        "/wallet/award-watches",
        json={
            "origin": "tpe",
            "destination": "tyo",
            "cabin": "business",
            "start_date": "2026-11-01",
            "end_date": "2026-11-07",
            "program_id": aeroplan["id"],
        },
    ).json()
    updated_watch = client.patch(
        f"/wallet/award-watches/{watch['id']}",
        json={
            "origin": "tpe",
            "destination": "osa",
            "cabin": "economy",
            "start_date": "2026-11-01",
            "end_date": "2026-11-07",
            "program_id": aeroplan["id"],
            "active": True,
            "note": "updated",
        },
    )
    delete_watch = client.post(
        "/wallet/award-watches",
        json={"origin": "tpe", "destination": "sel", "cabin": "business"},
    ).json()
    deleted_watch = client.delete(f"/wallet/award-watches/{delete_watch['id']}")

    from shared.models.point_wallet import AwardSnapshot
    from shared.services.seats_aero_service import SeatsAeroFetchResult

    def fake_fetch(session, *, watch_id, seen_date=None):
        snapshot = AwardSnapshot(
            watch_id=watch_id,
            seen_date=seen_date or date(2026, 7, 8),
            status="success",
            result_count=1,
            normalized_json=(
                '[{"origin":"TPE","destination":"TYO","travel_date":"2026-11-01",'
                '"cabin":"business","program_source":"aeroplan","miles_required":"45000"}]'
            ),
            raw_json='{"data":[]}',
        )
        session.add(snapshot)
        session.commit()
        return SeatsAeroFetchResult(snapshot=snapshot, created=True)

    monkeypatch.setattr("backend.app.main.fetch_award_watch", fake_fetch)
    fetched = client.post(f"/wallet/award-watches/{watch['id']}/fetch", json={"seen_date": "2026-07-08"})
    promoted = client.post(f"/wallet/award-snapshots/{fetched.json()['id']}/promote", json={"item_index": 0})
    alerts = client.post("/wallet/expiry-alerts/scan")

    assert updated_watch.status_code == 200
    assert updated_watch.json()["destination"] == "OSA"
    assert deleted_watch.status_code == 200
    assert client.get("/wallet/award-watches").json()[0]["origin"] == "TPE"
    assert fetched.status_code == 200
    assert fetched.json()["result_count"] == 1
    assert promoted.status_code == 200
    assert promoted.json()["award_quote"]["source"] == "seats_aero"
    assert promoted.json()["award_quote"]["miles_required"] == "45000"
    assert alerts.status_code == 200


def test_wallet_hotel_voucher_routes_and_status_guard():
    client = make_client()
    marriott = client.post("/wallet/programs", json={"name": "Marriott Bonvoy", "kind": "hotel"}).json()

    created = client.post(
        "/wallet/hotel-vouchers",
        json={
            "owner": "kent",
            "program_id": marriott["id"],
            "face_value_points": "50000",
            "expires_at": "2026-08-28",
            "acquired_note": "synthetic FNC",
        },
    )
    listed = client.get("/wallet/hotel-vouchers")
    used = client.patch(
        f"/wallet/hotel-vouchers/{created.json()['id']}/status",
        json={"status": "used", "used_note": "已訂房"},
    )
    rejected = client.patch(
        f"/wallet/hotel-vouchers/{created.json()['id']}/status",
        json={"status": "expired", "used_note": "try again"},
    )

    assert created.status_code == 200
    assert created.json()["program_name"] == "Marriott Bonvoy"
    assert listed.json()[0]["face_value_points"] == "50000"
    assert used.status_code == 200
    assert used.json()["status"] == "used"
    assert rejected.status_code == 409
