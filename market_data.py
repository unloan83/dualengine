from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
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


class UpstoxMarketData:
    BASE_URL = "https://api.upstox.com/v2"

    def __init__(self, access_token: str, timeout_seconds: float = 10.0):
        self.access_token = access_token.strip()
        self.timeout = timeout_seconds

    def fetch_quotes_batch(
        self, instrument_keys: Sequence[str]
    ) -> dict[str, dict[str, Any]]:
        clean_keys = [k.strip() for k in instrument_keys if k and k.strip()]
        if not clean_keys or not self.access_token:
            return {}

        # Limit to 500 keys per batch as per Upstox API limits
        batch = clean_keys[:500]
        query = urlencode({"instrument_key": ",".join(batch)})
        url = f"{self.BASE_URL}/market-quote/quotes?{query}"

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
                return data if isinstance(data, dict) else {}
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, Exception):
            return {}

    def parse_ohlc_snapshot(
        self, symbol: str, raw: dict[str, Any]
    ) -> OHLCSnapshot | None:
        if not isinstance(raw, dict):
            return None
        ohlc = raw.get("ohlc")
        if not isinstance(ohlc, dict):
            return None

        try:
            open_p = float(ohlc.get("open", 0.0))
            high_p = float(ohlc.get("high", 0.0))
            low_p = float(ohlc.get("low", 0.0))
            close_p = float(ohlc.get("close", 0.0))
            last_p = float(raw.get("last_price", close_p or 0.0))

            if open_p <= 0 or high_p <= 0 or low_p <= 0 or close_p <= 0:
                return None

            prev_close = float(ohlc.get("prev_close") or close_p)
            volume = int(raw.get("volume") or 0)
            as_of_ts = raw.get("timestamp") or datetime.now(INDIA_TZ).isoformat()

            return OHLCSnapshot(
                symbol=symbol,
                instrument_key=str(raw.get("instrument_token") or symbol),
                as_of=str(as_of_ts),
                open=open_p,
                high=high_p,
                low=low_p,
                close=last_p if last_p > 0 else close_p,
                volume=volume,
                prev_close=prev_close,
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
            prev_close = float(ohlc.get("close") or ohlc.get("open") or last_p)

            if last_p <= 0:
                return None

            raw_oi = raw.get("oi")
            current_oi = int(raw_oi) if raw_oi is not None and str(raw_oi).isdigit() else None

            # Upstox quote snapshots contain OI data for futures contracts
            raw_prev_oi = raw.get("prev_oi") or raw.get("previous_oi")
            prev_oi = int(raw_prev_oi) if raw_prev_oi is not None and str(raw_prev_oi).isdigit() else None

            oi_high = int(raw["oi_day_high"]) if raw.get("oi_day_high") is not None else None
            oi_low = int(raw["oi_day_low"]) if raw.get("oi_day_low") is not None else None

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
