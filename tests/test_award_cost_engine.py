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
from shared.models.point_wallet import FxRate
from shared.services.award_cost_engine import (
    EngineRule,
    create_award_quote,
    evaluate_award_quote,
    required_send,
)
from shared.services.point_wallet_service import (
    create_account,
    create_hotel_voucher,
    create_ledger_transaction,
    create_program,
    create_purchase_offer,
    create_transfer_rule,
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
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return session_factory()


def seed_hand_computed_wallet():
    session = make_session()
    wanlitong = create_program(session, name="平安萬里通", kind="bank")
    marriott = create_program(session, name="Marriott Bonvoy", kind="hotel")
    airline = create_program(session, name="Aeroplan", kind="airline")
    kent_source = create_account(session, owner="kent", program_id=wanlitong.id)
    create_account(session, owner="wife", program_id=wanlitong.id)
    create_account(session, owner="kent", program_id=airline.id)
    create_ledger_transaction(
        session,
        account_id=kent_source.id,
        kind="buy",
        quantity=Decimal("100000"),
        occurred_at=date(2026, 7, 1),
        cost_total=Decimal("10000"),
        cost_currency="TWD",
        create_lot=True,
    )
    create_ledger_transaction(
        session,
        account_id=kent_source.id,
        kind="buy",
        quantity=Decimal("10000"),
        occurred_at=date(2026, 7, 2),
        cost_total=Decimal("2000"),
        cost_currency="TWD",
        create_lot=True,
    )
    create_transfer_rule(
        session,
        from_program_id=wanlitong.id,
        to_program_id=marriott.id,
        ratio_from=Decimal("1"),
        ratio_to=Decimal("1"),
        valid_from=date(2026, 1, 1),
        valid_until=date(2026, 12, 31),
    )
    create_transfer_rule(
        session,
        from_program_id=marriott.id,
        to_program_id=airline.id,
        ratio_from=Decimal("3"),
        ratio_to=Decimal("1"),
        valid_from=date(2026, 1, 1),
        valid_until=date(2026, 12, 31),
        rule_kind="threshold_block",
        block_size=Decimal("60000"),
        block_bonus_points=Decimal("5000"),
    )
    create_purchase_offer(
        session,
        program_id=wanlitong.id,
        kind="official",
        base_price=Decimal("0.30"),
        currency="TWD",
        bonus_pct=Decimal("0"),
        start_date=date(2026, 1, 1),
        paid_amount=Decimal("20000"),
        fees=Decimal("1000"),
        rebate=Decimal("1000"),
        points_received=Decimal("100000"),
    )
    create_purchase_offer(
        session,
        program_id=airline.id,
        kind="official",
        base_price=Decimal("0.50"),
        currency="TWD",
        bonus_pct=Decimal("25"),
        start_date=date(2026, 1, 1),
    )
    quote = create_award_quote(
        session,
        origin="TPE",
        destination="TYO",
        travel_date=date(2026, 10, 1),
        cabin="商務艙",
        pax=1,
        program_id=airline.id,
        miles_required=Decimal("30000"),
        taxes_amount=Decimal("1000"),
        taxes_currency="TWD",
        cash_price_twd=Decimal("50000"),
    )
    return session, quote.id


def lot_snapshot(session):
    return [
        (lot.id, lot.account_id, lot.remaining_quantity, lot.total_cost_twd, lot.cost_per_point_twd, lot.acquired_at)
        for lot in list_cost_lots(session)
    ]


def voucher_snapshot(session):
    return [
        (voucher.id, voucher.owner, voucher.program_id, voucher.face_value_points, voucher.expires_at, voucher.status, voucher.used_note)
        for voucher in list_hotel_vouchers(session)
    ]


def test_hand_computed_award_scenarios_and_read_only_lots():
    session, quote_id = seed_hand_computed_wallet()
    before = lot_snapshot(session)

    scenarios = evaluate_award_quote(session, quote_id, evaluation_date=date(2026, 7, 7))

    after = lot_snapshot(session)
    assert after == before
    expected = [
        {
            "rank": 1,
            "owner": "kent",
            "method": "transfer_chain",
            "total_cash_cost_twd": Decimal("8500.00"),
            "effective_cpp": Decimal("0.283333"),
            "points_acquired": Decimal("30000.00"),
            "points_consumed": Decimal("75000.00"),
            "points_leftover": Decimal("0.00"),
        },
        {
            "rank": 2,
            "owner": "kent",
            "method": "purchase_official",
            "total_cash_cost_twd": Decimal("13000.00"),
            "effective_cpp": Decimal("0.433333"),
            "points_acquired": Decimal("30000.00"),
            "points_consumed": Decimal("30000.00"),
            "points_leftover": Decimal("0.00"),
        },
        {
            "rank": 3,
            "owner": "wife",
            "method": "purchase_official",
            "total_cash_cost_twd": Decimal("13000.00"),
            "effective_cpp": Decimal("0.433333"),
            "points_acquired": Decimal("30000.00"),
            "points_consumed": Decimal("30000.00"),
            "points_leftover": Decimal("0.00"),
        },
        {
            "rank": 4,
            "owner": "kent",
            "method": "transfer_chain",
            "total_cash_cost_twd": Decimal("16000.00"),
            "effective_cpp": Decimal("0.533333"),
            "points_acquired": Decimal("30000.00"),
            "points_consumed": Decimal("75000.00"),
            "points_leftover": Decimal("0.00"),
        },
        {
            "rank": 5,
            "owner": "wife",
            "method": "transfer_chain",
            "total_cash_cost_twd": Decimal("16000.00"),
            "effective_cpp": Decimal("0.533333"),
            "points_acquired": Decimal("30000.00"),
            "points_consumed": Decimal("75000.00"),
            "points_leftover": Decimal("0.00"),
        },
        {
            "rank": 6,
            "owner": "cash",
            "method": "cash",
            "total_cash_cost_twd": Decimal("50000.00"),
            "effective_cpp": None,
            "points_acquired": Decimal("0.00"),
            "points_consumed": Decimal("0.00"),
            "points_leftover": Decimal("0.00"),
        },
    ]
    actual = [
        {
            "rank": row.rank,
            "owner": row.owner,
            "method": row.method,
            "total_cash_cost_twd": row.total_cash_cost_twd,
            "effective_cpp": row.effective_cpp,
            "points_acquired": row.points_acquired,
            "points_consumed": row.points_consumed,
            "points_leftover": row.points_leftover,
        }
        for row in scenarios
    ]
    assert actual == expected
    best_path = json.loads(scenarios[0].path_json)
    assert best_path["hops"][1]["sent"] == "75000.00"
    assert best_path["hops"][1]["received"] == "30000.00"


def test_threshold_block_marriott_rule_requires_exactly_75000_points():
    rule = EngineRule(
        id=1,
        from_program_id=1,
        to_program_id=2,
        ratio_from=Decimal("3"),
        ratio_to=Decimal("1"),
        bonus_pct=Decimal("0"),
        min_transfer=None,
        valid_from=date(2026, 1, 1),
        valid_until=None,
        rule_kind="threshold_block",
        block_size=Decimal("60000"),
        block_bonus_points=Decimal("5000"),
    )

    assert required_send(rule, Decimal("30000")) == Decimal("75000.00")


def test_gap_fill_uses_existing_18911_and_fills_6089_at_35_to_1_read_only():
    session = make_session()
    wanlitong = create_program(session, name="平安萬里通", kind="bank")
    qatar = create_program(session, name="Qatar Avios", kind="airline")
    source = create_account(session, owner="kent", program_id=wanlitong.id)
    target = create_account(session, owner="kent", program_id=qatar.id)
    create_ledger_transaction(
        session,
        account_id=source.id,
        kind="buy",
        quantity=Decimal("300000"),
        occurred_at=date(2026, 7, 1),
        cost_total=Decimal("3000"),
        cost_currency="TWD",
        create_lot=True,
    )
    create_ledger_transaction(
        session,
        account_id=target.id,
        kind="earn",
        quantity=Decimal("18911"),
        occurred_at=date(2026, 7, 1),
        note="legacy balance without cost basis",
    )
    create_transfer_rule(
        session,
        from_program_id=wanlitong.id,
        to_program_id=qatar.id,
        ratio_from=Decimal("35"),
        ratio_to=Decimal("1"),
        valid_from=date(2026, 1, 1),
    )
    create_hotel_voucher(
        session,
        owner="kent",
        program_id=qatar.id,
        face_value_points=Decimal("50000"),
        expires_at=date(2026, 8, 28),
    )
    quote = create_award_quote(
        session,
        origin="TPE",
        destination="DOH",
        program_id=qatar.id,
        miles_required=Decimal("25000"),
        cash_price_twd=Decimal("100000"),
    )
    before_lots = lot_snapshot(session)
    before_vouchers = voucher_snapshot(session)

    scenarios = evaluate_award_quote(session, quote.id, evaluation_date=date(2026, 7, 7))

    assert lot_snapshot(session) == before_lots
    assert voucher_snapshot(session) == before_vouchers
    gap = next(row for row in scenarios if row.method == "gap_fill")
    path = json.loads(gap.path_json)
    assert path["existing"]["points"] == "18911.00"
    assert path["fill"]["gap_points"] == "6089.00"
    assert path["fill"]["path"]["hops"][0]["sent"] == "213115.00"
    assert path["fill"]["path"]["hops"][0]["received"] == "6089.00"
    assert gap.true_cost_twd == Decimal("2131.15")
    assert gap.points_acquired == Decimal("25000.00")
    assert gap.points_consumed == Decimal("232026.00")
    assert "部分無成本基礎" in (gap.warnings or "")


def test_gap_fill_is_not_emitted_for_zero_or_sufficient_existing_balance():
    session = make_session()
    wanlitong = create_program(session, name="平安萬里通", kind="bank")
    qatar = create_program(session, name="Qatar Avios", kind="airline")
    source = create_account(session, owner="kent", program_id=wanlitong.id)
    target = create_account(session, owner="kent", program_id=qatar.id)
    create_ledger_transaction(
        session,
        account_id=source.id,
        kind="buy",
        quantity=Decimal("300000"),
        occurred_at=date(2026, 7, 1),
        cost_total=Decimal("3000"),
        cost_currency="TWD",
        create_lot=True,
    )
    create_transfer_rule(session, from_program_id=wanlitong.id, to_program_id=qatar.id, ratio_from=Decimal("35"), ratio_to=Decimal("1"), valid_from=date(2026, 1, 1))
    zero_quote = create_award_quote(session, program_id=qatar.id, miles_required=Decimal("25000"))
    zero_scenarios = evaluate_award_quote(session, zero_quote.id, evaluation_date=date(2026, 7, 7))
    create_ledger_transaction(session, account_id=target.id, kind="earn", quantity=Decimal("26000"), occurred_at=date(2026, 7, 2))
    sufficient_quote = create_award_quote(session, program_id=qatar.id, miles_required=Decimal("25000"))
    sufficient_scenarios = evaluate_award_quote(session, sufficient_quote.id, evaluation_date=date(2026, 7, 7))

    assert "gap_fill" not in {row.method for row in zero_scenarios}
    assert "gap_fill" not in {row.method for row in sufficient_scenarios}


def test_infeasible_balance_and_expired_rules_are_excluded():
    session, quote_id = seed_hand_computed_wallet()
    scenarios = evaluate_award_quote(session, quote_id, evaluation_date=date(2027, 1, 1))

    assert [row.method for row in scenarios] == ["purchase_official", "purchase_official", "cash"]
    assert all(row.owner != "kent" or row.method != "existing" for row in scenarios)


def test_min_transfer_rounding_is_applied():
    rule = EngineRule(
        id=1,
        from_program_id=1,
        to_program_id=2,
        ratio_from=Decimal("1000"),
        ratio_to=Decimal("500"),
        bonus_pct=Decimal("0"),
        min_transfer=Decimal("5000"),
        valid_from=date(2026, 1, 1),
        valid_until=None,
        rule_kind="linear",
        block_size=None,
        block_bonus_points=None,
    )

    assert required_send(rule, Decimal("501")) == Decimal("5000.00")


def test_missing_fx_warning_is_carried_without_crashing():
    session, quote_id = seed_hand_computed_wallet()
    quote = session.get(point_wallet.AwardQuote, quote_id)
    quote.taxes_currency = "XYZ"
    session.add(FxRate(currency="TWD", twd_per_unit=Decimal("1"), as_of=date(2026, 7, 7), source="test"))
    session.commit()

    scenarios = evaluate_award_quote(session, quote_id, evaluation_date=date(2026, 7, 7))

    assert scenarios[0].warnings == "missing fx rate: XYZ"
