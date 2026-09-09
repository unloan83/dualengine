from __future__ import annotations

import unittest
import sys
from pathlib import Path

# Ensure dualengine directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cpr import (
    calculate_cpr,
    classify_pdh_pdl,
    classify_price_vs_cpr,
    determine_cpr_state,
)


class TestCPR(unittest.TestCase):
    def test_calculate_cpr_known_example(self):
        # Example 1: Symmetric High=100, Low=90, Close=95
        cpr = calculate_cpr(high=100.0, low=90.0, close=95.0)
        self.assertEqual(cpr.pivot, 95.0)
        self.assertEqual(cpr.bc, 95.0)
        self.assertEqual(cpr.tc, 95.0)
        self.assertEqual(cpr.cpr_top, 95.0)
        self.assertEqual(cpr.cpr_bottom, 95.0)
        self.assertEqual(cpr.width_pct, 0.0)
        self.assertEqual(cpr.width_classification, "NARROW")

    def test_calculate_cpr_asymmetric(self):
        # Example 2: High=2960, Low=2920, Close=2950
        # Pivot = (2960 + 2920 + 2950) / 3 = 2943.3333
        # BC = (2960 + 2920) / 2 = 2940.0
        # TC = 2 * 2943.3333 - 2940 = 2946.6667
        cpr = calculate_cpr(high=2960.0, low=2920.0, close=2950.0)
        self.assertAlmostEqual(cpr.pivot, 2943.3333, places=3)
        self.assertEqual(cpr.cpr_top, 2946.6667)
        self.assertEqual(cpr.cpr_bottom, 2940.0)
        self.assertTrue(cpr.width_pct > 0)

    def test_cpr_width_classifications(self):
        # Very narrow CPR
        narrow = calculate_cpr(high=100.1, low=99.9, close=100.0)
        self.assertEqual(narrow.width_classification, "NARROW")

        # Wide CPR (High=110, Low=90, Close=105 -> width = 3.28% > 0.75%)
        wide = calculate_cpr(high=110.0, low=90.0, close=105.0)
        self.assertEqual(wide.width_classification, "WIDE")

    def test_classify_price_vs_cpr(self):
        cpr = calculate_cpr(high=105.0, low=95.0, close=100.0)
        # TC=100, BC=100, Pivot=100
        self.assertEqual(classify_price_vs_cpr(106.0, cpr), "ABOVE_TC")
        self.assertEqual(classify_price_vs_cpr(94.0, cpr), "BELOW_BC")
        self.assertEqual(classify_price_vs_cpr(100.0, cpr), "INSIDE_CPR")

    def test_determine_cpr_state(self):
        cpr = calculate_cpr(high=100.0, low=90.0, close=95.0)
        # cpr_top = 95.0, cpr_bottom = 95.0, PDH=100.0, PDL=90.0
        # Bullish: price > cpr_top and price >= PDH
        self.assertEqual(determine_cpr_state(101.0, cpr, pdh=100.0, pdl=90.0), "BULLISH")
        # Moderately bullish: price > cpr_top but price < PDH
        self.assertEqual(determine_cpr_state(98.0, cpr, pdh=100.0, pdl=90.0), "MODERATELY_BULLISH")
        # Bearish: price < cpr_bottom and price <= PDL
        self.assertEqual(determine_cpr_state(89.0, cpr, pdh=100.0, pdl=90.0), "BEARISH")


if __name__ == "__main__":
    unittest.main()
