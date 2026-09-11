from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Sequence
from zoneinfo import ZoneInfo

from cpr import (
    CPRLevels,
    calculate_cpr,
    classify_pdh_pdl,
    classify_price_vs_cpr,
    determine_cpr_state,
)
from market_data import FuturesSnapshot, OHLCSnapshot
from oi_intelligence import OIMetrics, calculate_oi_metrics
from research_indicators import ResearchIndicators, compute_research_indicators

INDIA_TZ = ZoneInfo("Asia/Kolkata")


@dataclass(frozen=True, slots=True)
class DualEngineOpinion:
    dualengine_direction: str
    confidence: float
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DualEngineShadowRecord:
    symbol: str
    timestamp: str
    cpr_state: str
    cpr_width: str
    price_vs_cpr: str
    futures_price_change_pct: float | None
    oi_change_pct: float | str | None
    oi_state: str
    rsi: float | None
    ema_state: str
    dualengine_direction: str
    confidence: float
    reason_codes: list[str]
    factual_metrics: dict[str, Any]
    derived_classifications: dict[str, Any]
    opinion: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "cpr_state": self.cpr_state,
            "cpr_width": self.cpr_width,
            "price_vs_cpr": self.price_vs_cpr,
            "futures_price_change_pct": self.futures_price_change_pct,
            "oi_change_pct": self.oi_change_pct if self.oi_change_pct is not None else "NOT_AVAILABLE",
            "oi_state": self.oi_state,
            "rsi": self.rsi,
            "ema_state": self.ema_state,
            "dualengine_direction": self.dualengine_direction,
            "confidence": self.confidence,
            "reason_codes": self.reason_codes,
            "factual_metrics": self.factual_metrics,
            "derived_classifications": self.derived_classifications,
            "opinion": self.opinion,
        }


