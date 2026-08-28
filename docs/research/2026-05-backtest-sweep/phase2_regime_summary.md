# Phase 2: Regime Decomposition on mean_reversion

90 days × 7 symbols × 1 strategy. Goal: find regime conditions where mean_reversion has positive expectancy.

## Per-feature P&L decomposition

### BTC (baseline: 36 trades, ret -0.79%, IS-60d $+309.52 / OOS-30d $-109.23)

**atr_pct:**
| bucket | n | pnl$ | per-trade$ |
|---|---|---|---|
| high | 15 | +470.55 | +31.37 |
| low | 10 | -90.96 | -9.10 |
| mid | 8 | -169.57 | -21.20 |

**trend_v_ema200:**
| bucket | n | pnl$ | per-trade$ |
|---|---|---|---|
| above_ema200 | 32 | +233.24 | +7.29 |
| below_ema200 | 1 | -23.22 | -23.22 |

**ema20_slope:**
| bucket | n | pnl$ | per-trade$ |
|---|---|---|---|
| rising | 33 | +210.02 | +6.36 |

**rsi:**
| bucket | n | pnl$ | per-trade$ |
|---|---|---|---|
| overbought | 29 | +296.27 | +10.22 |
| neutral | 4 | -86.25 | -21.56 |

**bbw_pct:**
| bucket | n | pnl$ | per-trade$ |
|---|---|---|---|
| high | 18 | +365.64 | +20.31 |
| mid | 11 | -43.78 | -3.98 |
| low | 4 | -111.84 | -27.96 |

**hurst:**
| bucket | n | pnl$ | per-trade$ |
|---|---|---|---|
| trending | 29 | +185.48 | +6.40 |
| mean_rev | 4 | +24.54 | +6.13 |

### ETH (baseline: 41 trades, ret -0.90%, IS-60d $+216.51 / OOS-30d $+159.83)

**atr_pct:**
| bucket | n | pnl$ | per-trade$ |
|---|---|---|---|
| high | 25 | +503.32 | +20.13 |
| low | 8 | +77.58 | +9.70 |
| mid | 6 | -124.23 | -20.71 |

**trend_v_ema200:**
| bucket | n | pnl$ | per-trade$ |
|---|---|---|---|
| above_ema200 | 36 | +531.98 | +14.78 |
| below_ema200 | 3 | -75.31 | -25.10 |

**ema20_slope:**
| bucket | n | pnl$ | per-trade$ |
|---|---|---|---|
| rising | 39 | +456.67 | +11.71 |

**rsi:**
| bucket | n | pnl$ | per-trade$ |
|---|---|---|---|
| overbought | 37 | +519.33 | +14.04 |
| neutral | 2 | -62.66 | -31.33 |

**bbw_pct:**
| bucket | n | pnl$ | per-trade$ |
|---|---|---|---|
| high | 24 | +597.57 | +24.90 |
| mid | 7 | -23.60 | -3.37 |
| low | 8 | -117.30 | -14.66 |

**hurst:**
| bucket | n | pnl$ | per-trade$ |
|---|---|---|---|
| mean_rev | 7 | +294.41 | +42.06 |
| trending | 32 | +162.26 | +5.07 |

### SOL (baseline: 30 trades, ret -0.98%, IS-60d $+88.49 / OOS-30d $-4.75)

**atr_pct:**
| bucket | n | pnl$ | per-trade$ |
|---|---|---|---|
| high | 18 | +341.12 | +18.95 |
| low | 3 | -15.12 | -5.04 |
| mid | 6 | -81.78 | -13.63 |

**trend_v_ema200:**
| bucket | n | pnl$ | per-trade$ |
|---|---|---|---|
| above_ema200 | 27 | +244.22 | +9.05 |

**ema20_slope:**
| bucket | n | pnl$ | per-trade$ |
|---|---|---|---|
| rising | 27 | +244.22 | +9.05 |

**rsi:**
| bucket | n | pnl$ | per-trade$ |
|---|---|---|---|
| overbought | 26 | +252.48 | +9.71 |
| neutral | 1 | -8.26 | -8.26 |

**bbw_pct:**
| bucket | n | pnl$ | per-trade$ |
|---|---|---|---|
| high | 17 | +326.97 | +19.23 |
| mid | 6 | -33.92 | -5.65 |
| low | 4 | -48.83 | -12.21 |

**hurst:**
| bucket | n | pnl$ | per-trade$ |
|---|---|---|---|
| trending | 20 | +334.47 | +16.72 |
| mean_rev | 7 | -90.25 | -12.89 |

### LINK (baseline: 42 trades, ret -2.06%, IS-60d $+69.41 / OOS-30d $+13.08)

