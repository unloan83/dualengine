from __future__ import annotations

import gzip
import json
import math
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

INDIA_TZ = ZoneInfo("Asia/Kolkata")


@dataclass(frozen=True, slots=True)
class OHLCSnapshot:
    symbol: str
    instrument_key: str
    as_of: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    prev_close: float
    last_price: float | None = None


@dataclass(frozen=True, slots=True)
class FuturesSnapshot:
    symbol: str
    instrument_key: str
    as_of: str
    last_price: float
    prev_close: float
    current_oi: int | None
    prev_oi: int | None
    oi_day_high: int | None
    oi_day_low: int | None


@dataclass(frozen=True, slots=True)
class InstrumentPair:
    symbol: str
    equity_key: str
    futures_key: str
    futures_expiry: date


InstrumentTransport = Callable[[str, float], list[dict[str, Any]]]


class UpstoxMarketData:
    QUOTE_URL = "https://api.upstox.com/v3/market-quote/quotes"
    OHLC_URL = "https://api.upstox.com/v3/market-quote/ohlc"
    INSTRUMENTS_URL = (
        "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"
    )

    def __init__(
        self,
        access_token: str,
        timeout_seconds: float = 10.0,
        instrument_transport: InstrumentTransport | None = None,
    ):
        self.access_token = access_token.strip()
        self.timeout = timeout_seconds
        self._instrument_transport = instrument_transport or _download_instruments
        self._instrument_cache_date: date | None = None
        self._instrument_cache: dict[str, InstrumentPair] = {}

    def resolve_instruments(
        self,
        symbols: Sequence[str],
        *,
        as_of: datetime | None = None,
    ) -> dict[str, InstrumentPair]:
        now = (as_of or datetime.now(INDIA_TZ)).astimezone(INDIA_TZ)
        wanted = tuple(
            dict.fromkeys(
                str(symbol).strip().upper()
                for symbol in symbols
                if str(symbol).strip()
            )
        )
        if not wanted:
            return {}

        if self._instrument_cache_date != now.date():
            rows = self._instrument_transport(self.INSTRUMENTS_URL, self.timeout)
            self._instrument_cache = _resolve_instrument_rows(rows, now.date())
            self._instrument_cache_date = now.date()

        return {
            symbol: self._instrument_cache[symbol]
            for symbol in wanted
            if symbol in self._instrument_cache
        }

    def fetch_quotes_batch(
        self, instrument_keys: Sequence[str]
    ) -> dict[str, dict[str, Any]]:
        clean_keys = [k.strip() for k in instrument_keys if k and k.strip()]
        if not clean_keys or not self.access_token:
            return {}

        # Limit to 500 keys per batch as per Upstox API limits
        batch = clean_keys[:500]
        query = urlencode({"instrument_key": ",".join(batch)})
        url = f"{self.QUOTE_URL}?{query}"

        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.access_token}",
            "User-Agent": "DualEngine-Shadow/1.0",
        }

        req = Request(url, headers=headers, method="GET")
        try:
            with urlopen(req, timeout=self.timeout) as resp:
                if resp.status != 200:
                    return {}
                payload = json.loads(resp.read().decode("utf-8"))
                if payload.get("status") != "success":
                    return {}
                data = payload.get("data")
                if not isinstance(data, dict):
                    return {}
                normalized: dict[str, dict[str, Any]] = {}
                for raw in data.values():
                    if not isinstance(raw, dict):
                        continue
                    instrument_token = str(raw.get("instrument_token") or "").strip()
                    if instrument_token:
                        normalized[instrument_token] = raw
                return normalized
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, Exception):
            return {}

    def fetch_daily_ohlc_batch(
        self, instrument_keys: Sequence[str]
    ) -> dict[str, dict[str, Any]]:
        """Fetch explicit live and previous-session daily equity OHLC."""
        clean_keys = [k.strip() for k in instrument_keys if k and k.strip()]
        if not clean_keys or not self.access_token:
            return {}
        query = urlencode({
            "instrument_key": ",".join(clean_keys[:500]),
            "interval": "1d",
        })
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.access_token}",
            "User-Agent": "DualEngine-Shadow/1.0",
        }
        req = Request(f"{self.OHLC_URL}?{query}", headers=headers, method="GET")
        try:
            with urlopen(req, timeout=self.timeout) as resp:
                if resp.status != 200:
                    return {}
                payload = json.loads(resp.read().decode("utf-8"))
                if payload.get("status") != "success":
                    return {}
                data = payload.get("data")
                if not isinstance(data, dict):
                    return {}
                normalized = {}
                for raw in data.values():
                    if not isinstance(raw, dict):
                        continue
                    token = str(raw.get("instrument_token") or "").strip()
                    if token:
                        normalized[token] = raw
                return normalized
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, Exception):
            return {}

    def parse_ohlc_snapshot(
        self,
        symbol: str,
        quote_raw: dict[str, Any],
        daily_ohlc_raw: dict[str, Any] | None = None,
    ) -> OHLCSnapshot | None:
        if not isinstance(quote_raw, dict) or not isinstance(daily_ohlc_raw, dict):
            return None
        previous = daily_ohlc_raw.get("prev_ohlc")
        if not isinstance(previous, dict):
            return None

        try:
            open_p = float(previous.get("open", 0.0))
            high_p = float(previous.get("high", 0.0))
            low_p = float(previous.get("low", 0.0))
            close_p = float(previous.get("close", 0.0))
            last_p = float(quote_raw.get("last_price", 0.0))

            if min(open_p, high_p, low_p, close_p, last_p) <= 0:
                return None
            if high_p < max(open_p, close_p, low_p) or low_p > min(open_p, close_p, high_p):
                return None

            prev_close = close_p
            volume = int(previous.get("volume") or 0)
            as_of_ts = quote_raw.get("timestamp") or datetime.now(INDIA_TZ).isoformat()

            return OHLCSnapshot(
                symbol=symbol,
                instrument_key=str(quote_raw.get("instrument_token") or symbol),
                as_of=str(as_of_ts),
                open=open_p,
                high=high_p,
                low=low_p,
                close=close_p,
                volume=volume,
                prev_close=prev_close,
                last_price=last_p,
            )
        except (ValueError, TypeError):
            return None

    def parse_futures_snapshot(
        self, symbol: str, raw: dict[str, Any]
    ) -> FuturesSnapshot | None:
        if not isinstance(raw, dict):
            return None

        try:
            last_p = float(raw.get("last_price") or 0.0)
            ohlc = raw.get("ohlc") if isinstance(raw.get("ohlc"), dict) else {}
            prev_close = float(
                raw.get("prev_close_price")
                or ohlc.get("close")
                or ohlc.get("open")
                or last_p
            )

            if last_p <= 0:
                return None

            current_oi = _optional_nonnegative_int(raw.get("oi"))

            # Upstox quote snapshots contain OI data for futures contracts
            prev_oi = _optional_nonnegative_int(
                raw.get("previous_oi")
                if raw.get("previous_oi") is not None
                else raw.get("prev_oi")
            )

            oi_high = _optional_nonnegative_int(raw.get("oi_day_high"))
            oi_low = _optional_nonnegative_int(raw.get("oi_day_low"))

            as_of_ts = raw.get("timestamp") or datetime.now(INDIA_TZ).isoformat()

            return FuturesSnapshot(
                symbol=symbol,
                instrument_key=str(raw.get("instrument_token") or symbol),
                as_of=str(as_of_ts),
                last_price=last_p,
                prev_close=prev_close,
                current_oi=current_oi,
                prev_oi=prev_oi,
                oi_day_high=oi_high,
                oi_day_low=oi_low,
            )
        except (ValueError, TypeError):
            return None


