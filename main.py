from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from config import load_config
from engine import DualEngine, DualEngineShadowRecord
from logger import ShadowLogger
from market_data import FuturesSnapshot, OHLCSnapshot, UpstoxMarketData

INDIA_TZ = ZoneInfo("Asia/Kolkata")


def run_shadow_cycle(
    client: UpstoxMarketData,
    engine: DualEngine,
    logger: ShadowLogger,
    symbols: tuple[str, ...],
) -> list[DualEngineShadowRecord]:
    now = datetime.now(INDIA_TZ)

    # 1. Map symbols to Upstox instrument keys for batch API queries
    # Standard format: NSE_EQ|<SYMBOL> (Cash OHLC) & NSE_FO|<SYMBOL> (Futures Quote/OI)
    eq_keys = [f"NSE_EQ|{sym}" for sym in symbols]
    fo_keys = [f"NSE_FO|{sym}" for sym in symbols]

    all_keys = eq_keys + fo_keys

    # 2. Fetch market quotes batch in REST call
    raw_quotes = client.fetch_quotes_batch(all_keys)

    records: list[DualEngineShadowRecord] = []

    for sym in symbols:
        try:
            eq_key = f"NSE_EQ|{sym}"
            fo_key = f"NSE_FO|{sym}"

            raw_eq = raw_quotes.get(eq_key) or raw_quotes.get(sym) or {}
            raw_fo = raw_quotes.get(fo_key) or {}

            prev_ohlc = client.parse_ohlc_snapshot(sym, raw_eq)
            futures_snap = client.parse_futures_snapshot(sym, raw_fo)

            # Fallback if separate futures key is not in response: check if raw_eq contains price/OI
            if futures_snap is None and raw_eq:
                futures_snap = client.parse_futures_snapshot(sym, raw_eq)

            rec = engine.evaluate_stock(
                symbol=sym,
                prev_ohlc=prev_ohlc,
                current_futures=futures_snap,
                recent_prices=None,
                now=now,
            )
            records.append(rec)
            logger.log_record(rec)
        except Exception as exc:
            # One bad symbol must NOT stop the batch (fail-safe)
            fallback = engine._build_fallback_record(sym, now.isoformat())
            records.append(fallback)
            logger.log_record(fallback)

    return records


def main() -> int:
    parser = argparse.ArgumentParser(description="DualEngine Standalone Shadow Intelligence Engine")
    parser.add_argument("--once", action="store_true", help="Run a single shadow evaluation cycle and exit")
    parser.add_argument("--interval", type=int, default=None, help="Polling interval in seconds (default from config)")
    args = parser.parse_args()

    config = load_config(Path(__file__).resolve().parent)
    poll_interval = args.interval if args.interval is not None else config.poll_interval_seconds

    client = UpstoxMarketData(access_token=config.upstox_access_token)
    engine = DualEngine()
    logger = ShadowLogger(config.log_file_path)

    print("=========================================================================")
    print(" DUALENGINE SHADOW INTELLIGENCE V1 (STANDALONE)")
    print("=========================================================================")
    print(f" Mode: SHADOW ONLY | Symbols: {len(config.symbols)} | Log: {config.log_file_path}")
    print(f" Trading / Order Capability: NONE (100% Shadow Analysis)")
    print("=========================================================================\n")

    while True:
        cycle_start = time.time()
        records = run_shadow_cycle(client, engine, logger, config.symbols)

        print(f"[{datetime.now(INDIA_TZ).isoformat()}] Evaluated {len(records)} symbols:")
        for r in records[:5]:
            print(
                f"  {r.symbol:10s} | CPR: {r.cpr_state:17s} | OI: {r.oi_state:16s} "
                f"| Direction: {r.dualengine_direction:7s} | Conf: {r.confidence:.2f} | Reasons: {r.reason_codes}"
            )
        if len(records) > 5:
            print(f"  ... and {len(records) - 5} more symbols logged to {config.log_file_path}")

        print()

        if args.once:
            break

        elapsed = time.time() - cycle_start
        sleep_time = max(1.0, poll_interval - elapsed)
        time.sleep(sleep_time)

    return 0


if __name__ == "__main__":
    sys.exit(main())
