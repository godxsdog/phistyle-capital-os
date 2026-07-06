from datetime import date
from decimal import Decimal
import json

import pytest


pytest.importorskip("sqlalchemy")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from shared.database.base import Base
from shared.models import point_wallet  # noqa: F401
from shared.services.exchange_rate_service import get_twd_per_unit, refresh_fx_rates
from shared.services.point_wallet_legacy_import import import_legacy_point_wallet_data
from shared.services.point_wallet_service import (
    create_ledger_transaction,
    get_portfolio_summary,
    list_accounts,
    list_cost_lots,
    list_ledger_transactions,
    list_purchase_offers,
    list_transfer_rules,
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


def write_synthetic_rescue(tmp_path):
    data_dir = tmp_path / "data-rescue"
    data_dir.mkdir()
    (data_dir / "points_wallet.json").write_text(
        json.dumps(
            {
                "accounts": {
                    "kai": [
                        {
                            "id": "kent-aero",
                            "category": "airline",
                            "program": "Aeroplan",
                            "balance": 10000,
                            "costPerPoint": 0.31,
                            "expiryDate": "2026-08-01",
                            "note": "synthetic",
                        }
                    ],
                    "wife": [
                        {
                            "id": "wife-bank",
                            "category": "bank",
                            "program": "Wanlitong",
                            "balance": 20000,
                            "costPerPoint": 0.1,
                            "expiryDate": "",
                            "note": "synthetic",
                        }
                    ],
                },
                "transfers": {"kai": [], "wife": []},
                "awardCosts": {"kai": {}, "wife": {}},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (data_dir / "pingan_wanlitong_rules.json").write_text(
        json.dumps(
            {
                "programs": [
                    {
                        "program": "Aeroplan",
                        "wanlitongPerMile": 3,
                        "bonusMultiplier": 1.25,
                        "formula": "synthetic 25% bonus",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (data_dir / "official_purchase_costs.json").write_text(
        json.dumps(
            {
                "programs": [
                    {
                        "program": "Aeroplan",
                        "vendor": "official",
                        "costPerMile": 0.5,
                        "bonusPercent": 25,
                        "endsAt": "2026-12-31",
                        "note": "synthetic offer",
                    }
                ],
                "source": "manual",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return data_dir


def test_legacy_import_round_trip_lots_rules_offers_and_idempotency(tmp_path):
    session = make_session()
    data_dir = write_synthetic_rescue(tmp_path)

    first = import_legacy_point_wallet_data(session, data_dir=data_dir, import_date=date(2026, 7, 6))
    second = import_legacy_point_wallet_data(session, data_dir=data_dir, import_date=date(2026, 7, 6))

    assert first.warnings == []
    assert second.created["ledger_transactions"] == 0
    assert len(list_accounts(session)) == 2
    assert len(list_ledger_transactions(session)) == 2
    assert len(list_cost_lots(session)) == 2
    assert len(list_transfer_rules(session)) == 1
    assert len(list_purchase_offers(session)) == 1


def test_lot_math_and_append_only_ledger_are_hand_computed(tmp_path):
    session = make_session()
    data_dir = write_synthetic_rescue(tmp_path)
    import_legacy_point_wallet_data(session, data_dir=data_dir, import_date=date(2026, 7, 6))

    summary = get_portfolio_summary(session, owner="kent", today=date(2026, 7, 6))

    assert summary["total_real_cost_basis_twd"] == Decimal("3100.00")
    assert summary["accounts"][0].balance == Decimal("10000.00")
    assert summary["accounts"][0].avg_cost_per_point_twd == Decimal("0.310000")
    assert summary["expiring_soon"][0].expires_at == date(2026, 8, 1)

    account_id = summary["accounts"][0].account_id
    create_ledger_transaction(
        session,
        account_id=account_id,
        kind="adjustment",
        quantity=Decimal("500"),
        occurred_at=date(2026, 7, 7),
        cost_total=Decimal("200"),
        cost_currency="TWD",
        create_lot=True,
    )

    assert len(list_ledger_transactions(session, account_id)) == 2
    assert get_portfolio_summary(session, owner="kent")["accounts"][0].balance == Decimal("10500.00")


def test_fx_refresh_falls_back_when_api_fails(monkeypatch):
    session = make_session()

    def fail_fetch():
        raise TimeoutError("synthetic timeout")

    monkeypatch.setattr("shared.services.exchange_rate_service._fetch_open_er_api_rates", fail_fetch)
    result = refresh_fx_rates(session, as_of=date(2026, 7, 6))

    assert result["source"] == "fallback"
    assert get_twd_per_unit(session, "USD", as_of=date(2026, 7, 6)) == Decimal("31.500000")