**atr_pct:**
| bucket | n | pnl$ | per-trade$ |
|---|---|---|---|
| high | 23 | +286.80 | +12.47 |
| low | 5 | -22.47 | -4.49 |
| mid | 12 | -81.07 | -6.76 |

**trend_v_ema200:**
| bucket | n | pnl$ | per-trade$ |
|---|---|---|---|
| above_ema200 | 39 | +211.18 | +5.41 |
| below_ema200 | 1 | -27.92 | -27.92 |

**ema20_slope:**
| bucket | n | pnl$ | per-trade$ |
|---|---|---|---|
| rising | 40 | +183.26 | +4.58 |

**rsi:**
| bucket | n | pnl$ | per-trade$ |
|---|---|---|---|
| overbought | 36 | +105.10 | +2.92 |
| neutral | 4 | +78.16 | +19.54 |

**bbw_pct:**
| bucket | n | pnl$ | per-trade$ |
|---|---|---|---|
| high | 21 | +637.82 | +30.37 |
| low | 7 | -169.42 | -24.20 |
| mid | 12 | -285.14 | -23.76 |

**hurst:**
| bucket | n | pnl$ | per-trade$ |
|---|---|---|---|
| trending | 32 | +323.75 | +10.12 |
| mean_rev | 8 | -140.49 | -17.56 |

### AVAX (baseline: 39 trades, ret -0.80%, IS-60d $+280.49 / OOS-30d $-69.98)

**atr_pct:**
| bucket | n | pnl$ | per-trade$ |
|---|---|---|---|
| high | 19 | +225.29 | +11.86 |
| mid | 9 | +118.25 | +13.14 |
| low | 10 | -68.22 | -6.82 |

**trend_v_ema200:**
| bucket | n | pnl$ | per-trade$ |
|---|---|---|---|
| above_ema200 | 38 | +275.32 | +7.25 |

**ema20_slope:**
| bucket | n | pnl$ | per-trade$ |
|---|---|---|---|
| rising | 38 | +275.32 | +7.25 |

**rsi:**
| bucket | n | pnl$ | per-trade$ |
|---|---|---|---|
| overbought | 37 | +300.23 | +8.11 |
| neutral | 1 | -24.91 | -24.91 |

**bbw_pct:**
| bucket | n | pnl$ | per-trade$ |
|---|---|---|---|
| high | 19 | +190.71 | +10.04 |
| mid | 12 | +85.73 | +7.14 |
| low | 7 | -1.12 | -0.16 |

**hurst:**
| bucket | n | pnl$ | per-trade$ |
|---|---|---|---|
| trending | 26 | +245.98 | +9.46 |
| mean_rev | 12 | +29.34 | +2.45 |

### ARB (baseline: 42 trades, ret -2.80%, IS-60d $+413.91 / OOS-30d $-545.54)

**atr_pct:**
| bucket | n | pnl$ | per-trade$ |
|---|---|---|---|
| mid | 15 | +113.10 | +7.54 |
| low | 9 | +11.53 | +1.28 |
| high | 18 | -256.26 | -14.24 |

**trend_v_ema200:**
| bucket | n | pnl$ | per-trade$ |
|---|---|---|---|
| below_ema200 | 4 | +227.07 | +56.77 |
| above_ema200 | 38 | -358.70 | -9.44 |

**ema20_slope:**
| bucket | n | pnl$ | per-trade$ |
|---|---|---|---|
| rising | 42 | -131.63 | -3.13 |

**rsi:**
| bucket | n | pnl$ | per-trade$ |
|---|---|---|---|
| neutral | 1 | -5.92 | -5.92 |
| overbought | 41 | -125.71 | -3.07 |

**bbw_pct:**
| bucket | n | pnl$ | per-trade$ |
|---|---|---|---|
| high | 24 | +178.59 | +7.44 |
| low | 7 | -18.76 | -2.68 |
| mid | 11 | -291.46 | -26.50 |

**hurst:**
| bucket | n | pnl$ | per-trade$ |
|---|---|---|---|
| trending | 26 | +176.72 | +6.80 |
| mean_rev | 16 | -308.35 | -19.27 |

### DOGE (baseline: 47 trades, ret +0.46%, IS-60d $+136.66 / OOS-30d $+221.19)

**atr_pct:**
| bucket | n | pnl$ | per-trade$ |
|---|---|---|---|
| high | 29 | +349.38 | +12.05 |
| mid | 11 | +56.06 | +5.10 |
| low | 5 | -104.46 | -20.89 |

