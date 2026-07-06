from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from urllib.request import urlopen

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from shared.models.point_wallet import FxRate


FALLBACK_TWD_RATES: dict[str, Decimal] = {
    "TWD": Decimal("1"),
    "CNY": Decimal("4.35"),
    "USD": Decimal("31.5"),
    "JPY": Decimal("0.21"),
    "EUR": Decimal("34"),
    "GBP": Decimal("40"),
    "HKD": Decimal("4.03"),
    "CAD": Decimal("23"),
    "AUD": Decimal("20.6"),
}


def refresh_fx_rates(session: Session, *, as_of: date | None = None) -> dict[str, str]:
    as_of = as_of or date.today()
    try:
        rates = _fetch_open_er_api_rates()
        source = "open.er-api.com"
    except Exception:
        rates = FALLBACK_TWD_RATES
        source = "fallback"
    created = 0
    for currency, twd_per_unit in rates.items():
        existing = session.scalar(select(FxRate).where(FxRate.currency == currency, FxRate.as_of == as_of))
        if existing is not None:
            continue
        session.add(FxRate(currency=currency, twd_per_unit=twd_per_unit, as_of=as_of, source=source))
        created += 1
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise
    return {"source": source, "created": str(created)}


def get_twd_per_unit(session: Session, currency: str, *, as_of: date | None = None) -> Decimal:
    normalized = currency.upper()
    statement = select(FxRate).where(FxRate.currency == normalized).order_by(FxRate.as_of.desc(), FxRate.id.desc())
    if as_of is not None:
        statement = statement.where(FxRate.as_of <= as_of)
    row = session.scalar(statement)
    if row is not None:
        return row.twd_per_unit
    return FALLBACK_TWD_RATES.get(normalized, Decimal("1"))


def list_fx_rates(session: Session) -> list[FxRate]:
    return list(session.scalars(select(FxRate).order_by(FxRate.currency, FxRate.as_of.desc())))


def _fetch_open_er_api_rates() -> dict[str, Decimal]:
    with urlopen("https://open.er-api.com/v6/latest/TWD", timeout=8) as response:
        payload = json.loads(response.read().decode("utf-8"))
    raw_rates = payload.get("rates") or {}
    converted = {
        currency: (Decimal("1") / Decimal(str(value))).quantize(Decimal("0.000001"))
        for currency, value in raw_rates.items()
        if value
    }
    converted["TWD"] = Decimal("1")
    return converted
