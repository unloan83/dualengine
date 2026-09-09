from __future__ import annotations

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine import DualEngine
from market_data import OHLCSnapshot
from research_indicators import calculate_ema, calculate_rsi, compute_research_indicators


class TestIndicators(unittest.TestCase):
    def test_calculate_rsi(self):
        # 15 steadily increasing prices -> high RSI
        prices = [float(100 + i) for i in range(20)]
        rsi = calculate_rsi(prices, period=14)
        self.assertIsNotNone(rsi)
        self.assertEqual(rsi, 100.0)

        # Insufficient data
        self.assertIsNone(calculate_rsi([10.0, 11.0], period=14))

    def test_calculate_ema(self):
        prices = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0]
        ema = calculate_ema(prices, period=5)
        self.assertIsNotNone(ema)
        self.assertTrue(ema > 10.0)

    def test_indicators_do_not_affect_dualengine_opinion(self):
        engine = DualEngine()
        prev_ohlc = OHLCSnapshot("RELIANCE", "NSE_EQ|RELIANCE", "2026-09-09", 100.0, 105.0, 95.0, 102.0, 1000, 100.0)

        # Evaluate with bullish RSI / EMA
        rec_high_rsi = engine.evaluate_stock(
            symbol="RELIANCE",
            prev_ohlc=prev_ohlc,
            current_futures=None,
            recent_prices=[100.0 + i for i in range(20)],
        )

        # Evaluate with bearish RSI / EMA
        rec_low_rsi = engine.evaluate_stock(
            symbol="RELIANCE",
            prev_ohlc=prev_ohlc,
            current_futures=None,
            recent_prices=[100.0 - i for i in range(20)],
        )

        # RSI values must be recorded differently in research features
        self.assertNotEqual(rec_high_rsi.rsi, rec_low_rsi.rsi)

        # But final DualEngine opinion direction & confidence MUST remain identical
        self.assertEqual(rec_high_rsi.dualengine_direction, rec_low_rsi.dualengine_direction)
        self.assertEqual(rec_high_rsi.confidence, rec_low_rsi.confidence)


if __name__ == "__main__":
    unittest.main()
