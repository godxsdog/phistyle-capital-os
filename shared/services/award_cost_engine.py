from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.models.point_wallet import (
    AwardQuote,
    CostLot,
    FundingScenario,
    FxRate,
    LedgerTransaction,
    PointAccount,
    PointProgram,
    PurchaseOffer,
    TransferRule,
)
from shared.services.exchange_rate_service import FALLBACK_TWD_RATES, get_twd_per_unit
from shared.services.point_wallet_service import PointWalletError, PointWalletNotFoundError


MAX_SCENARIOS_PER_QUOTE = 200
VALID_OFFER_KINDS = {"official", "promo", "third_party"}


@dataclass(frozen=True)
class EngineLot:
    id: int
    account_id: int
    remaining_quantity: Decimal
    total_cost_twd: Decimal
    acquired_at: date


@dataclass(frozen=True)
class EngineAccount:
    id: int
    owner: str
    program_id: int
    balance: Decimal
    lots: tuple[EngineLot, ...]


@dataclass(frozen=True)
class EngineRule:
    id: int
    from_program_id: int
    to_program_id: int
    ratio_from: Decimal
    ratio_to: Decimal
    bonus_pct: Decimal
    min_transfer: Decimal | None
    valid_from: date
    valid_until: date | None
    rule_kind: str
    block_size: Decimal | None
    block_bonus_points: Decimal | None


@dataclass(frozen=True)
class EngineOffer:
    id: int
    program_id: int
    kind: str
    base_price: Decimal
    currency: str
    bonus_pct: Decimal
    min_points: Decimal | None
    max_points: Decimal | None
    effective_cpp: Decimal
    start_date: date
    end_date: date | None
    paid_amount: Decimal | None
    fees: Decimal | None
    rebate: Decimal | None
    points_received: Decimal | None


@dataclass(frozen=True)
class EngineQuote:
    id: int
    program_id: int
    miles_required: Decimal
    taxes_amount: Decimal | None
    taxes_currency: str | None
    cash_price_twd: Decimal | None


@dataclass(frozen=True)
class EngineScenario:
    owner: str
    method: str
    path: dict[str, Any]
    true_cost_twd: Decimal
    saving_vs_cash_twd: Decimal | None
    warnings: tuple[str, ...]
    effective_cpp: Decimal | None
    total_cash_cost_twd: Decimal
    points_acquired: Decimal
    points_consumed: Decimal
    points_leftover: Decimal
    rank: int = 0


def create_award_quote(
    session: Session,
    *,
    origin: str | None = None,
    destination: str | None = None,
    travel_date: date | None = None,
    cabin: str | None = None,
    pax: int = 1,
    program_id: int,
    miles_required: Decimal,
    taxes_amount: Decimal | None = None,
    taxes_currency: str | None = None,
    cash_price_twd: Decimal | None = None,
    source: str = "manual",
) -> AwardQuote:
    if pax < 1:
        raise PointWalletError("pax must be at least 1")
    if miles_required <= 0:
        raise PointWalletError("miles_required must be positive")
    if session.get(PointProgram, program_id) is None:
        raise PointWalletNotFoundError(f"Unknown program_id: {program_id}")
    row = AwardQuote(
        origin=origin,
        destination=destination,
        travel_date=travel_date,
        cabin=cabin,
        pax=pax,
        program_id=program_id,
        miles_required=miles_required,
        taxes_amount=taxes_amount,
        taxes_currency=taxes_currency.upper() if taxes_currency else None,
        cash_price_twd=cash_price_twd,
        source=source,
        created_at=datetime.now(UTC),
    )
    session.add(row)
    session.commit()
    return row


def list_award_quotes(session: Session) -> list[AwardQuote]:
    return list(session.scalars(select(AwardQuote).order_by(AwardQuote.created_at.desc(), AwardQuote.id.desc())))


def get_award_quote(session: Session, quote_id: int) -> AwardQuote:
    row = session.get(AwardQuote, quote_id)
    if row is None:
        raise PointWalletNotFoundError(f"Unknown award_quote_id: {quote_id}")
    return row


