from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from html.parser import HTMLParser
from typing import Callable, Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from shared.models.market_data import IngestRun, InstitutionalPosition, MarketDailyBar, SettlementCalendar, WatchlistSymbol


TAIFEX_PRODUCTS = {"TX": "TX", "MTX": "MTX", "TMF": "TMF"}
TAIFEX_INSTITUTIONAL_IDS = {"TX": "TXF", "MTX": "MXF", "TMF": "TMF"}
IDENTITY_MAP = {
    "自營商": "dealer",
    "投信": "trust",
    "外資": "foreign",
    "外資及陸資": "foreign",
}


class MarketDataError(ValueError):
    pass


@dataclass(frozen=True)
class DailyBarInput:
    market: str
    symbol: str
    bar_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int | None
    open_interest: int | None
    source: str


@dataclass(frozen=True)
class InstitutionalPositionInput:
    trade_date: date
    product: str
    identity: str
    long_contracts: int
    short_contracts: int
    net_contracts: int


@dataclass(frozen=True)
class SettlementCalendarInput:
    product: str
    contract: str
    last_trading_date: date


@dataclass(frozen=True)
class IngestResult:
    source: str
    status: str
    inserted: int
    skipped: int
    warnings: list[str]


def create_watchlist_symbol(session: Session, market: str, symbol: str, active: bool = True) -> WatchlistSymbol:
    market = market.lower().strip()
    symbol = normalize_us_symbol(symbol) if market == "us" else symbol.strip().upper()
    if market not in {"us", "taifex"}:
        raise MarketDataError("market must be us or taifex")
    existing = session.scalars(
        select(WatchlistSymbol).where(WatchlistSymbol.market == market, WatchlistSymbol.symbol == symbol)
    ).first()
    if existing is not None:
        existing.active = active
        session.commit()
        session.refresh(existing)
        return existing
    row = WatchlistSymbol(market=market, symbol=symbol, active=active)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def list_watchlist_symbols(session: Session, market: str | None = None) -> list[WatchlistSymbol]:
    stmt: Select[tuple[WatchlistSymbol]] = select(WatchlistSymbol).order_by(WatchlistSymbol.market, WatchlistSymbol.symbol)
    if market:
        stmt = stmt.where(WatchlistSymbol.market == market.lower())
    return list(session.scalars(stmt))


def update_watchlist_symbol(session: Session, symbol_id: int, active: bool) -> WatchlistSymbol:
    row = session.get(WatchlistSymbol, symbol_id)
    if row is None:
        raise MarketDataError("watchlist symbol not found")
    row.active = active
    session.commit()
    session.refresh(row)
    return row


def delete_watchlist_symbol(session: Session, symbol_id: int) -> None:
    row = session.get(WatchlistSymbol, symbol_id)
    if row is None:
        raise MarketDataError("watchlist symbol not found")
    session.delete(row)
    session.commit()


def ingest_manual_bars(session: Session, source: str, bars: Iterable[DailyBarInput]) -> IngestResult:
    started_at = datetime.now(timezone.utc)
    warnings: list[str] = []
    inserted = 0
    skipped = 0
    for bar in bars:
        status = _insert_bar_if_new(session, bar)
        if status == "inserted":
            inserted += 1
        elif status == "same":
            skipped += 1
        else:
            skipped += 1
            warnings.append(status)
            _record_run(session, source, bar.bar_date, "correction_detected", status, started_at)
    detail = json.dumps({"inserted": inserted, "skipped": skipped, "warnings": warnings}, ensure_ascii=False)
    _record_run(session, source, date.today(), "success" if not warnings else "success_with_warnings", detail, started_at)
    session.commit()
    return IngestResult(source=source, status="success" if not warnings else "success_with_warnings", inserted=inserted, skipped=skipped, warnings=warnings)


