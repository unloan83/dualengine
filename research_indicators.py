from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ResearchIndicators:
    rsi: float | None
    ema_fast: float | None
    ema_slow: float | None
    ema_state: str


def calculate_rsi(prices: list[float], period: int = 14) -> float | None:
    if len(prices) < period + 1:
        return None

    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, len(prices)):
        change = prices[i] - prices[i - 1]
        if change > 0:
            gains.append(change)
            losses.append(0.0)
        else:
            gains.append(abs(change))
            losses.append(abs(change)) if change < 0 else losses.append(0.0)

    if len(gains) < period:
        return None

    avg_gain = sum(gains[:period]) / float(period)
    avg_loss = sum(losses[:period]) / float(period)

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / float(period)
        avg_loss = (avg_loss * (period - 1) + losses[i]) / float(period)

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return round(rsi, 2)


def calculate_ema(prices: list[float], period: int) -> float | None:
    if len(prices) < period or period <= 0:
        return None

    multiplier = 2.0 / (period + 1)
    ema = sum(prices[:period]) / float(period)

    for price in prices[period:]:
        ema = (price - ema) * multiplier + ema

    return round(ema, 4)


def compute_research_indicators(
    prices: list[float],
    rsi_period: int = 14,
    fast_period: int = 9,
    slow_period: int = 21,
) -> ResearchIndicators:
    rsi = calculate_rsi(prices, rsi_period)
    ema_fast = calculate_ema(prices, fast_period)
    ema_slow = calculate_ema(prices, slow_period)

    if ema_fast is not None and ema_slow is not None:
        if ema_fast > ema_slow:
            ema_state = "POSITIVE"
        elif ema_fast < ema_slow:
            ema_state = "NEGATIVE"
        else:
            ema_state = "NEUTRAL"
    else:
        ema_state = "NEUTRAL"

    return ResearchIndicators(
        rsi=rsi,
        ema_fast=ema_fast,
        ema_slow=ema_slow,
        ema_state=ema_state,
    )