def list_funding_scenarios(session: Session, quote_id: int) -> list[FundingScenario]:
    return list(
        session.scalars(
            select(FundingScenario)
            .where(FundingScenario.award_quote_id == quote_id)
            .order_by(FundingScenario.evaluated_at.desc(), FundingScenario.rank, FundingScenario.id)
        )
    )


def evaluate_award_quote(session: Session, quote_id: int, *, evaluation_date: date | None = None) -> list[FundingScenario]:
    quote_row = get_award_quote(session, quote_id)
    evaluation_date = evaluation_date or date.today()
    scenarios = evaluate_award_quote_data(
        quote=_quote_from_row(quote_row),
        accounts=_accounts_from_session(session),
        rules=_active_rules(session, evaluation_date),
        offers=_active_offers(session, evaluation_date),
        tax_twd=_tax_twd(session, quote_row, evaluation_date),
        program_names={program.id: program.name for program in session.scalars(select(PointProgram))},
        owners=_owners_from_session(session),
    )
    evaluated_at = datetime.now(UTC)
    rows: list[FundingScenario] = []
    for scenario in scenarios:
        row = FundingScenario(
            award_quote_id=quote_row.id,
            evaluated_at=evaluated_at,
            owner=scenario.owner,
            method=scenario.method,
            path_json=json.dumps(scenario.path, ensure_ascii=False, sort_keys=True, default=str),
            true_cost_twd=scenario.true_cost_twd,
            saving_vs_cash_twd=scenario.saving_vs_cash_twd,
            rank=scenario.rank,
            warnings="; ".join(scenario.warnings) if scenario.warnings else None,
            effective_cpp=scenario.effective_cpp,
            total_cash_cost_twd=scenario.total_cash_cost_twd,
            points_acquired=scenario.points_acquired,
            points_consumed=scenario.points_consumed,
            points_leftover=scenario.points_leftover,
        )
        session.add(row)
        rows.append(row)
    session.commit()
    return rows


