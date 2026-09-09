from __future__ import annotations

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from oi_intelligence import calculate_oi_metrics


class TestOIIntelligence(unittest.TestCase):
    def test_price_up_oi_up_long_buildup(self):
        m = calculate_oi_metrics(
            current_price=105.0, prev_close=100.0, current_oi=1100, prev_oi=1000
        )
        self.assertEqual(m.price_change_pct, 5.0)
        self.assertEqual(m.oi_change_pct, 10.0)
        self.assertEqual(m.oi_state, "PRICE_UP_OI_UP")

    def test_price_down_oi_up_short_buildup(self):
        m = calculate_oi_metrics(
            current_price=95.0, prev_close=100.0, current_oi=1100, prev_oi=1000
        )
        self.assertEqual(m.price_change_pct, -5.0)
        self.assertEqual(m.oi_change_pct, 10.0)
        self.assertEqual(m.oi_state, "PRICE_DOWN_OI_UP")

    def test_price_up_oi_down_short_covering(self):
        m = calculate_oi_metrics(
            current_price=105.0, prev_close=100.0, current_oi=900, prev_oi=1000
        )
        self.assertEqual(m.price_change_pct, 5.0)
        self.assertEqual(m.oi_change_pct, -10.0)
        self.assertEqual(m.oi_state, "PRICE_UP_OI_DOWN")

    def test_price_down_oi_down_long_unwinding(self):
        m = calculate_oi_metrics(
            current_price=95.0, prev_close=100.0, current_oi=900, prev_oi=1000
        )
        self.assertEqual(m.price_change_pct, -5.0)
        self.assertEqual(m.oi_change_pct, -10.0)
        self.assertEqual(m.oi_state, "PRICE_DOWN_OI_DOWN")

    def test_missing_oi_returns_not_available(self):
        m1 = calculate_oi_metrics(
            current_price=105.0, prev_close=100.0, current_oi=None, prev_oi=1000
        )
        self.assertIsNone(m1.oi_change_pct)
        self.assertEqual(m1.oi_state, "NOT_AVAILABLE")

        m2 = calculate_oi_metrics(
            current_price=105.0, prev_close=100.0, current_oi=1100, prev_oi=None
        )
        self.assertEqual(m2.oi_state, "NOT_AVAILABLE")


if __name__ == "__main__":
    unittest.main()
