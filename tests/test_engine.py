from __future__ import annotations

import json
import os
import tempfile
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine import DualEngine, DualEngineShadowRecord
from logger import ShadowLogger
from market_data import FuturesSnapshot, OHLCSnapshot


class TestEngine(unittest.TestCase):
    def setUp(self):
        self.engine = DualEngine()
        self.prev_ohlc = OHLCSnapshot(
            symbol="RELIANCE",
            instrument_key="NSE_EQ|RELIANCE",
            as_of="2026-09-09T09:15:00+05:30",
            open=2930.0,
            high=2960.0,
            low=2920.0,
            close=2940.0,
            volume=100000,
            prev_close=2920.0,
        )
        self.futures_snap = FuturesSnapshot(
            symbol="RELIANCE",
            instrument_key="NSE_FO|RELIANCE26SEPFUT",
            as_of="2026-09-09T11:30:00+05:30",
            last_price=2965.0,
            prev_close=2940.0,
            current_oi=15420000,
            prev_oi=14438200,
            oi_day_high=15500000,
            oi_day_low=14400000,
        )

    def test_output_schema_structure(self):
        rec = self.engine.evaluate_stock(
            symbol="RELIANCE",
            prev_ohlc=self.prev_ohlc,
            current_futures=self.futures_snap,
            recent_prices=[2930.0, 2940.0, 2950.0, 2965.0],
        )

        d = rec.to_dict()

        # 1. Top-level required keys
        self.assertEqual(d["symbol"], "RELIANCE")
        self.assertIn("timestamp", d)
        self.assertEqual(d["cpr_state"], "BULLISH")
        self.assertEqual(d["price_vs_cpr"], "ABOVE_TC")
        self.assertEqual(d["oi_state"], "PRICE_UP_OI_UP")
        self.assertEqual(d["dualengine_direction"], "LONG")
        self.assertTrue(d["confidence"] > 0.5)

        # 2. Distinct subsections
        self.assertIn("factual_metrics", d)
        self.assertIn("derived_classifications", d)
        self.assertIn("opinion", d)

        # Factual metrics
        self.assertEqual(d["factual_metrics"]["cpr_pivot"], 2940.0)
        self.assertEqual(d["factual_metrics"]["current_oi"], 15420000)

        # Derived classifications
        self.assertEqual(d["derived_classifications"]["cpr_state"], "BULLISH")
        self.assertEqual(d["derived_classifications"]["oi_state"], "PRICE_UP_OI_UP")

        # Opinion
        self.assertEqual(d["opinion"]["dualengine_direction"], "LONG")

    def test_logger_rotation_and_restart(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_path = Path(tmp_dir) / "shadow.jsonl"
            logger = ShadowLogger(log_path, max_bytes=500, backup_count=3)

            rec = self.engine.evaluate_stock(
                symbol="RELIANCE",
                prev_ohlc=self.prev_ohlc,
                current_futures=self.futures_snap,
            )

            for _ in range(10):
                logger.log_record(rec)

            self.assertTrue(log_path.exists())
            self.assertTrue(log_path.stat().st_size > 0)

    def test_zero_external_repo_imports_or_references(self):
        dualengine_root = Path(__file__).resolve().parents[1]
        py_files = list(dualengine_root.rglob("*.py"))
        self.assertTrue(len(py_files) > 0)

        forbidden = "day" + "bagger"
        for pf in py_files:
            content = pf.read_text(encoding="utf-8")
            self.assertNotIn(
                forbidden,
                content.lower(),
                msg=f"{pf} contains reference/import to external repo!",
            )


if __name__ == "__main__":
    unittest.main()