def evaluate_award_quote_data(
    *,
    quote: EngineQuote,
    accounts: tuple[EngineAccount, ...],
    rules: tuple[EngineRule, ...],
    offers: tuple[EngineOffer, ...],
    tax_twd: tuple[Decimal, tuple[str, ...]],
    program_names: dict[int, str] | None = None,
    owners: tuple[str, ...] = ("kent", "wife"),
    include_gap_fill: bool = True,
) -> list[EngineScenario]:
    program_names = program_names or {}
    taxes_twd, tax_warnings = tax_twd
    scenarios: list[EngineScenario] = []
    target_accounts = [account for account in accounts if account.program_id == quote.program_id]

    for account in target_accounts:
        if account.balance < quote.miles_required:
            continue
        lot_cost, lots, partial = simulate_fifo(account.lots, quote.miles_required)
        warnings = list(tax_warnings)
        if partial:
            warnings.append("partial cost basis")
        points_cost = _money(lot_cost)
        scenarios.append(
            _scenario(
                owner=account.owner,
                method="existing",
                path={
                    "program_id": quote.program_id,
                    "program_name": program_names.get(quote.program_id, str(quote.program_id)),
                    "lots_consumed": lots,
                },
                points_cost_twd=points_cost,
                taxes_twd=taxes_twd,
                cash_price_twd=quote.cash_price_twd,
                warnings=tuple(warnings),
                points_acquired=quote.miles_required,
                points_consumed=quote.miles_required,
                points_leftover=Decimal("0"),
            )
        )

    chains = _chains_to_target(rules, quote.program_id)
    for chain in chains:
        required_source, hop_details = required_source_points(chain, quote.miles_required, program_names)
        source_program_id = chain[0].from_program_id
        for account in accounts:
            if account.program_id != source_program_id or account.balance < required_source:
                continue
            lot_cost, lots, partial = simulate_fifo(account.lots, required_source)
            warnings = list(tax_warnings)
            if partial:
                warnings.append("partial cost basis")
            scenarios.append(
                _scenario(
                    owner=account.owner,
                    method="transfer_chain",
                    path={"funding": "existing_points", "hops": hop_details, "lots_consumed": lots},
                    points_cost_twd=_money(lot_cost),
                    taxes_twd=taxes_twd,
                    cash_price_twd=quote.cash_price_twd,
                    warnings=tuple(warnings),
                    points_acquired=hop_details[-1]["received"],
                    points_consumed=required_source,
                    points_leftover=hop_details[-1]["received"] - quote.miles_required,
                )
            )
        for offer in [offer for offer in offers if offer.program_id == source_program_id and offer.kind in VALID_OFFER_KINDS]:
            source_cost = purchase_cost_twd(offer, required_source)
            if source_cost is None:
                continue
            for owner in owners:
                scenarios.append(
                    _scenario(
                        owner=owner,
                        method="transfer_chain",
                        path={
                            "funding": "same_day_source_purchase",
                            "purchase_offer_id": offer.id,
                            "source_program_id": source_program_id,
                            "hops": hop_details,
                        },
                        points_cost_twd=source_cost,
                        taxes_twd=taxes_twd,
                        cash_price_twd=quote.cash_price_twd,
                        warnings=tax_warnings,
                        points_acquired=hop_details[-1]["received"],
                        points_consumed=required_source,
                        points_leftover=hop_details[-1]["received"] - quote.miles_required,
                    )
                )

    for offer in [offer for offer in offers if offer.program_id == quote.program_id and offer.kind in VALID_OFFER_KINDS]:
        cost = purchase_cost_twd(offer, quote.miles_required)
        if cost is None:
            continue
        method = "purchase_third_party" if offer.kind == "third_party" else "purchase_official"
        for owner in owners:
            scenarios.append(
                _scenario(
                    owner=owner,
                    method=method,
                    path={"purchase_offer_id": offer.id, "program_id": offer.program_id, "kind": offer.kind},
                    points_cost_twd=cost,
                    taxes_twd=taxes_twd,
                    cash_price_twd=quote.cash_price_twd,
                    warnings=tax_warnings,
                    points_acquired=quote.miles_required,
                    points_consumed=quote.miles_required,
                    points_leftover=Decimal("0"),
                )
            )

    if include_gap_fill:
        scenarios.extend(
            _gap_fill_scenarios(
                quote=quote,
                accounts=accounts,
                rules=rules,
                offers=offers,
                taxes_twd=taxes_twd,
                tax_warnings=tax_warnings,
                cash_price_twd=quote.cash_price_twd,
                program_names=program_names,
            )
        )

    if quote.cash_price_twd is not None:
        scenarios.append(
            _scenario(
                owner="cash",
                method="cash",
                path={"cash_price_twd": str(_money(quote.cash_price_twd))},
                points_cost_twd=_money(quote.cash_price_twd),
                taxes_twd=Decimal("0"),
                cash_price_twd=quote.cash_price_twd,
                warnings=(),
                points_acquired=Decimal("0"),
                points_consumed=Decimal("0"),
                points_leftover=Decimal("0"),
            )
        )

    if len(scenarios) > MAX_SCENARIOS_PER_QUOTE:
        raise PointWalletError("Award cost evaluation produced more than 200 scenarios")
    ranked = sorted(scenarios, key=lambda item: (item.total_cash_cost_twd, item.method, item.owner))
    return [EngineScenario(**{**scenario.__dict__, "rank": index + 1}) for index, scenario in enumerate(ranked)]


