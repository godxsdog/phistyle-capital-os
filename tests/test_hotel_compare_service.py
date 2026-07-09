from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

pytest.importorskip("sqlalchemy")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from shared.database.base import Base
from shared.models import point_wallet  # noqa: F401
from shared.services.hotel_compare_service import create_hotel_stay_quote, evaluate_hotel_stay_quote
from shared.services.point_wallet_service import (
    create_account,
    create_hotel_voucher,
    create_ledger_transaction,
    create_program,
    list_cost_lots,
    list_hotel_vouchers,
)


def make_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()


def seed_base(*, points: Decimal = Decimal("100000"), lot_points: Decimal = Decimal("100000")):
    session = make_session()
    marriott = create_program(session, name="Marriott Bonvoy", kind="hotel")
    account = create_account(session, owner="kent", program_id=marriott.id)
    if lot_points > 0:
        create_ledger_transaction(
            session,
            account_id=account.id,
            kind="buy",
            quantity=lot_points,
            occurred_at=date(2026, 7, 1),
            cost_total=lot_points * Decimal("0.2"),
            cost_currency="TWD",
            create_lot=True,
        )
    extra = points - lot_points
    if extra:
        create_ledger_transaction(
            session,
            account_id=account.id,
            kind="earn",
            quantity=extra,
            occurred_at=date(2026, 7, 2),
            note="synthetic no cost basis",
        )
    return session, marriott


def lot_snapshot(session):
    return [(lot.id, lot.remaining_quantity, lot.total_cost_twd, lot.acquired_at) for lot in list_cost_lots(session)]


def voucher_snapshot(session):
    return [(voucher.id, voucher.status, voucher.used_note, voucher.expires_at) for voucher in list_hotel_vouchers(session)]


def option(result, method):
    return next(row for row in result["options"] if row["method"] == method)


def test_one_night_hand_computed_cash_points_and_voucher_read_only():
    session, marriott = seed_base()
    create_hotel_voucher(session, owner="kent", program_id=marriott.id, face_value_points=Decimal("50000"), expires_at=date(2026, 8, 28))
    quote = create_hotel_stay_quote(
        session,
        owner="kent",
        hotel_name="Synthetic Marriott",
        stay_date=date(2026, 8, 1),
        nights=1,
        program_id=marriott.id,
        cash_price_twd=Decimal("12000"),
        points_price_per_night=Decimal("50000"),
    )
    before_lots = lot_snapshot(session)
    before_vouchers = voucher_snapshot(session)

    result = evaluate_hotel_stay_quote(session, quote.id)

    assert lot_snapshot(session) == before_lots
    assert voucher_snapshot(session) == before_vouchers
    assert result["cpp"] == "0.240000"
    assert result["total_points"] == "50000.00"
    assert option(result, "cash")["cash_cost_twd"] == "12000.00"
    assert option(result, "points")["cash_cost_twd"] == "10000.00"
    assert option(result, "voucher")["cash_cost_twd"] == "0.00"
    assert "消耗面額 50K 券(到期 2026-08-28)" in option(result, "voucher")["notes"][0]


def test_two_nights_one_voucher_remaining_night_costs_10000_twd():
    session, marriott = seed_base()
    create_hotel_voucher(session, owner="kent", program_id=marriott.id, face_value_points=Decimal("50000"), expires_at=date(2026, 8, 28))
    quote = create_hotel_stay_quote(
        session,
        owner="kent",
        hotel_name="Two Night Marriott",
        stay_date=date(2026, 8, 1),
        nights=2,
        program_id=marriott.id,
        cash_price_twd=Decimal("24000"),
        points_price_per_night=Decimal("50000"),
    )

    result = evaluate_hotel_stay_quote(session, quote.id)
    voucher = option(result, "voucher")

    assert result["total_points"] == "100000.00"
    assert voucher["cash_cost_twd"] == "10000.00"
    assert voucher["nights_with_voucher"] == 1
    assert voucher["nights_with_points"] == 1
    assert "1 晚用券 + 1 晚點數" in voucher["notes"]


def test_points_shortage_and_partial_cost_basis_are_distinct():
    short_session, short_program = seed_base(points=Decimal("40000"), lot_points=Decimal("40000"))
    short_quote = create_hotel_stay_quote(
        short_session,
        owner="kent",
        hotel_name="Shortage",
        stay_date=date(2026, 8, 1),
        nights=1,
        program_id=short_program.id,
        cash_price_twd=Decimal("12000"),
        points_price_per_night=Decimal("50000"),
    )
    short = option(evaluate_hotel_stay_quote(short_session, short_quote.id), "points")

    partial_session, partial_program = seed_base(points=Decimal("50000"), lot_points=Decimal("25000"))
    partial_quote = create_hotel_stay_quote(
        partial_session,
        owner="kent",
        hotel_name="Partial",
        stay_date=date(2026, 8, 1),
        nights=1,
        program_id=partial_program.id,
        cash_price_twd=Decimal("12000"),
        points_price_per_night=Decimal("50000"),
    )
    partial = option(evaluate_hotel_stay_quote(partial_session, partial_quote.id), "points")

    assert short["available"] is False
    assert "點數不足" in short["notes"]
    assert short["rank"] is None
    assert partial["available"] is True
    assert partial["cash_cost_twd"] == "5000.00"
    assert "部分無成本基礎" in partial["notes"]


def test_topup_boundary_equal_allowed_exceeding_disallowed():
    equal_session, equal_program = seed_base(points=Decimal("10000"), lot_points=Decimal("10000"))
    create_hotel_voucher(equal_session, owner="kent", program_id=equal_program.id, face_value_points=Decimal("45000"), expires_at=date(2026, 8, 1))
    equal_quote = create_hotel_stay_quote(
        equal_session,
        owner="kent",
        hotel_name="Topup Equal",
        stay_date=date(2026, 8, 1),
        nights=1,
        program_id=equal_program.id,
        cash_price_twd=Decimal("12000"),
        points_price_per_night=Decimal("50000"),
        topup_allowed=True,
        topup_points=Decimal("5000"),
    )

    exceed_session, exceed_program = seed_base(points=Decimal("10000"), lot_points=Decimal("10000"))
    create_hotel_voucher(exceed_session, owner="kent", program_id=exceed_program.id, face_value_points=Decimal("44999"), expires_at=date(2026, 8, 1))
    exceed_quote = create_hotel_stay_quote(
        exceed_session,
        owner="kent",
        hotel_name="Topup Exceed",
        stay_date=date(2026, 8, 1),
        nights=1,
        program_id=exceed_program.id,
        cash_price_twd=Decimal("12000"),
        points_price_per_night=Decimal("50000"),
        topup_allowed=True,
        topup_points=Decimal("5000"),
    )

    equal = option(evaluate_hotel_stay_quote(equal_session, equal_quote.id), "voucher_topup")
    exceed = option(evaluate_hotel_stay_quote(exceed_session, exceed_quote.id), "voucher_topup")

    assert equal["available"] is True
    assert equal["cash_cost_twd"] == "1000.00"
    assert equal["points_consumed"] == "5000.00"
    assert exceed["available"] is False
    assert "沒有符合補點上限的 active 免房券" in exceed["notes"]
