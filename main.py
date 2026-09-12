from __future__ import annotations

import argparse
from dataclasses import replace
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from config import load_config
from engine import DualEngine, DualEngineShadowRecord
from engine.publisher import SignalPublisher
from logger import ShadowLogger
from market_data import FuturesSnapshot, OHLCSnapshot, UpstoxMarketData
from trading_contracts.schemas.v1 import Direction, MarketRegime
from trading_contracts.execution import liquidity_slippage_bps_per_side

INDIA_TZ = ZoneInfo("Asia/Kolkata")


def map_record_to_signal_params(r: DualEngineShadowRecord):
    direction = (
        Direction.LONG if r.dualengine_direction == "LONG"
        else Direction.SHORT if r.dualengine_direction == "SHORT"
        else Direction.NO_TRADE
    )
    regime = (
        MarketRegime.TRENDING if r.cpr_state in ("BULLISH", "BEARISH")
        else MarketRegime.RANGE_BOUND
    )
    entry_price = float(r.factual_metrics.get("current_price") or r.factual_metrics.get("prev_close") or 0.0)
    if direction == Direction.LONG:
        stop_loss = float(r.factual_metrics.get("cpr_bc") or 0.0)
    elif direction == Direction.SHORT:
        stop_loss = float(r.factual_metrics.get("cpr_tc") or 0.0)
    else:
        stop_loss = 0.0
    prior_turnover = float(r.factual_metrics.get("prev_close") or 0.0) * float(
        r.factual_metrics.get("prev_volume") or 0.0
    )
    return {
        "instrument_id": r.symbol,
        "direction": direction,
        "setup_type": "CPR_OI_INTELLIGENCE",
        "regime": regime,
        "confidence": float(r.confidence),
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "reasons": r.reason_codes,
        "slippage_bps_per_side": liquidity_slippage_bps_per_side(prior_turnover),
        "cohort": str(r.derived_classifications.get("contract_cohort") or "STANDARD"),
    }


def run_shadow_cycle(
    client: UpstoxMarketData,
    engine: DualEngine,
    logger: ShadowLogger,
    symbols: tuple[str, ...],
    publisher: SignalPublisher | None = None,
) -> list[DualEngineShadowRecord]:
    now = datetime.now(INDIA_TZ)

    instruments = client.resolve_instruments(symbols, as_of=now)
    eq_keys = [pair.equity_key for pair in instruments.values()]
    fo_keys = [pair.futures_key for pair in instruments.values()]
    all_keys = eq_keys + fo_keys

    raw_quotes = client.fetch_quotes_batch(all_keys)
    daily_ohlc = client.fetch_daily_ohlc_batch(eq_keys)
    records: list[DualEngineShadowRecord] = []

    for sym in symbols:
        try:
            pair = instruments.get(sym)
            if pair is None:
                raise ValueError(f"{sym}: no current Upstox equity/futures mapping")

            raw_eq = raw_quotes.get(pair.equity_key) or {}
            raw_fo = raw_quotes.get(pair.futures_key) or {}

            prev_ohlc = client.parse_ohlc_snapshot(
                sym,
                raw_eq,
                daily_ohlc.get(pair.equity_key),
            )
            actions = client.fetch_corporate_actions(pair.equity_isin, as_of=now.date())
            if prev_ohlc is None or actions is None:
                raise ValueError(f"{sym}: corporate-action validation unavailable")
            prev_ohlc = client.adjust_previous_ohlc_for_actions(
                prev_ohlc, actions, session_date=now.date()
            )
            futures_snap = client.parse_futures_snapshot(sym, raw_fo)

            if futures_snap is None and raw_eq:
                futures_snap = client.parse_futures_snapshot(sym, raw_eq)

            rec = engine.evaluate_stock(
                symbol=sym,
                prev_ohlc=prev_ohlc,
                current_futures=futures_snap,
                recent_prices=None,
                now=now,
            )
            if pair.contract_cohort != "STANDARD":
                rec = replace(
                    rec,
                    reason_codes=[*rec.reason_codes, pair.contract_cohort],
                    derived_classifications={
                        **rec.derived_classifications,
                        "contract_cohort": pair.contract_cohort,
                    },
                    opinion={
                        **rec.opinion,
                        "reason_codes": [*rec.opinion["reason_codes"], pair.contract_cohort],
                    },
                )
            records.append(rec)
            logger.log_record(rec)

            if publisher is not None:
                params = map_record_to_signal_params(rec)
                publisher.publish_signal(**params)

        except Exception as exc:
            fallback = engine._build_fallback_record(sym, now.isoformat())
            records.append(fallback)
            logger.log_record(fallback)

            if publisher is not None:
                params = map_record_to_signal_params(fallback)
                publisher.publish_signal(**params)

    return records


def main() -> int:
    parser = argparse.ArgumentParser(description="DualEngine Standalone Shadow Intelligence Engine")
    parser.add_argument("--once", action="store_true", help="Run a single shadow evaluation cycle and exit")
    parser.add_argument("--interval", type=int, default=None, help="Polling interval in seconds (default from config)")
    parser.add_argument("--publish", action="store_true", default=True, help="Enable ZeroMQ & DuckDB publishing")
    args = parser.parse_args()

    config = load_config(Path(__file__).resolve().parent)
    poll_interval = args.interval if args.interval is not None else config.poll_interval_seconds

    client = UpstoxMarketData(access_token=config.upstox_access_token)
    engine = DualEngine()
    logger = ShadowLogger(config.log_file_path)
    publisher = SignalPublisher() if args.publish else None

    print("=========================================================================")
    print(" DUALENGINE SHADOW INTELLIGENCE V1 (STANDALONE)")
    print("=========================================================================")
    print(f" Mode: SHADOW ONLY | Symbols: {len(config.symbols)} | Log: {config.log_file_path}")
    print(f" Publisher: {'ENABLED (ZeroMQ + DuckDB)' if publisher else 'DISABLED'}")
    print("=========================================================================\n")

    try:
        while True:
            cycle_start = time.time()
            records = run_shadow_cycle(client, engine, logger, config.symbols, publisher=publisher)

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
    finally:
        if publisher:
            publisher.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
