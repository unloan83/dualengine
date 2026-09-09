# DualEngine V1 (Standalone Shadow Intelligence Engine)

`dualengine` is an independent **SHADOW intelligence engine** that calculates market structure metrics (CPR levels, Price vs CPR, PDH/PDL relationship, F&O Futures Price + Open Interest intelligence, RSI, and EMA structure) and records its independent opinion to timestamped JSON lines logs for research and later comparison.

---

## CRITICAL INVARIANTS & ISOLATION

- **SHADOW ONLY**: `dualengine` has **ZERO** order execution, broker placement, position tracking, stop-loss, target calculation, or trade commands.
- **ZERO DAYBAGGER DEPENDENCY**: `dualengine` is strictly standalone. It does NOT import, modify, depend on, patch, or interact with Daybagger code, services, databases, or schedulers.
- **DATA SOURCE**: Upstox REST API only.

---

## ARCHITECTURE

```
dualengine/
├── .env.example              # Sample environment configuration
├── README.md                 # Documentation
├── config.py                 # Configuration loader (symbols, API tokens, polling)
├── cpr.py                    # CPR (Pivot, BC, TC, Width), Price vs CPR, PDH/PDL classification
├── oi_intelligence.py        # F&O Futures Price & OI change %, 4-quadrant classification
├── research_indicators.py    # Research-only indicators (RSI, EMA structure) - Logged ONLY
├── engine.py                 # Independent DualEngine opinion generation & record creation
├── logger.py                 # Bounded/rotating JSON lines logger
├── main.py                   # CLI entrypoint (--once or continuous shadow polling)
├── requirements.txt          # Minimal Python dependencies (requests, python-dotenv)
└── tests/                    # Comprehensive unit test suite
    ├── test_cpr.py
    ├── test_oi_intelligence.py
    ├── test_indicators.py
    ├── test_market_data.py
    └── test_engine.py
```

---

## CPR & OI CLASSIFICATION RULES

### 1. CPR (Central Pivot Range)
- **Pivot** = `(High + Low + Close) / 3`
- **BC** = `(High + Low) / 2`
- **TC** = `2 * Pivot - BC`
- **Width %** = `(cpr_top - cpr_bottom) / Pivot * 100`
- **CPR Width Classification**:
  - `NARROW`: `< 0.25%`
  - `AVERAGE`: `0.25% - 0.75%`
  - `WIDE`: `> 0.75%`

### 2. Price & OI 4-Quadrant Classification
- `PRICE_UP_OI_UP` (Long Buildup)
- `PRICE_DOWN_OI_UP` (Short Buildup)
- `PRICE_UP_OI_DOWN` (Short Covering)
- `PRICE_DOWN_OI_DOWN` (Long Unwinding)
- `NOT_AVAILABLE` (When OI data is missing or stock is non-F&O)

### 3. Research Indicators
- **RSI** (14-period) & **EMA** (9 & 21 period) are logged for research analysis **ONLY** and do **NOT** determine the final V1 opinion.

---

## USAGE & EXECUTION

### Run Unit Tests
```bash
python -m unittest discover -s tests -p "test_*.py"
```

### Run Single Shadow Cycle
```bash
python main.py --once
```

### Run Continuous Shadow Loop (Every 5 minutes)
```bash
python main.py --interval 300
```

---

## COMPACT OUTPUT SCHEMA

```json
{
  "symbol": "RELIANCE",
  "timestamp": "2026-09-09T11:30:00+05:30",
  "cpr_state": "BULLISH",
  "cpr_width": "NARROW",
  "price_vs_cpr": "ABOVE_TC",
  "futures_price_change_pct": 0.74,
  "oi_change_pct": 6.8,
  "oi_state": "PRICE_UP_OI_UP",
  "rsi": 63.0,
  "ema_state": "POSITIVE",
  "dualengine_direction": "LONG",
  "confidence": 0.78,
  "reason_codes": ["ABOVE_CPR", "OI_LONG_BUILDUP"],
  "factual_metrics": { ... },
  "derived_classifications": { ... },
  "opinion": { ... }
}
```
