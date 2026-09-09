from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OIMetrics:
    price_change_pct: float | None
    oi_change_pct: float | None
    oi_state: str


def calculate_oi_metrics(
    current_price: float | None,
    prev_close: float | None,
    current_oi: int | float | None,
    prev_oi: int | float | None,
) -> OIMetrics:
    if (
        current_oi is None
        or prev_oi is None
        or prev_oi <= 0
        or current_price is None
        or prev_close is None
        or prev_close <= 0
    ):
        price_pct = (
            round(((current_price - prev_close) / prev_close) * 100.0, 4)
            if (current_price is not None and prev_close is not None and prev_close > 0)
            else None
        )
        return OIMetrics(
            price_change_pct=price_pct,
            oi_change_pct=None,
            oi_state="NOT_AVAILABLE",
        )

    price_change_pct = round(((current_price - prev_close) / prev_close) * 100.0, 4)
    oi_change_pct = round(((current_oi - prev_oi) / float(prev_oi)) * 100.0, 4)

    if price_change_pct > 0 and oi_change_pct > 0:
        oi_state = "PRICE_UP_OI_UP"
    elif price_change_pct < 0 and oi_change_pct > 0:
        oi_state = "PRICE_DOWN_OI_UP"
    elif price_change_pct > 0 and oi_change_pct < 0:
        oi_state = "PRICE_UP_OI_DOWN"
    elif price_change_pct < 0 and oi_change_pct < 0:
        oi_state = "PRICE_DOWN_OI_DOWN"
    else:
        oi_state = "NEUTRAL"

    return OIMetrics(
        price_change_pct=price_change_pct,
        oi_change_pct=oi_change_pct,
        oi_state=oi_state,
    )
