# Phase 11: 3-leg portfolio with Fixes A+B+C — last 90 days

**Fixes applied:**
- A: hysteresis — 3 confirming bars to change regime (kills whipsaw)
- B: Leg 2/3 simplified — hold full position while regime active, no ladder/chandelier
- C: leading classifier — price>SMA200 + 7d_return>+2% + funding>0 → BULL (mirror for BEAR)

**Window**: last 540 4h-bars (90 days). **Cost**: 10.0 bps round-trip.

## Per-symbol
| sym | regime dist (hyst) | transitions | L1 % | L2 % | L3 % | Portfolio % | HODL % | SMA200 % | beats HODL | beats SMA |
|---|---|---|---|---|---|---|---|---|---|---|
| BTC | B=101 S=380 D=59 U=0 | 34 | +1.25 | -8.14 | -5.34 | -4.08 | +13.72 | +4.38 | ✗ | ✗ |
| ETH | B=114 S=399 D=27 U=0 | 27 | -1.00 | -14.73 | -8.90 | -8.21 | +11.86 | -8.35 | ✗ | ✓ |
| SOL | B=37 S=372 D=131 U=0 | 24 | +0.04 | -1.17 | -9.12 | -3.42 | +1.79 | -18.76 | ✗ | ✓ |
| LINK | B=122 S=418 D=0 U=0 | 19 | +1.25 | -16.38 | +0.00 | -5.04 | +12.31 | -9.98 | ✗ | ✓ |
| AVAX | B=100 S=408 D=32 U=0 | 29 | -0.04 | -16.69 | -14.66 | -10.47 | +2.91 | -21.79 | ✗ | ✓ |
| ARB | B=54 S=363 D=123 U=0 | 32 | -0.19 | +9.38 | -13.43 | -1.41 | +6.69 | +13.62 | ✗ | ✗ |
| DOGE | B=145 S=303 D=92 U=0 | 30 | +0.80 | -0.52 | +4.57 | +1.62 | +10.72 | -14.49 | ✗ | ✓ |

## Aggregate
- Portfolio avg: **-4.43%**
- HODL avg: +8.57%
- SMA200 timing avg: -7.91%
- Beats HODL: **0/7**
- Beats SMA200: **5/7**