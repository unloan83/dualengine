from datetime import datetime

from engine.engine_core import DualEngineShadowRecord
from main import map_record_to_signal_params


def _record(direction: str) -> DualEngineShadowRecord:
    return DualEngineShadowRecord(
        symbol="TEST",
        timestamp=datetime.now().astimezone().isoformat(),
        cpr_state="BULLISH" if direction == "LONG" else "BEARISH",
        cpr_width="NARROW",
        price_vs_cpr="ABOVE_TC" if direction == "LONG" else "BELOW_BC",
        futures_price_change_pct=1.0,
        oi_change_pct=1.0,
        oi_state="PRICE_UP_OI_UP" if direction == "LONG" else "PRICE_DOWN_OI_UP",
        rsi=None,
        ema_state="NEUTRAL",
        dualengine_direction=direction,
        confidence=0.85,
        reason_codes=["TEST"],
        factual_metrics={
            "current_price": 100.0,
            "cpr_bc": 95.0,
            "cpr_tc": 105.0,
        },
        derived_classifications={},
        opinion={},
    )


def test_long_maps_lower_cpr_boundary_as_invalidation():
    mapped = map_record_to_signal_params(_record("LONG"))
    assert mapped["entry_price"] == 100.0
    assert mapped["stop_loss"] == 95.0


def test_short_maps_upper_cpr_boundary_as_invalidation():
    mapped = map_record_to_signal_params(_record("SHORT"))
    assert mapped["entry_price"] == 100.0
    assert mapped["stop_loss"] == 105.0
