from __future__ import annotations

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from market_data import UpstoxMarketData


class TestMarketData(unittest.TestCase):
    def setUp(self):
        self.client = UpstoxMarketData(access_token="mock_token")

    def test_parse_ohlc_snapshot_valid(self):
        raw = {
            "instrument_token": "NSE_EQ|RELIANCE",
            "last_price": 2955.0,
            "volume": 1250000,
            "timestamp": "2026-09-09T11:30:00+05:30",
            "ohlc": {
                "open": 2930.0,
                "high": 2960.0,
                "low": 2920.0,
                "close": 2940.0,
                "prev_close": 2925.0,
            },
        }
        snap = self.client.parse_ohlc_snapshot("RELIANCE", raw)
        self.assertIsNotNone(snap)
        self.assertEqual(snap.symbol, "RELIANCE")
        self.assertEqual(snap.open, 2930.0)
        self.assertEqual(snap.high, 2960.0)
        self.assertEqual(snap.low, 2920.0)
        self.assertEqual(snap.close, 2955.0)

    def test_parse_ohlc_snapshot_invalid(self):
        # Invalid OHLC (missing fields or zero prices)
        raw = {"ohlc": {"open": 0.0, "high": 0.0}}
        snap = self.client.parse_ohlc_snapshot("INVALID", raw)
        self.assertIsNone(snap)

    def test_parse_futures_snapshot_with_oi(self):
        raw = {
            "instrument_token": "NSE_FO|RELIANCE26SEPFUT",
            "last_price": 2960.0,
            "oi": 15420000,
            "prev_oi": 14438200,
            "ohlc": {"close": 2940.0},
            "timestamp": "2026-09-09T11:30:00+05:30",
        }
        snap = self.client.parse_futures_snapshot("RELIANCE", raw)
        self.assertIsNotNone(snap)
        self.assertEqual(snap.last_price, 2960.0)
        self.assertEqual(snap.current_oi, 15420000)
        self.assertEqual(snap.prev_oi, 14438200)

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