def _gap_fill_scenarios(
    *,
    quote: EngineQuote,
    accounts: tuple[EngineAccount, ...],
    rules: tuple[EngineRule, ...],
    offers: tuple[EngineOffer, ...],
    taxes_twd: Decimal,
    tax_warnings: tuple[str, ...],
    cash_price_twd: Decimal | None,
    program_names: dict[int, str],
) -> list[EngineScenario]:
    rows: list[EngineScenario] = []
    for account in [item for item in accounts if item.program_id == quote.program_id and Decimal("0") < item.balance < quote.miles_required]:
        existing_cost, existing_lots, partial = simulate_fifo(account.lots, account.balance)
        gap = quote.miles_required - account.balance
        fill_accounts = tuple(
            EngineAccount(
                id=item.id,
                owner=item.owner,
                program_id=item.program_id,
                balance=Decimal("0") if item.id == account.id else item.balance,
                lots=() if item.id == account.id else item.lots,
            )
            for item in accounts
            if item.owner == account.owner
        )
        fill_scenarios = evaluate_award_quote_data(
            quote=EngineQuote(
                id=quote.id,
                program_id=quote.program_id,
                miles_required=gap,
                taxes_amount=None,
                taxes_currency=None,
                cash_price_twd=None,
            ),
            accounts=fill_accounts,
            rules=rules,
            offers=offers,
            tax_twd=(Decimal("0"), ()),
            program_names=program_names,
            owners=(account.owner,),
            include_gap_fill=False,
        )
        for fill in [item for item in fill_scenarios if item.method != "cash"]:
            warnings = list(tax_warnings)
            if partial:
                warnings.append("部分無成本基礎")
            warnings.extend(fill.warnings)
            points_cost = _money(existing_cost + fill.total_cash_cost_twd)
            rows.append(
                _scenario(
                    owner=account.owner,
                    method="gap_fill",
                    path={
                        "existing": {
                            "program_id": quote.program_id,
                            "program_name": program_names.get(quote.program_id, str(quote.program_id)),
                            "points": _points(account.balance),
                            "lots_consumed": existing_lots,
                        },
                        "fill": {
                            "gap_points": _points(gap),
                            "method": fill.method,
                            "path": fill.path,
                        },
                    },
                    points_cost_twd=points_cost,
                    taxes_twd=taxes_twd,
                    cash_price_twd=cash_price_twd,
                    warnings=tuple(warnings),
                    points_acquired=quote.miles_required,
                    points_consumed=account.balance + fill.points_consumed,
                    points_leftover=fill.points_leftover,
                )
            )
    return rows


def simulate_fifo(lots: tuple[EngineLot, ...], required: Decimal) -> tuple[Decimal, list[dict[str, str | int]], bool]:
    remaining = required
    cost = Decimal("0")
    consumed: list[dict[str, str | int]] = []
    for lot in sorted(lots, key=lambda item: (item.acquired_at, item.id)):
        if remaining <= 0:
            break
        take = min(lot.remaining_quantity, remaining)
        if take <= 0:
            continue
        lot_cost = (lot.total_cost_twd * take / lot.remaining_quantity).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        cost += lot_cost
        consumed.append({"lot_id": lot.id, "qty": str(_points(take)), "cost_twd": str(lot_cost)})
        remaining -= take
    return cost, consumed, remaining > 0


def required_source_points(chain: tuple[EngineRule, ...], required_final: Decimal, program_names: dict[int, str] | None = None) -> tuple[Decimal, list[dict[str, Any]]]:
    program_names = program_names or {}
    required = required_final
    reversed_details: list[dict[str, Any]] = []
    for rule in reversed(chain):
        sent = required_send(rule, required)
        received = transfer_received(rule, sent)
        reversed_details.append(
            {
                "rule_id": rule.id,
                "from_program_id": rule.from_program_id,
                "from_program_name": program_names.get(rule.from_program_id, str(rule.from_program_id)),
                "to_program_id": rule.to_program_id,
                "to_program_name": program_names.get(rule.to_program_id, str(rule.to_program_id)),
                "sent": _points(sent),
                "received": _points(received),
                "bonus_pct": str(rule.bonus_pct),
                "rule_kind": rule.rule_kind,
            }
        )
        required = sent
    return required, list(reversed(reversed_details))