class DualEngine:
    def evaluate_stock(
        self,
        symbol: str,
        prev_ohlc: OHLCSnapshot | None,
        current_futures: FuturesSnapshot | None = None,
        recent_prices: list[float] | None = None,
        now: datetime | None = None,
    ) -> DualEngineShadowRecord:
        timestamp_str = (now or datetime.now(INDIA_TZ)).astimezone(INDIA_TZ).isoformat()

        # Handle missing or invalid previous session OHLC
        if prev_ohlc is None or prev_ohlc.high <= 0 or prev_ohlc.low <= 0 or prev_ohlc.close <= 0:
            return self._build_fallback_record(symbol, timestamp_str)

        if prev_ohlc.last_price is None or prev_ohlc.last_price <= 0:
            return self._build_fallback_record(symbol, timestamp_str)

        cpr = calculate_cpr(prev_ohlc.high, prev_ohlc.low, prev_ohlc.close)
        # CPR and the executable paper entry are both cash-equity prices.
        # The stock-futures contract is used only for OI confirmation.
        current_price = prev_ohlc.last_price

        price_vs_cpr = classify_price_vs_cpr(current_price, cpr)
        pdh_pdl = classify_pdh_pdl(current_price, prev_ohlc.high, prev_ohlc.low)
        cpr_state = determine_cpr_state(current_price, cpr, prev_ohlc.high, prev_ohlc.low)

        # OI intelligence
        if current_futures:
            oi_metrics = calculate_oi_metrics(
                current_price=current_futures.last_price,
                prev_close=current_futures.prev_close,
                current_oi=current_futures.current_oi,
                prev_oi=current_futures.prev_oi,
            )
        else:
            oi_metrics = OIMetrics(
                price_change_pct=None,
                oi_change_pct=None,
                oi_state="NOT_AVAILABLE",
            )

        # Research-only indicators (Logged but do NOT determine V1 opinion)
        indicators = compute_research_indicators(recent_prices or [])

        # Formulate V1 DualEngine opinion strictly based on CPR + OI
        opinion = self._generate_opinion(cpr_state, oi_metrics.oi_state)

        factual = {
            "cpr_pivot": cpr.pivot,
            "cpr_tc": cpr.tc,
            "cpr_bc": cpr.bc,
            "cpr_width_pct": cpr.width_pct,
            "prev_high": prev_ohlc.high,
            "prev_low": prev_ohlc.low,
            "prev_close": prev_ohlc.close,
            "current_price": current_price,
            "futures_last_price": current_futures.last_price if current_futures else None,
            "futures_price_change_pct": oi_metrics.price_change_pct,
            "current_oi": current_futures.current_oi if current_futures else None,
            "previous_oi": current_futures.prev_oi if current_futures else None,
            "oi_change_pct": oi_metrics.oi_change_pct if oi_metrics.oi_change_pct is not None else "NOT_AVAILABLE",
            "rsi": indicators.rsi,
            "ema_fast": indicators.ema_fast,
            "ema_slow": indicators.ema_slow,
        }

        derived = {
            "cpr_state": cpr_state,
            "cpr_width": cpr.width_classification,
            "price_vs_cpr": price_vs_cpr,
            "pdh_pdl_state": pdh_pdl,
            "oi_state": oi_metrics.oi_state,
            "ema_state": indicators.ema_state,
        }

        opinion_dict = {
            "dualengine_direction": opinion.dualengine_direction,
            "confidence": opinion.confidence,
            "reason_codes": list(opinion.reason_codes),
        }

        return DualEngineShadowRecord(
            symbol=symbol,
            timestamp=timestamp_str,
            cpr_state=cpr_state,
            cpr_width=cpr.width_classification,
            price_vs_cpr=price_vs_cpr,
            futures_price_change_pct=oi_metrics.price_change_pct,
            oi_change_pct=oi_metrics.oi_change_pct if oi_metrics.oi_change_pct is not None else "NOT_AVAILABLE",
            oi_state=oi_metrics.oi_state,
            rsi=indicators.rsi,
            ema_state=indicators.ema_state,
            dualengine_direction=opinion.dualengine_direction,
            confidence=opinion.confidence,
            reason_codes=list(opinion.reason_codes),
            factual_metrics=factual,
            derived_classifications=derived,
            opinion=opinion_dict,
        )

    def _generate_opinion(self, cpr_state: str, oi_state: str) -> DualEngineOpinion:
        reasons: list[str] = []

        if cpr_state in ("BULLISH", "MODERATELY_BULLISH"):
            reasons.append("ABOVE_CPR")
            if oi_state == "PRICE_UP_OI_UP":
                reasons.append("OI_LONG_BUILDUP")
                return DualEngineOpinion("LONG", 0.85, tuple(reasons))
            if oi_state == "PRICE_UP_OI_DOWN":
                reasons.append("OI_SHORT_COVERING")
                return DualEngineOpinion("LONG", 0.75, tuple(reasons))
            if oi_state == "NOT_AVAILABLE":
                reasons.append("OI_NOT_AVAILABLE")
                return DualEngineOpinion("LONG", 0.60, tuple(reasons))
            reasons.append("OI_DIVERGENCE")
            return DualEngineOpinion("NEUTRAL", 0.50, tuple(reasons))

        if cpr_state in ("BEARISH", "MODERATELY_BEARISH"):
            reasons.append("BELOW_CPR")
            if oi_state == "PRICE_DOWN_OI_UP":
                reasons.append("OI_SHORT_BUILDUP")
                return DualEngineOpinion("SHORT", 0.85, tuple(reasons))
            if oi_state == "PRICE_DOWN_OI_DOWN":
                reasons.append("OI_LONG_UNWINDING")
                return DualEngineOpinion("SHORT", 0.75, tuple(reasons))
            if oi_state == "NOT_AVAILABLE":
                reasons.append("OI_NOT_AVAILABLE")
                return DualEngineOpinion("SHORT", 0.60, tuple(reasons))
            reasons.append("OI_DIVERGENCE")
            return DualEngineOpinion("NEUTRAL", 0.50, tuple(reasons))

        reasons.append("INSIDE_CPR")
        return DualEngineOpinion("NEUTRAL", 0.50, tuple(reasons))

    def _build_fallback_record(
        self, symbol: str, timestamp_str: str
    ) -> DualEngineShadowRecord:
        return DualEngineShadowRecord(
            symbol=symbol,
            timestamp=timestamp_str,
            cpr_state="NOT_AVAILABLE",
            cpr_width="NOT_AVAILABLE",
            price_vs_cpr="NOT_AVAILABLE",
            futures_price_change_pct=None,
            oi_change_pct="NOT_AVAILABLE",
            oi_state="NOT_AVAILABLE",
            rsi=None,
            ema_state="NEUTRAL",
            dualengine_direction="NEUTRAL",
            confidence=0.0,
            reason_codes=["MISSING_DATA"],
            factual_metrics={},
            derived_classifications={
                "cpr_state": "NOT_AVAILABLE",
                "oi_state": "NOT_AVAILABLE",
            },
            opinion={
                "dualengine_direction": "NEUTRAL",
                "confidence": 0.0,
                "reason_codes": ["MISSING_DATA"],
            },
        )
