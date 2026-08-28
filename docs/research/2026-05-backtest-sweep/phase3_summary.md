# Phase 3: per-symbol × per-strategy × per-timeframe backtest

168 cells. 168 succeeded, 2 passed acceptance.

**Acceptance:** full_return>0 AND oos_return>0 AND oos_sharpe>0.5 AND max_dd<20% AND trades≥10

**Fees/slippage:** 5+5 bps. **Equity:** $25k. **IS/OOS split:** 70/30 walk-forward.

## Survivors (passed acceptance)
| sym | strategy | tf | full_ret% | OOS_ret% | OOS_sharpe | OOS_n | full_trades | full_wr% | max_dd% |
|---|---|---|---|---|---|---|---|---|---|
| DOGE | regime_momentum | 4h | +11.69 | +2663.83 | +0.86 | 109 | 383 | 41.0 | 8.16 |
| BTC | regime_momentum | 4h | +1.57 | +1134.30 | +0.65 | 93 | 342 | 36.3 | 6.05 |

## Top 25 by OOS return (regardless of full-period sign)
| sym | strategy | tf | full_ret% | OOS_ret% | OOS_sharpe | OOS_n | accept |
|---|---|---|---|---|---|---|---|
| ETH | ema_crossover | 4h | -3.23 | +5707.61 | +4.89 | 16 |  |
| ARB | rsi2_connors | 4h | -17.36 | +5204.37 | +1.51 | 159 |  |
| AVAX | mean_reversion | 4h | -6.25 | +4605.89 | +6.54 | 22 |  |
| ARB | range_breakout | 1h | -4.53 | +4017.51 | +4.71 | 38 |  |
| DOGE | trend_pullback | 4h | -7.79 | +3903.41 | +1.45 | 108 |  |
| LINK | mean_reversion | 4h | -11.60 | +3822.22 | +8.46 | 16 |  |
| DOGE | regime_momentum | 4h | +11.69 | +2663.83 | +0.86 | 109 | ✓ |
| ETH | mean_reversion | 4h | -9.54 | +2081.90 | +5.04 | 22 |  |
| ARB | turtle_donchian | 1h | -8.68 | +2005.43 | +2.82 | 10 |  |
| BTC | ema_crossover | 4h | -1.01 | +1775.37 | +1.78 | 21 |  |
| DOGE | mean_reversion | 1h | -2.65 | +1692.04 | +4.22 | 24 |  |
| SOL | mean_reversion | 4h | -8.38 | +1569.85 | +3.97 | 17 |  |
| AVAX | rsi2_connors | 4h | -17.22 | +1261.74 | +0.32 | 195 |  |
| BTC | regime_momentum | 4h | +1.57 | +1134.30 | +0.65 | 93 | ✓ |
| DOGE | rsi2_connors | 4h | -12.61 | +1079.16 | +0.33 | 177 |  |
| ARB | range_breakout | 4h | -0.08 | +1045.91 | +0.39 | 44 |  |
| AVAX | mean_reversion | 1h | -3.87 | +944.79 | +2.79 | 19 |  |
| DOGE | slow_drift_follow | 4h | -7.22 | +936.20 | +0.40 | 112 |  |
| BTC | range_breakout | 4h | -1.15 | +929.27 | +0.74 | 46 |  |
| DOGE | slow_drift_follow | 1h | -3.55 | +795.32 | +1.01 | 91 |  |
| ETH | mean_reversion | 1h | -3.12 | +669.39 | +2.41 | 21 |  |
| AVAX | slow_drift_follow | 4h | -8.13 | +641.82 | +0.26 | 126 |  |
| SOL | slow_drift_follow | 4h | -4.57 | +585.54 | +0.24 | 121 |  |
| ETH | trend_pullback | 4h | -18.14 | +472.01 | +0.23 | 106 |  |
| ETH | regime_momentum | 4h | +2.50 | +399.67 | +0.18 | 109 |  |

## By strategy × timeframe — averages across 7 symbols
| strategy | tf | avg_full_ret% | avg_OOS_ret% | n_pos_full | n_pos_OOS | n_pass_acceptance |
|---|---|---|---|---|---|---|
| mean_reversion | 4h | -8.76 | +1350.55 | 0/7 | 4/7 | 0/7 |
| mean_reversion | 1h | -3.30 | +182.36 | 0/7 | 3/7 | 0/7 |
| orb_session | 1h | +0.00 | +0.00 | 0/7 | 0/7 | 0/7 |
| measured_move | 1h | +0.00 | +0.00 | 0/7 | 0/7 | 0/7 |
| band_fade | 1h | +0.00 | +0.00 | 0/7 | 0/7 | 0/7 |
| vol_breakout | 4h | +0.00 | +0.00 | 0/7 | 0/7 | 0/7 |
| orb_session | 4h | +0.00 | +0.00 | 0/7 | 0/7 | 0/7 |
| measured_move | 4h | +0.00 | +0.00 | 0/7 | 0/7 | 0/7 |
| band_fade | 4h | +0.00 | +0.00 | 0/7 | 0/7 | 0/7 |
| vol_breakout | 1h | +0.05 | -0.63 | 3/7 | 0/7 | 0/7 |
| rsi2_connors | 4h | -15.42 | -169.32 | 0/7 | 3/7 | 0/7 |
| regime_momentum | 4h | -0.79 | -564.75 | 3/7 | 3/7 | 2/7 |
| trend_pullback | 4h | -11.54 | -573.46 | 0/7 | 2/7 | 0/7 |
| turtle_donchian | 1h | -8.95 | -576.13 | 0/7 | 2/7 | 0/7 |
| slow_drift_follow | 1h | -5.12 | -614.73 | 0/7 | 3/7 | 0/7 |
| range_breakout | 1h | -3.98 | -680.04 | 0/7 | 2/7 | 0/7 |
| slow_drift_follow | 4h | -7.05 | -1345.45 | 0/7 | 3/7 | 0/7 |
| ema_crossover | 4h | -1.12 | -1592.54 | 3/7 | 2/7 | 0/7 |
| ema_crossover | 1h | -6.38 | -1688.53 | 1/7 | 0/7 | 0/7 |
| regime_momentum | 1h | -12.85 | -1706.16 | 0/7 | 0/7 | 0/7 |
| trend_pullback | 1h | -14.66 | -2035.80 | 0/7 | 0/7 | 0/7 |
| turtle_donchian | 4h | +3.35 | -3014.69 | 4/7 | 0/7 | 0/7 |
| rsi2_connors | 1h | -16.54 | -3164.55 | 0/7 | 0/7 | 0/7 |
| range_breakout | 4h | -1.01 | -3332.11 | 2/7 | 2/7 | 0/7 |