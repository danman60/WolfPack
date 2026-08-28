# Phase 12: HODL + Drawdown Harvester — last 90 days

**Window**: last 540 4h-bars (90 days). **Cost**: 10.0 bps round-trip.

**Architecture**: HODL captures bull moves; Leg 1 (funding-z<-2 → long, 3% SL / 2% TP / 48h) harvests during sideways/drawdowns.

**Hypothesis**: 80/20 (or 90/10) blend matches HODL return with lower drawdown.

## Per-symbol total return
| sym | 100% HODL | 100% Leg1 | 90/10 | 80/20 | 70/30 |
|---|---|---|---|---|---|
| BTC | +13.80% | +0.00% | +12.42% | +11.04% | +9.66% |
| ETH | +11.89% | +0.00% | +10.70% | +9.51% | +8.33% |
| SOL | +1.69% | +0.00% | +1.52% | +1.35% | +1.18% |
| LINK | +12.24% | +0.00% | +11.02% | +9.80% | +8.57% |
| AVAX | +2.94% | +0.00% | +2.64% | +2.35% | +2.06% |
| ARB | +6.36% | +0.00% | +5.72% | +5.09% | +4.45% |
| DOGE | +10.57% | +0.00% | +9.51% | +8.45% | +7.40% |

## Per-symbol max drawdown
| sym | 100% HODL | 100% Leg1 | 90/10 | 80/20 | 70/30 |
|---|---|---|---|---|---|
| BTC | 11.87% | 0.00% | 10.74% | 9.60% | 8.45% |
| ETH | 15.64% | 0.00% | 14.25% | 12.82% | 11.36% |
| SOL | 18.56% | 0.00% | 16.87% | 15.14% | 13.38% |
| LINK | 15.25% | 0.00% | 13.88% | 12.47% | 11.04% |
| AVAX | 18.12% | 0.00% | 16.51% | 14.85% | 13.15% |
| ARB | 27.63% | 0.00% | 24.92% | 22.20% | 19.47% |
| DOGE | 23.66% | 0.00% | 21.62% | 19.51% | 17.34% |

## Per-symbol Sharpe (annualized)
| sym | 100% HODL | 100% Leg1 | 90/10 | 80/20 | 70/30 |
|---|---|---|---|---|---|
| BTC | +1.16 | +0.00 | +1.17 | +1.17 | +1.18 |
| ETH | +0.77 | +0.00 | +0.78 | +0.78 | +0.78 |
| SOL | +0.11 | +0.00 | +0.11 | +0.11 | +0.11 |
| LINK | +0.78 | +0.00 | +0.79 | +0.79 | +0.80 |
| AVAX | +0.19 | +0.00 | +0.19 | +0.19 | +0.19 |
| ARB | +0.32 | +0.00 | +0.32 | +0.33 | +0.33 |
| DOGE | +0.62 | +0.00 | +0.62 | +0.62 | +0.63 |
- 100% HODL: avg ret=+8.50%, avg maxDD=18.68%, avg Sharpe=+0.56
- 100% Leg1: avg ret=+0.00%, avg maxDD=0.00%, avg Sharpe=+0.00
- 90/10: avg ret=+7.65%, avg maxDD=16.97%, avg Sharpe=+0.57
- 80/20: avg ret=+6.80%, avg maxDD=15.23%, avg Sharpe=+0.57
- 70/30: avg ret=+5.95%, avg maxDD=13.45%, avg Sharpe=+0.57