from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CPRLevels:
    pivot: float
    bc: float
    tc: float
    cpr_top: float
    cpr_bottom: float
    width_pct: float
    width_classification: str


def calculate_cpr(high: float, low: float, close: float) -> CPRLevels:
    if high <= 0 or low <= 0 or close <= 0:
        raise ValueError("OHLC prices must be positive")
    if high < low:
        raise ValueError("High cannot be lower than Low")

    pivot = (high + low + close) / 3.0
    bc = (high + low) / 2.0
    tc = 2.0 * pivot - bc

    cpr_top = max(tc, bc)
    cpr_bottom = min(tc, bc)

    width_pct = ((cpr_top - cpr_bottom) / pivot) * 100.0 if pivot > 0 else 0.0

    if width_pct < 0.25:
        width_classification = "NARROW"
    elif width_pct > 0.75:
        width_classification = "WIDE"
    else:
        width_classification = "AVERAGE"

    return CPRLevels(
        pivot=round(pivot, 4),
        bc=round(bc, 4),
        tc=round(tc, 4),
        cpr_top=round(cpr_top, 4),
        cpr_bottom=round(cpr_bottom, 4),
        width_pct=round(width_pct, 4),
        width_classification=width_classification,
    )


def classify_price_vs_cpr(current_price: float, cpr: CPRLevels) -> str:
    if current_price > cpr.cpr_top:
        return "ABOVE_TC"
    if current_price < cpr.cpr_bottom:
        return "BELOW_BC"
    return "INSIDE_CPR"


def classify_pdh_pdl(current_price: float, pdh: float, pdl: float) -> str:
    if current_price > pdh:
        return "ABOVE_PDH"
    if current_price < pdl:
        return "BELOW_PDL"
    return "INSIDE_PDH_PDL"


def determine_cpr_state(
    current_price: float, cpr: CPRLevels, pdh: float, pdl: float
) -> str:
    price_vs_cpr = classify_price_vs_cpr(current_price, cpr)
    pdh_pdl = classify_pdh_pdl(current_price, pdh, pdl)

    if price_vs_cpr == "ABOVE_TC" and pdh_pdl == "ABOVE_PDH":
        return "BULLISH"
    if price_vs_cpr == "BELOW_BC" and pdh_pdl == "BELOW_PDL":
        return "BEARISH"
    if price_vs_cpr == "ABOVE_TC":
        return "MODERATELY_BULLISH"
    if price_vs_cpr == "BELOW_BC":
        return "MODERATELY_BEARISH"
    return "NEUTRAL"