def required_send(rule: EngineRule, required_received: Decimal) -> Decimal:
    minimum = max(rule.ratio_from, rule.min_transfer or Decimal("0"))
    candidate = _ceil_to_multiple(minimum, rule.ratio_from)
    rough = required_received * rule.ratio_from / max(rule.ratio_to, Decimal("1"))
    candidate = max(candidate, _ceil_to_multiple(rough * Decimal("0.8"), rule.ratio_from))
    while transfer_received(rule, candidate) < required_received:
        candidate += rule.ratio_from
    while candidate - rule.ratio_from >= minimum and transfer_received(rule, candidate - rule.ratio_from) >= required_received:
        candidate -= rule.ratio_from
    return _points(candidate)


def transfer_received(rule: EngineRule, sent: Decimal) -> Decimal:
    base = (sent * rule.ratio_to / rule.ratio_from).to_integral_value(rounding=ROUND_FLOOR)
    if rule.rule_kind == "threshold_block":
        block_bonus = Decimal("0")
        if rule.block_size and rule.block_bonus_points:
            blocks = (sent / rule.block_size).to_integral_value(rounding=ROUND_FLOOR)
            block_bonus = blocks * rule.block_bonus_points
        return _points(base + block_bonus)
    multiplier = Decimal("1") + (rule.bonus_pct / Decimal("100"))
    return _points((base * multiplier).to_integral_value(rounding=ROUND_FLOOR))


def purchase_cost_twd(offer: EngineOffer, points_needed: Decimal) -> Decimal | None:
    if offer.min_points is not None and points_needed < offer.min_points:
        return None
    if offer.max_points is not None and points_needed > offer.max_points:
        return None
    return _money(offer.effective_cpp * points_needed)


def _scenario(
    *,
    owner: str,
    method: str,
    path: dict[str, Any],
    points_cost_twd: Decimal,
    taxes_twd: Decimal,
    cash_price_twd: Decimal | None,
    warnings: tuple[str, ...],
    points_acquired: Decimal,
    points_consumed: Decimal,
    points_leftover: Decimal,
) -> EngineScenario:
    total = _money(points_cost_twd + taxes_twd)
    saving = _money(cash_price_twd - total) if cash_price_twd is not None else None
    effective_cpp = (total / points_acquired).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP) if points_acquired > 0 else None
    return EngineScenario(
        owner=owner,
        method=method,
        path=path,
        true_cost_twd=total,
        saving_vs_cash_twd=saving,
        warnings=warnings,
        effective_cpp=effective_cpp,
        total_cash_cost_twd=total,
        points_acquired=_points(points_acquired),
        points_consumed=_points(points_consumed),
        points_leftover=_points(points_leftover),
    )


def _chains_to_target(rules: tuple[EngineRule, ...], target_program_id: int) -> list[tuple[EngineRule, ...]]:
    one_hop = [(rule,) for rule in rules if rule.to_program_id == target_program_id]
    two_hop = [
        (first, second)
        for second in rules
        if second.to_program_id == target_program_id
        for first in rules
        if first.to_program_id == second.from_program_id and first.from_program_id != target_program_id
    ]
    return one_hop + two_hop


def _quote_from_row(row: AwardQuote) -> EngineQuote:
    return EngineQuote(
        id=row.id,
        program_id=row.program_id,
        miles_required=row.miles_required,
        taxes_amount=row.taxes_amount,
        taxes_currency=row.taxes_currency,
        cash_price_twd=row.cash_price_twd,
    )


