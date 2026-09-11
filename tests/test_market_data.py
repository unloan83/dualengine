from __future__ import annotations

import unittest
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from market_data import UpstoxMarketData


class TestMarketData(unittest.TestCase):
    def setUp(self):
        self.client = UpstoxMarketData(access_token="mock_token")

    def test_parse_ohlc_snapshot_valid(self):
        quote_raw = {
            "instrument_token": "NSE_EQ|RELIANCE",
            "last_price": 2955.0,
            "timestamp": "2026-09-09T11:30:00+05:30",
        }
        daily_raw = {
            "instrument_token": "NSE_EQ|RELIANCE",
            "prev_ohlc": {
                "open": 2930.0,
                "high": 2960.0,
                "low": 2920.0,
                "close": 2940.0,
                "volume": 1250000,
            },
        }
        snap = self.client.parse_ohlc_snapshot("RELIANCE", quote_raw, daily_raw)
        self.assertIsNotNone(snap)
        self.assertEqual(snap.symbol, "RELIANCE")
        self.assertEqual(snap.open, 2930.0)
        self.assertEqual(snap.high, 2960.0)
        self.assertEqual(snap.low, 2920.0)
        self.assertEqual(snap.close, 2940.0)
        self.assertEqual(snap.last_price, 2955.0)

    def test_parse_ohlc_snapshot_invalid(self):
        # Invalid OHLC (missing fields or zero prices)
        quote_raw = {"last_price": 100.0}
        daily_raw = {"prev_ohlc": {"open": 0.0, "high": 0.0}}
        snap = self.client.parse_ohlc_snapshot("INVALID", quote_raw, daily_raw)
        self.assertIsNone(snap)

    def test_parse_ohlc_snapshot_refuses_current_session_ohlc_fallback(self):
        quote_raw = {
            "instrument_token": "NSE_EQ|RELIANCE",
            "last_price": 2955.0,
            "ohlc": {"open": 2950.0, "high": 2960.0, "low": 2940.0, "close": 2955.0},
        }
        self.assertIsNone(self.client.parse_ohlc_snapshot("RELIANCE", quote_raw))

    def test_parse_futures_snapshot_with_oi(self):
        raw = {
            "instrument_token": "NSE_FO|RELIANCE26SEPFUT",
            "last_price": 2960.0,
            "oi": 15420000.0,
            "previous_oi": 14438200.0,
            "prev_close_price": 2940.0,
            "ohlc": {"close": 2940.0},
            "timestamp": "2026-09-09T11:30:00+05:30",
        }
        snap = self.client.parse_futures_snapshot("RELIANCE", raw)
        self.assertIsNotNone(snap)
        self.assertEqual(snap.last_price, 2960.0)
        self.assertEqual(snap.current_oi, 15420000)
        self.assertEqual(snap.prev_oi, 14438200)

    def test_resolve_instruments_uses_nearest_future_and_daily_cache(self):
        rows = [
            {
                "segment": "NSE_EQ",
                "instrument_type": "EQ",
                "trading_symbol": "RELIANCE",
                "instrument_key": "equity-key",
            },
            {
                "segment": "NSE_FO",
                "instrument_type": "FUT",
                "underlying_symbol": "RELIANCE",
                "instrument_key": "later-future",
                "expiry": 1793298600000,
            },
            {
                "segment": "NSE_FO",
                "instrument_type": "FUT",
                "underlying_symbol": "RELIANCE",
                "instrument_key": "near-future",
                "expiry": 1790274600000,
            },
        ]
        transport = MagicMock(return_value=rows)
        client = UpstoxMarketData("token", instrument_transport=transport)
        as_of = datetime.fromisoformat("2026-09-11T09:20:00+05:30")

        first = client.resolve_instruments(["RELIANCE"], as_of=as_of)
        second = client.resolve_instruments(["RELIANCE"], as_of=as_of)

        self.assertEqual(first["RELIANCE"].equity_key, "equity-key")
        self.assertEqual(first["RELIANCE"].futures_key, "near-future")
        self.assertEqual(second, first)
        transport.assert_called_once()

    @patch("market_data.urlopen")
    def test_fetch_quotes_normalizes_v3_response_by_token(self, mocked_urlopen):
        response = MagicMock()
        response.status = 200
        response.read.return_value = (
            b'{"status":"success","data":{"NSE_EQ:RELIANCE":'
            b'{"instrument_token":"requested-key","last_price":1}}}'
        )
        mocked_urlopen.return_value.__enter__.return_value = response

        result = self.client.fetch_quotes_batch(["requested-key"])

        self.assertEqual(result["requested-key"]["last_price"], 1)
        requested_url = mocked_urlopen.call_args.args[0].full_url
        self.assertIn("/v3/market-quote/quotes?", requested_url)

    @patch("market_data.urlopen")
    def test_fetch_daily_ohlc_requests_explicit_one_day_interval(self, mocked_urlopen):
        response = MagicMock()
        response.status = 200
        response.read.return_value = (
            b'{"status":"success","data":{"NSE_EQ:RELIANCE":'
            b'{"instrument_token":"requested-key","prev_ohlc":{"close":1}}}}'
        )
        mocked_urlopen.return_value.__enter__.return_value = response

        result = self.client.fetch_daily_ohlc_batch(["requested-key"])

        self.assertIn("requested-key", result)
        requested_url = mocked_urlopen.call_args.args[0].full_url
        self.assertIn("/v3/market-quote/ohlc?", requested_url)
        self.assertIn("interval=1d", requested_url)

    def test_parse_futures_snapshot_missing_oi(self):
        raw = {
            "instrument_token": "NSE_EQ|NON_FO",
            "last_price": 500.0,
            "ohlc": {"close": 495.0},
        }
        snap = self.client.parse_futures_snapshot("NON_FO", raw)
        self.assertIsNotNone(snap)
        self.assertIsNone(snap.current_oi)
        self.assertIsNone(snap.prev_oi)


if __name__ == "__main__":
    unittest.main()
