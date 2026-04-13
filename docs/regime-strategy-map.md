# WolfPack Regime-Strategy Map

Single source of truth for which strategies fire in which market regimes, and how each strategy's parameters auto-adapt. Every wallet (v1 Full Send, v2 Conservative, v3 Human Heuristics) shares this map — the flavor differences live in YOLO level, sizing, and conviction floors, not in regime logic.

## Six canonical regimes

The regime router (`intel/wolfpack/strategies/regime_router.py`) emits **specific sub-regimes** which collapse to **parent families** via `regime_family()`:

| Specific sub-regime | Family | Detection trigger | Strategies allowed |
|---|---|---|---|
| `TRENDING_UP` | `TRENDING` | `regime=trending_up` + multi-TF agreement ≥ 0.75 | ema_crossover (long), turtle_donchian (long), orb_session |
| `TRENDING_DOWN` | `TRENDING` | `regime=trending_down` + multi-TF agreement ≥ 0.75 | ema_crossover (short), turtle_donchian (short), orb_session |
| `RANGING_LOW_VOL` | `RANGING` | `regime=choppy/low_vol_grind` + `vol_regime ∈ {low, normal}` | mean_reversion, band_fade |
| `RANGING_HIGH_VOL` | `RANGING` | `regime=choppy` + `vol_regime=elevated` | mean_reversion, band_fade |
| `VOLATILE` | `VOLATILE` | `regime=panic` OR `vol_regime=extreme` | *(none — tighten stops only)* |
| `TRANSITION` | `TRANSITION` | pending regime ≠ current AND debounce count < 3 | *(none — tighten stops, wait)* |

**Debounce** requires 3 consecutive ticks of the same pending regime before promoting it to current. VOLATILE is always immediate (safety override).

## Strategy-by-strategy behavior

### mean_reversion (1h candles)
Fade deviations from the 20-period SMA back toward the mean. Fires in RANGING regimes with params tuned to band width. In TRENDING, the extreme 3.0 ATR threshold acts as a contrarian "capitulation fade" filter.

| Regime | mean_period | threshold_atr_mult | stop_atr_mult | size_pct |
|---|---|---|---|---|
| `RANGING_LOW_VOL` | 15 | 1.2 | 0.6 | 8% |
| `RANGING_HIGH_VOL` | 20 | 2.0 | 1.0 | 10% |
| `TRENDING_UP / DOWN` | 20 | 3.0 | 1.0 | 12% |
| `VOLATILE / TRANSITION` | — (disabled) | | | |

**Why it matters:** the pre-adaptation default of 3.0 made this strategy mathematically inert in actual range chop. The 1.2 RANGING_LOW_VOL threshold fires on normal band oscillations (the bread and butter of chop).

### band_fade (1h candles) — NEW in Phase R1
Pure range play: fires when price closes outside the Bollinger Band AND RSI(14) confirms overbought/oversold. Targets the middle band (SMA) for TP.

| Regime | bb_stdev | rsi_oversold | rsi_overbought | stop_atr_mult | size_pct |
|---|---|---|---|---|---|
| `RANGING_LOW_VOL` | 2.0 | 35 | 65 | 0.6 | 10% |
| `RANGING_HIGH_VOL` | 2.5 | 30 | 70 | 0.9 | 8% |
| *(any other)* | — (disabled) | | | | |

### ema_crossover (1h candles)
Classic fast/slow EMA crossover (20/50). Golden cross → long, death cross → short. Regime gates prevent whipsaw entries in chop:

- `TRENDING_UP`: longs only (golden crosses). Conviction +5 (75 instead of 70) because aligned with trend.
- `TRENDING_DOWN`: shorts only (death crosses). Same conviction bump.
- `RANGING_*, VOLATILE, TRANSITION`: **disabled** — too many false crosses in chop.
- `None`: both directions (back-compat for tests).

### turtle_donchian (1h candles)
20-period Donchian channel breakout with SMA(55) trend filter and ATR(2.0) stops. Structural exit (close on opposite channel break).

- `TRENDING_UP`: long breakouts only (conviction 70 instead of 65).
- `TRENDING_DOWN`: short breakouts only.
- `RANGING_*, VOLATILE, TRANSITION`: **disabled** — range highs/lows are traps, not breakouts.
- **Close signals fire regardless of regime** (structural exit for existing positions is regime-agnostic).
- `None`: both directions allowed.

### orb_session (5m candles)
Opening-range breakout for specific session-open windows (NY / London / Asia). Currently enabled in `TRENDING_UP` and `TRENDING_DOWN` families — session breakouts are trend-follow plays.

### measured_move (5m candles)
Session-open measured-move breakout. Was previously misclassified as a range strategy; now correctly routed as a trend/breakout play only during session-open windows.

### regime_momentum (1h candles)
Bucket-momentum trend follower. Not yet regime-gated (operates on its own internal signal). Future work.

### vol_breakout (1h candles)
Volatility expansion from compression. Not yet regime-gated; will eventually fire in a BREAKOUT sub-regime (future work).

## TRANSITION handling

When the regime router detects a pending regime that differs from the current regime AND the debounce counter is below threshold (<3 ticks), it emits `transition=True`. The auto-trader:

1. **Does not open new positions** (all strategies return None or are filtered upstream).
2. **Tightens trailing stops** on existing positions: any stop wider than 2.0% gets multiplied by 0.7 (down to a 2.0% floor) so profitable positions preserve more P&L if the regime flip goes against them.
3. **Resumes normal operation** once the debounce count hits 3 and the new regime is confirmed, at which point the appropriate strategy set takes over.

This is distinct from `VOLATILE` (panic posture, trailing stops → 1.5% floor) — TRANSITION is a "wait and see" pause while we decide if the regime is really changing.

## Observability

- **`GET /regime/state?symbol=BTC`** — current specific regime + family, pending, debounce count, transition flag, last reason.
- **Cycle logs** — every cycle emits `[auto-trader] Regime routing: SPECIFIC (family=FAMILY) -- reason [debounce=pending(N/3)]`.
- **Regime shift logs** — `[regime-router] BTC: REGIME SHIFT TRENDING_UP -> RANGING_LOW_VOL (confirmed after 3 ticks)`.

## When to edit this map

- Adding a new strategy → add a row to the relevant regime section + update `_ALLOWED_BY_REGIME` in `regime_router.py`.
- Adjusting regime-specific params → edit the strategy's `REGIME_PRESETS` / `_REGIME_PRESETS` dict.
- Adding a new sub-regime → extend the `Regime` enum in `modules/regime.py`, update `_classify_macro` in `regime_router.py`, and add a mapping row to `FAMILY_OF`.

## References

- Router: `intel/wolfpack/strategies/regime_router.py`
- Strategies: `intel/wolfpack/strategies/*.py`
- Regime detection: `intel/wolfpack/modules/regime.py`
- Volatility module: `intel/wolfpack/modules/volatility.py`
- Wiring: `intel/wolfpack/auto_trader.py::process_strategy_signals`