def _download_instruments(url: str, timeout_seconds: float) -> list[dict[str, Any]]:
    request = Request(
        url,
        headers={"Accept": "application/json, application/gzip"},
        method="GET",
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        payload = json.loads(gzip.decompress(response.read()).decode("utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Upstox instrument master is not a list")
    return [row for row in payload if isinstance(row, dict)]


def _resolve_instrument_rows(
    rows: Sequence[dict[str, Any]],
    session_date: date,
) -> dict[str, InstrumentPair]:
    equities: dict[str, str] = {}
    futures: dict[str, list[tuple[date, str]]] = {}

    for row in rows:
        segment = str(row.get("segment") or "").strip().upper()
        instrument_type = str(row.get("instrument_type") or "").strip().upper()
        instrument_key = str(row.get("instrument_key") or "").strip()
        if not instrument_key:
            continue

        if segment == "NSE_EQ" and instrument_type == "EQ":
            symbol = str(row.get("trading_symbol") or "").strip().upper()
            if symbol:
                equities[symbol] = instrument_key
            continue

        if segment == "NSE_FO" and instrument_type == "FUT":
            symbol = str(row.get("underlying_symbol") or "").strip().upper()
            expiry = _parse_expiry_date(row.get("expiry"))
            if symbol and expiry is not None and expiry >= session_date:
                futures.setdefault(symbol, []).append((expiry, instrument_key))

    resolved: dict[str, InstrumentPair] = {}
    for symbol, equity_key in equities.items():
        contracts = futures.get(symbol)
        if not contracts:
            continue
        expiry, futures_key = min(contracts, key=lambda item: (item[0], item[1]))
        resolved[symbol] = InstrumentPair(
            symbol=symbol,
            equity_key=equity_key,
            futures_key=futures_key,
            futures_expiry=expiry,
        )
    return resolved


def _parse_expiry_date(value: Any) -> date | None:
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        seconds = float(value)
        if seconds > 10_000_000_000:
            seconds /= 1000.0
        return datetime.fromtimestamp(seconds, tz=INDIA_TZ).date()
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    return None


def _optional_nonnegative_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number < 0 or not number.is_integer():
        return None
    return int(number)