def ingest_taifex(
    session: Session,
    start_date: date,
    end_date: date,
    fetcher: Callable[[str], bytes] | None = None,
) -> IngestResult:
    started_at = datetime.now(timezone.utc)
    fetcher = fetcher or fetch_url
    warnings: list[str] = []
    inserted = 0
    skipped = 0
    for product in TAIFEX_PRODUCTS:
        try:
            raw = fetcher(taifex_daily_url(product, start_date, end_date))
            bars, settlements = parse_taifex_daily_csv(raw)
            for bar in bars:
                status = _insert_bar_if_new(session, bar)
                if status == "inserted":
                    inserted += 1
                elif status == "same":
                    skipped += 1
                else:
                    skipped += 1
                    warnings.append(status)
                    _record_run(session, "taifex", bar.bar_date, "correction_detected", status, started_at)
            _insert_settlements_if_new(session, settlements)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"{product}: {exc}")
    _ingest_taifex_institutional(session, start_date, end_date, fetcher, warnings, started_at)
    quality_warnings = record_quality_checks(session, "taifex", source="taifex")
    warnings.extend(quality_warnings)
    status = "success" if not warnings else "success_with_warnings"
    _record_run(
        session,
        "taifex",
        end_date,
        status,
        json.dumps({"inserted": inserted, "skipped": skipped, "warnings": warnings}, ensure_ascii=False),
        started_at,
    )
    session.commit()
    return IngestResult(source="taifex", status=status, inserted=inserted, skipped=skipped, warnings=warnings)


def ingest_yahoo_us(
    session: Session,
    fetcher: Callable[[str], bytes] | None = None,
) -> IngestResult:
    started_at = datetime.now(timezone.utc)
    fetcher = fetcher or fetch_url
    warnings: list[str] = []
    inserted = 0
    skipped = 0
    symbols = [row.symbol for row in list_watchlist_symbols(session, "us") if row.active]
    for symbol in symbols:
        try:
            raw = fetcher(yahoo_chart_url(symbol))
            bars = parse_yahoo_chart_json(raw, symbol)
            for bar in bars:
                status = _insert_bar_if_new(session, bar)
                if status == "inserted":
                    inserted += 1
                elif status == "same":
                    skipped += 1
                else:
                    skipped += 1
                    warnings.append(status)
                    _record_run(session, "yahoo", bar.bar_date, "correction_detected", status, started_at)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"{symbol}: {exc}")
    quality_warnings = record_quality_checks(session, "us", source="yahoo")
    warnings.extend(quality_warnings)
    status = "success" if not warnings else "success_with_warnings"
    _record_run(
        session,
        "yahoo",
        date.today(),
        status,
        json.dumps({"symbols": symbols, "inserted": inserted, "skipped": skipped, "warnings": warnings}, ensure_ascii=False),
        started_at,
    )
    session.commit()
    return IngestResult(source="yahoo", status=status, inserted=inserted, skipped=skipped, warnings=warnings)


def market_sanity_summary(session: Session) -> list[dict[str, object]]:
    rows = session.execute(
        select(
            MarketDailyBar.market,
            MarketDailyBar.symbol,
            func.min(MarketDailyBar.bar_date),
            func.max(MarketDailyBar.bar_date),
            func.count(MarketDailyBar.id),
        )
        .group_by(MarketDailyBar.market, MarketDailyBar.symbol)
        .order_by(MarketDailyBar.market, MarketDailyBar.symbol)
    ).all()
    return [
        {
            "market": market,
            "symbol": symbol,
            "first_date": first_date.isoformat() if first_date else None,
            "last_date": last_date.isoformat() if last_date else None,
            "row_count": row_count,
            "gap_count": count_business_day_gaps(session, market, symbol),
            "note": "未復權，除權息日會有跳空" if market == "us" else None,
        }
        for market, symbol, first_date, last_date, row_count in rows
    ]


def list_ingest_runs(session: Session, limit: int = 50) -> list[IngestRun]:
    return list(session.scalars(select(IngestRun).order_by(IngestRun.started_at.desc()).limit(limit)))