**trend_v_ema200:**
| bucket | n | pnl$ | per-trade$ |
|---|---|---|---|
| above_ema200 | 44 | +336.27 | +7.64 |
| below_ema200 | 1 | -35.29 | -35.29 |

**ema20_slope:**
| bucket | n | pnl$ | per-trade$ |
|---|---|---|---|
| rising | 45 | +300.98 | +6.69 |

**rsi:**
| bucket | n | pnl$ | per-trade$ |
|---|---|---|---|
| overbought | 45 | +300.98 | +6.69 |

**bbw_pct:**
| bucket | n | pnl$ | per-trade$ |
|---|---|---|---|
| high | 30 | +489.33 | +16.31 |
| mid | 9 | -46.21 | -5.13 |
| low | 6 | -142.14 | -23.69 |

**hurst:**
| bucket | n | pnl$ | per-trade$ |
|---|---|---|---|
| trending | 33 | +190.91 | +5.79 |
| mean_rev | 12 | +110.07 | +9.17 |

## Top combined regimes per symbol

### BTC
| regime | n | wins | pnl$ | longs | shorts |
|---|---|---|---|---|---|
| above_ema200|atr_high|trend_rising | 14 | 8 | +493.77 | 0 | 14 |
| below_ema200|atr_high|trend_rising | 1 | 0 | -23.22 | 0 | 1 |
| above_ema200|atr_low|trend_rising | 10 | 3 | -90.96 | 0 | 10 |
| above_ema200|atr_mid|trend_rising | 8 | 1 | -169.57 | 0 | 8 |

### ETH
| regime | n | wins | pnl$ | longs | shorts |
|---|---|---|---|---|---|
| above_ema200|atr_high|trend_rising | 23 | 9 | +569.03 | 0 | 23 |
| above_ema200|atr_low|trend_rising | 7 | 3 | +87.18 | 0 | 7 |
| below_ema200|atr_low|trend_rising | 1 | 0 | -9.60 | 0 | 1 |
| below_ema200|atr_high|trend_rising | 2 | 0 | -65.71 | 0 | 2 |
| above_ema200|atr_mid|trend_rising | 6 | 1 | -124.23 | 0 | 6 |

### SOL
| regime | n | wins | pnl$ | longs | shorts |
|---|---|---|---|---|---|
| above_ema200|atr_high|trend_rising | 18 | 6 | +341.12 | 0 | 18 |
| above_ema200|atr_low|trend_rising | 3 | 1 | -15.12 | 0 | 3 |
| above_ema200|atr_mid|trend_rising | 6 | 2 | -81.78 | 0 | 6 |

### LINK
| regime | n | wins | pnl$ | longs | shorts |
|---|---|---|---|---|---|
| above_ema200|atr_high|trend_rising | 23 | 7 | +286.80 | 0 | 23 |
| above_ema200|atr_low|trend_rising | 5 | 1 | -22.47 | 0 | 5 |
| below_ema200|atr_mid|trend_rising | 1 | 0 | -27.92 | 0 | 1 |
| above_ema200|atr_mid|trend_rising | 11 | 4 | -53.15 | 0 | 11 |

### AVAX
| regime | n | wins | pnl$ | longs | shorts |
|---|---|---|---|---|---|
| above_ema200|atr_high|trend_rising | 19 | 5 | +225.29 | 0 | 19 |
| above_ema200|atr_mid|trend_rising | 9 | 4 | +118.25 | 0 | 9 |
| above_ema200|atr_low|trend_rising | 10 | 2 | -68.22 | 0 | 10 |

### ARB
| regime | n | wins | pnl$ | longs | shorts |
|---|---|---|---|---|---|
| below_ema200|atr_mid|trend_rising | 3 | 1 | +148.03 | 0 | 3 |
| below_ema200|atr_low|trend_rising | 1 | 1 | +79.04 | 0 | 1 |
| above_ema200|atr_mid|trend_rising | 12 | 4 | -34.93 | 0 | 12 |
| above_ema200|atr_low|trend_rising | 8 | 2 | -67.51 | 0 | 8 |
| above_ema200|atr_high|trend_rising | 18 | 4 | -256.26 | 0 | 18 |

### DOGE
| regime | n | wins | pnl$ | longs | shorts |
|---|---|---|---|---|---|
| above_ema200|atr_high|trend_rising | 29 | 9 | +349.38 | 0 | 29 |
| above_ema200|atr_mid|trend_rising | 11 | 5 | +56.06 | 0 | 11 |
| below_ema200|atr_low|trend_rising | 1 | 0 | -35.29 | 0 | 1 |
| above_ema200|atr_low|trend_rising | 4 | 1 | -69.17 | 0 | 4 |