def _accounts_from_session(session: Session) -> tuple[EngineAccount, ...]:
    accounts: list[EngineAccount] = []
    for account in session.scalars(select(PointAccount).order_by(PointAccount.owner, PointAccount.id)):
        balance = sum(
            session.scalars(select(LedgerTransaction.quantity).where(LedgerTransaction.account_id == account.id)),
            Decimal("0"),
        )
        lots = tuple(
            EngineLot(
                id=lot.id,
                account_id=lot.account_id,
                remaining_quantity=lot.remaining_quantity,
                total_cost_twd=lot.total_cost_twd,
                acquired_at=lot.acquired_at,
            )
            for lot in session.scalars(
                select(CostLot)
                .where(CostLot.account_id == account.id, CostLot.remaining_quantity > 0)
                .order_by(CostLot.acquired_at, CostLot.id)
            )
        )
        accounts.append(EngineAccount(id=account.id, owner=account.owner, program_id=account.program_id, balance=balance, lots=lots))
    return tuple(accounts)


def _active_rules(session: Session, evaluation_date: date) -> tuple[EngineRule, ...]:
    rows = session.scalars(
        select(TransferRule).where(
            TransferRule.valid_from <= evaluation_date,
            (TransferRule.valid_until.is_(None)) | (TransferRule.valid_until >= evaluation_date),
        )
    )
    return tuple(
        EngineRule(
            id=row.id,
            from_program_id=row.from_program_id,
            to_program_id=row.to_program_id,
            ratio_from=row.ratio_from,
            ratio_to=row.ratio_to,
            bonus_pct=row.bonus_pct,
            min_transfer=row.min_transfer,
            valid_from=row.valid_from,
            valid_until=row.valid_until,
            rule_kind=row.rule_kind,
            block_size=row.block_size,
            block_bonus_points=row.block_bonus_points,
        )
        for row in rows
    )


def _active_offers(session: Session, evaluation_date: date) -> tuple[EngineOffer, ...]:
    rows = session.scalars(
        select(PurchaseOffer).where(
            PurchaseOffer.start_date <= evaluation_date,
            (PurchaseOffer.end_date.is_(None)) | (PurchaseOffer.end_date >= evaluation_date),
        )
    )
    return tuple(
        EngineOffer(
            id=row.id,
            program_id=row.program_id,
            kind=row.kind,
            base_price=row.base_price,
            currency=row.currency,
            bonus_pct=row.bonus_pct,
            min_points=row.min_points,
            max_points=row.max_points,
            effective_cpp=_offer_effective_cpp_twd(session, row, evaluation_date),
            start_date=row.start_date,
            end_date=row.end_date,
            paid_amount=row.paid_amount,
            fees=row.fees,
            rebate=row.rebate,
            points_received=row.points_received,
        )
        for row in rows
    )


def _offer_effective_cpp_twd(session: Session, row: PurchaseOffer, evaluation_date: date) -> Decimal:
    if row.paid_amount is not None and row.fees is not None and row.rebate is not None and row.points_received and row.points_received > 0:
        cpp = (row.paid_amount + row.fees - row.rebate) / row.points_received
    else:
        cpp = row.effective_cpp
    return (cpp * get_twd_per_unit(session, row.currency, as_of=evaluation_date)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def _owners_from_session(session: Session) -> tuple[str, ...]:
    owners = tuple(sorted(set(session.scalars(select(PointAccount.owner)))))
    return owners or ("kent", "wife")


def _tax_twd(session: Session, quote: AwardQuote, evaluation_date: date) -> tuple[Decimal, tuple[str, ...]]:
    if quote.taxes_amount is None:
        return Decimal("0"), ()
    currency = (quote.taxes_currency or "TWD").upper()
    row = session.scalar(
        select(FxRate)
        .where(FxRate.currency == currency, FxRate.as_of <= evaluation_date)
        .order_by(FxRate.as_of.desc(), FxRate.id.desc())
    )
    if row is None and currency not in FALLBACK_TWD_RATES:
        return _money(quote.taxes_amount), (f"missing fx rate: {currency}",)
    return _money(quote.taxes_amount * get_twd_per_unit(session, currency, as_of=evaluation_date)), ()


def _ceil_to_multiple(value: Decimal, multiple: Decimal) -> Decimal:
    if multiple <= 0:
        return value
    return (value / multiple).to_integral_value(rounding=ROUND_CEILING) * multiple


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _points(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