def parse_yahoo_chart_json(raw: bytes | str, symbol: str) -> list[DailyBarInput]:
    payload = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
    chart = payload.get("chart", {})
    error = chart.get("error")
    if error:
        raise MarketDataError(str(error))
    results = chart.get("result") or []
    if not results:
        raise MarketDataError("Yahoo chart response has no result")
    result = results[0]
    timestamps = result.get("timestamp") or []
    quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    opens = quote.get("open") or []
    highs = quote.get("high") or []
    lows = quote.get("low") or []
    closes = quote.get("close") or []
    volumes = quote.get("volume") or []
    bars: list[DailyBarInput] = []
    normalized_symbol = normalize_us_symbol(symbol)
    for index, ts in enumerate(timestamps):
        values = [safe_decimal(opens, index), safe_decimal(highs, index), safe_decimal(lows, index), safe_decimal(closes, index)]
        if any(value is None for value in values):
            continue
        bars.append(
            DailyBarInput(
                market="us",
                symbol=normalized_symbol,
                bar_date=datetime.fromtimestamp(int(ts), tz=timezone.utc).date(),
                open=values[0],
                high=values[1],
                low=values[2],
                close=values[3],
                volume=safe_int(volumes, index),
                open_interest=None,
                source="yahoo",
            )
        )
    return bars


def parse_taifex_daily_csv(raw: bytes | str) -> tuple[list[DailyBarInput], list[SettlementCalendarInput]]:
    text = decode_taifex(raw)
    reader = csv.DictReader(io.StringIO(text))
    bars: list[DailyBarInput] = []
    settlements: dict[tuple[str, str], date] = {}
    for row in reader:
        product = (row.get("商品") or row.get("商品代號") or "").strip()
        if product not in TAIFEX_PRODUCTS:
            continue
        session_name = (row.get("交易時段") or "").strip()
        if session_name and session_name not in {"一般", "一般交易時段"}:
            continue
        contract = normalize_contract(row.get("到期月份(週別)") or row.get("到期月份") or "")
        bar_date = parse_date(row.get("交易日期") or "")
        bar = DailyBarInput(
            market="taifex",
            symbol=product,
            bar_date=bar_date,
            open=parse_decimal(row.get("開盤價")),
            high=parse_decimal(row.get("最高價")),
            low=parse_decimal(row.get("最低價")),
            close=parse_decimal(row.get("收盤價")),
            volume=parse_optional_int(row.get("成交量")),
            open_interest=parse_optional_int(row.get("未沖銷契約量")),
            source="taifex",
        )
        bars.append(bar)
        if contract:
            settlements[(product, contract)] = max(settlements.get((product, contract), bar_date), bar_date)
    settlement_rows = [
        SettlementCalendarInput(product=product, contract=contract, last_trading_date=last_date)
        for (product, contract), last_date in settlements.items()
        if re.fullmatch(r"\d{6}", contract)
    ]
    return bars, settlement_rows


def parse_taifex_institutional_html(raw: bytes | str, product: str, trade_date: date) -> list[InstitutionalPositionInput]:
    html = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw
    parser = SimpleTableParser()
    parser.feed(html)
    rows: list[InstitutionalPositionInput] = []
    for cells in parser.rows:
        compact = [normalize_cell(cell) for cell in cells]
        if len(compact) < 15:
            continue
        identity = map_identity(compact[2])
        if identity is None:
            continue
        long_contracts = parse_optional_int(compact[9])
        short_contracts = parse_optional_int(compact[11])
        net_contracts = parse_optional_int(compact[13])
        if long_contracts is None or short_contracts is None or net_contracts is None:
            continue
        rows.append(
            InstitutionalPositionInput(
                trade_date=trade_date,
                product=product,
                identity=identity,
                long_contracts=long_contracts,
                short_contracts=short_contracts,
                net_contracts=net_contracts,
            )
        )
    return rows


def fetch_url(url: str, data: bytes | None = None) -> bytes:
    request = Request(
        url,
        data=data,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X) AppleWebKit/537.36 Chrome Safari",
            "Accept": "application/json,text/csv,text/html,*/*",
        },
    )
    with urlopen(request, timeout=30) as response:
        return response.read()


