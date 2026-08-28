# Phase 1 Backtest Sweep — 90d, 1h candles

Ran 77 cells (77 succeeded, 0 failed) in 44s.

## Top 20 by full-period total return

| sym | strategy | trades | WR% | full_ret% | calmar | max_dd% | OOS_trades | OOS_pnl$ |
|---|---|---|---|---|---|---|---|---|
| DOGE | mean_reversion | 47 | 34.0 | +0.46 | 0.18 | 2.50 | 12 | +221.19 |
| BTC | orb_session | 0 | 0.0 | +0.00 | 0.00 | 0.00 | 0 | +0.00 |
| BTC | measured_move | 0 | 0.0 | +0.00 | 0.00 | 0.00 | 0 | +0.00 |
| BTC | band_fade | 0 | 0.0 | +0.00 | 0.00 | 0.00 | 0 | +0.00 |
| ETH | vol_breakout | 0 | 0.0 | +0.00 | 0.00 | 0.00 | 0 | +0.00 |
| ETH | orb_session | 0 | 0.0 | +0.00 | 0.00 | 0.00 | 0 | +0.00 |
| ETH | measured_move | 0 | 0.0 | +0.00 | 0.00 | 0.00 | 0 | +0.00 |
| ETH | band_fade | 0 | 0.0 | +0.00 | 0.00 | 0.00 | 0 | +0.00 |
| SOL | vol_breakout | 0 | 0.0 | +0.00 | 0.00 | 0.00 | 0 | +0.00 |
| SOL | orb_session | 0 | 0.0 | +0.00 | 0.00 | 0.00 | 0 | +0.00 |
| SOL | measured_move | 0 | 0.0 | +0.00 | 0.00 | 0.00 | 0 | +0.00 |
| SOL | band_fade | 0 | 0.0 | +0.00 | 0.00 | 0.00 | 0 | +0.00 |
| LINK | vol_breakout | 0 | 0.0 | +0.00 | 0.00 | 0.00 | 0 | +0.00 |
| LINK | orb_session | 0 | 0.0 | +0.00 | 0.00 | 0.00 | 0 | +0.00 |
| LINK | measured_move | 0 | 0.0 | +0.00 | 0.00 | 0.00 | 0 | +0.00 |
| LINK | band_fade | 0 | 0.0 | +0.00 | 0.00 | 0.00 | 0 | +0.00 |
| AVAX | vol_breakout | 0 | 0.0 | +0.00 | 0.00 | 0.00 | 0 | +0.00 |
| AVAX | orb_session | 0 | 0.0 | +0.00 | 0.00 | 0.00 | 0 | +0.00 |
| AVAX | measured_move | 0 | 0.0 | +0.00 | 0.00 | 0.00 | 0 | +0.00 |
| AVAX | band_fade | 0 | 0.0 | +0.00 | 0.00 | 0.00 | 0 | +0.00 |

## Bottom 20 (worst) by full-period total return

| sym | strategy | trades | WR% | full_ret% | calmar | max_dd% |
|---|---|---|---|---|---|---|
| SOL | ema_crossover | 22 | 31.8 | -4.05 | -0.55 | 7.30 |
| AVAX | turtle_donchian | 23 | 13.0 | -4.89 | -0.83 | 5.88 |
| LINK | turtle_donchian | 26 | 15.4 | -4.98 | -0.77 | 6.48 |
| ETH | turtle_donchian | 22 | 9.1 | -5.14 | -0.93 | 5.50 |
| DOGE | ema_crossover | 37 | 29.7 | -5.19 | -0.54 | 9.57 |
| ETH | trend_pullback | 131 | 40.5 | -5.83 | -0.94 | 6.20 |
| BTC | trend_pullback | 140 | 40.7 | -5.95 | -0.93 | 6.38 |
| SOL | regime_momentum | 159 | 32.1 | -6.38 | -0.87 | 7.36 |
| LINK | regime_momentum | 152 | 32.2 | -6.47 | -0.91 | 7.15 |
| SOL | turtle_donchian | 25 | 8.0 | -6.51 | -0.84 | 7.78 |
| DOGE | regime_momentum | 160 | 34.4 | -6.56 | -0.71 | 9.22 |
| LINK | ema_crossover | 33 | 21.2 | -6.56 | -0.73 | 8.97 |
| AVAX | regime_momentum | 157 | 32.5 | -6.78 | -0.98 | 6.95 |
| AVAX | ema_crossover | 24 | 25.0 | -7.17 | -0.75 | 9.50 |
| SOL | trend_pullback | 155 | 40.6 | -7.50 | -0.96 | 7.77 |
| ARB | regime_momentum | 163 | 28.8 | -7.66 | -0.84 | 9.12 |
| DOGE | trend_pullback | 142 | 42.2 | -8.18 | -0.91 | 9.00 |
| ARB | trend_pullback | 150 | 42.0 | -8.33 | -0.95 | 8.78 |
| LINK | trend_pullback | 141 | 35.5 | -9.52 | -0.97 | 9.77 |
| AVAX | trend_pullback | 145 | 31.7 | -9.53 | -0.97 | 9.81 |

## By strategy — average across 7 symbols

| strategy | avg_ret% | avg_calmar | total_trades | avg_WR% | n_pos_symbols | avg_OOS_pnl$ |
|---|---|---|---|---|---|---|
| orb_session | +0.00 | 0.00 | 0 | 0.0 | 0/7 | +0.00 |
| measured_move | +0.00 | 0.00 | 0 | 0.0 | 0/7 | +0.00 |
| band_fade | +0.00 | 0.00 | 0 | 0.0 | 0/7 | +0.00 |
| vol_breakout | -0.00 | -0.03 | 1 | 0.0 | 0/7 | -0.10 |
| mean_reversion | -0.90 | -0.37 | 279 | 31.6 | 1/7 | +21.27 |
| range_breakout | -1.59 | -0.78 | 483 | 41.0 | 0/7 | -90.09 |
| slow_drift_follow | -2.13 | -0.93 | 998 | 35.1 | 0/7 | +8.63 |
| ema_crossover | -3.97 | -0.53 | 193 | 31.8 | 0/7 | -432.68 |
| turtle_donchian | -3.98 | -0.66 | 154 | 13.6 | 0/7 | +60.96 |
| regime_momentum | -5.65 | -0.87 | 1084 | 32.1 | 0/7 | -269.80 |
| trend_pullback | -7.84 | -0.95 | 1004 | 39.0 | 0/7 | -234.37 |

## By symbol — average across 11 strategies

| symbol | avg_ret% | best_strategy | best_ret% | n_pos_strategies |
|---|---|---|---|---|
| BTC | -1.48 | orb_session | +0.00 | 0/11 |
| ETH | -1.74 | vol_breakout | +0.00 | 0/11 |
| DOGE | -2.34 | mean_reversion | +0.46 | 1/11 |
| ARB | -2.40 | vol_breakout | +0.00 | 0/11 |
| SOL | -2.51 | vol_breakout | +0.00 | 0/11 |
| LINK | -3.06 | vol_breakout | +0.00 | 0/11 |
| AVAX | -3.07 | vol_breakout | +0.00 | 0/11 |