def taifex_daily_url(product: str, start_date: date, end_date: date) -> str:
    query = urlencode(
        {
            "down_type": "1",
            "commodity_id": product,
            "queryStartDate": start_date.strftime("%Y/%m/%d"),
            "queryEndDate": end_date.strftime("%Y/%m/%d"),
        }
    )
    return f"https://www.taifex.com.tw/cht/3/futDataDown?{query}"


def yahoo_chart_url(symbol: str) -> str:
    return f"https://query1.finance.yahoo.com/v8/finance/chart/{normalize_us_symbol(symbol)}?range=10y&interval=1d"


def taifex_institutional_request(product: str, trade_date: date) -> tuple[str, bytes]:
    data = urlencode(
        {
            "queryDate": trade_date.strftime("%Y/%m/%d"),
            "commodityId": TAIFEX_INSTITUTIONAL_IDS[product],
            "queryType": "1",
            "goDay": "",
            "doQuery": "1",
            "dateaddcnt": "",
        }
    ).encode()
    return "https://www.taifex.com.tw/cht/3/futContractsDate", data


def normalize_us_symbol(symbol: str) -> str:
    return symbol.strip().upper().removesuffix(".US")


def decode_taifex(raw: bytes | str) -> str:
    if isinstance(raw, str):
        return raw
    for encoding in ("ms950", "big5", "utf-8-sig", "utf-8"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def parse_date(value: str) -> date:
    return datetime.strptime(value.strip(), "%Y/%m/%d").date()


def parse_decimal(value: str | None) -> Decimal:
    if value is None or value.strip() in {"", "-"}:
        raise MarketDataError("missing decimal value")
    return Decimal(value.replace(",", "").strip())


def parse_optional_int(value: str | None) -> int | None:
    if value is None:
        return None
    clean = value.replace(",", "").strip()
    if clean in {"", "-"}:
        return None
    return int(Decimal(clean))


def normalize_contract(value: str) -> str:
    clean = value.strip()
    match = re.match(r"(\d{6})", clean)
    return match.group(1) if match else ""


def safe_decimal(values: list[object], index: int) -> Decimal | None:
    try:
        value = values[index]
    except IndexError:
        return None
    if value is None:
        return None
    return Decimal(str(value))


def safe_int(values: list[object], index: int) -> int | None:
    try:
        value = values[index]
    except IndexError:
        return None
    if value is None:
        return None
    return int(value)


def _insert_bar_if_new(session: Session, bar: DailyBarInput) -> str:
    existing = session.scalars(
        select(MarketDailyBar).where(
            MarketDailyBar.market == bar.market,
            MarketDailyBar.symbol == bar.symbol,
            MarketDailyBar.bar_date == bar.bar_date,
        )
    ).first()
    if existing is None:
        session.add(MarketDailyBar(**bar.__dict__))
        return "inserted"
    existing_tuple = (
        existing.open,
        existing.high,
        existing.low,
        existing.close,
        existing.volume,
        existing.open_interest,
        existing.source,
    )
    next_tuple = (bar.open, bar.high, bar.low, bar.close, bar.volume, bar.open_interest, bar.source)
    if existing_tuple == next_tuple:
        return "same"
    return (
        f"{bar.symbol}/{bar.bar_date.isoformat()} correction detected: "
        f"old={existing_tuple} new={next_tuple}"
    )


def _insert_settlements_if_new(session: Session, rows: Iterable[SettlementCalendarInput]) -> None:
    for item in rows:
        existing = session.scalars(
            select(SettlementCalendar).where(SettlementCalendar.product == item.product, SettlementCalendar.contract == item.contract)
        ).first()
        if existing is None:
            session.add(SettlementCalendar(**item.__dict__))


def _insert_institutional_if_new(session: Session, rows: Iterable[InstitutionalPositionInput], warnings: list[str], source: str, started_at: datetime) -> None:
    for item in rows:
        existing = session.scalars(
            select(InstitutionalPosition).where(
                InstitutionalPosition.trade_date == item.trade_date,
                InstitutionalPosition.product == item.product,
                InstitutionalPosition.identity == item.identity,
            )
        ).first()
        if existing is None:
            session.add(InstitutionalPosition(**item.__dict__))
            continue
        existing_tuple = (existing.long_contracts, existing.short_contracts, existing.net_contracts)
        next_tuple = (item.long_contracts, item.short_contracts, item.net_contracts)
        if existing_tuple != next_tuple:
            warning = f"{item.product}/{item.trade_date.isoformat()}/{item.identity} correction detected: old={existing_tuple} new={next_tuple}"
            warnings.append(warning)
            _record_run(session, source, item.trade_date, "correction_detected", warning, started_at)


def _ingest_taifex_institutional(
    session: Session,
    start_date: date,
    end_date: date,
    fetcher: Callable[[str], bytes],
    warnings: list[str],
    started_at: datetime,
) -> None:
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:
            for product in TAIFEX_PRODUCTS:
                try:
                    url, data = taifex_institutional_request(product, current)
                    raw = fetch_url_with_body(url, data) if fetcher is fetch_url else fetcher(f"{url}?{data.decode()}")
                    rows = parse_taifex_institutional_html(raw, product, current)
                    _insert_institutional_if_new(session, rows, warnings, "taifex_institutional", started_at)
                except Exception as exc:  # noqa: BLE001
                    warnings.append(f"institutional {product} {current.isoformat()}: {exc}")
        current += timedelta(days=1)


def fetch_url_with_body(url: str, data: bytes) -> bytes:
    request = Request(
        url,
        data=data,
        headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/x-www-form-urlencoded"},
    )
    with urlopen(request, timeout=30) as response:
        return response.read()


def record_quality_checks(session: Session, market: str, source: str) -> list[str]:
    warnings: list[str] = []
    symbols = session.scalars(select(MarketDailyBar.symbol).where(MarketDailyBar.market == market).distinct()).all()
    for symbol in symbols:
        gap_count = count_business_day_gaps(session, market, symbol)
        if gap_count:
            warning = f"{market}/{symbol}: {gap_count} business-day gaps detected"
            warnings.append(warning)
            _record_run(session, source, date.today(), "quality_warning", warning, datetime.now(timezone.utc))
    return warnings


def count_business_day_gaps(session: Session, market: str, symbol: str) -> int:
    dates = [
        row[0]
        for row in session.execute(
            select(MarketDailyBar.bar_date)
            .where(MarketDailyBar.market == market, MarketDailyBar.symbol == symbol)
            .order_by(MarketDailyBar.bar_date)
        ).all()
    ]
    if len(dates) < 2:
        return 0
    date_set = set(dates)
    current = dates[0]
    missing = 0
    while current <= dates[-1]:
        if current.weekday() < 5 and current not in date_set:
            missing += 1
        current += timedelta(days=1)
    return missing


def _record_run(session: Session, source: str, run_date: date, status: str, detail: str | None, started_at: datetime) -> IngestRun:
    row = IngestRun(source=source, run_date=run_date, status=status, detail=detail, started_at=started_at, finished_at=datetime.now(timezone.utc))
    session.add(row)
    return row


class SimpleTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_cell = False
        self.current_cell: list[str] = []
        self.current_row: list[str] = []
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"td", "th"}:
            self.in_cell = True
            self.current_cell = []

    def handle_endtag(self, tag: str) -> None:
        lower = tag.lower()
        if lower in {"td", "th"} and self.in_cell:
            self.current_row.append("".join(self.current_cell))
            self.in_cell = False
        elif lower == "tr" and self.current_row:
            self.rows.append(self.current_row)
            self.current_row = []

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.current_cell.append(data)


def normalize_cell(value: str) -> str:
    return re.sub(r"\s+", "", value)


def map_identity(value: str) -> str | None:
    for label, identity in IDENTITY_MAP.items():
        if label in value:
            return identity
    return None
