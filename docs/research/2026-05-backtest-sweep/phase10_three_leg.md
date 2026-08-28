# Phase 10: 3-leg regime portfolio — last 90 days

**Window**: last 540 4h-bars (~90 days). **Cost**: 10.0 bps round-trip.

**Architecture:**
- Regime classifier: 30d return + 200-SMA → BULL/SIDEWAYS/BEAR
- Leg 1: funding-z < -2 → long, exit at first of 3% SL / 2% TP / 48h
- Leg 2: BULL regime entry → long with profit ladder (+5%/+10%/+20% scale-out 25% each), trail last 25% on 3-ATR chandelier
- Leg 3: BEAR regime entry → short with mirror ladder
- Portfolio: equal-weight 1/3 per leg

## Per-symbol results
| sym | regime dist | L1 (n,ret%) | L2 (n,ret%) | L3 (n,ret%) | Portfolio% | HODL% | SMA200 timing% | beats HODL | beats SMA |
|---|---|---|---|---|---|---|---|---|---|
| BTC | B=95 S=292 D=153 U=0 | 13,+1.25 | 7,-0.64 | 0,+0.00 | +0.20 | +13.62 | +4.29 | ✗ | ✗ |
| ETH | B=120 S=267 D=153 U=0 | 17,-1.00 | 19,-4.79 | 0,+0.00 | -1.93 | +11.73 | -8.46 | ✗ | ✓ |
| SOL | B=30 S=343 D=167 U=0 | 7,+0.04 | 9,-2.45 | 4,-0.46 | -0.96 | +1.70 | -18.83 | ✗ | ✓ |
| LINK | B=41 S=352 D=147 U=0 | 19,+1.25 | 10,-1.28 | 1,+0.42 | +0.13 | +12.05 | -10.18 | ✗ | ✓ |
| AVAX | B=26 S=366 D=148 U=0 | 13,-0.04 | 8,-1.92 | 3,-0.46 | -0.81 | +2.78 | -21.89 | ✗ | ✓ |
| ARB | B=144 S=155 D=241 U=0 | 28,-0.19 | 8,+2.60 | 13,-1.10 | +0.44 | +6.71 | +13.65 | ✗ | ✗ |
| DOGE | B=58 S=310 D=172 U=0 | 8,+0.80 | 4,-0.88 | 9,+1.97 | +0.63 | +10.91 | -14.34 | ✗ | ✓ |

## Aggregate (avg across 7 symbols)
- Portfolio avg return: **-0.33%**
- HODL avg return: +8.50%
- SMA200 timing avg return: -7.97%
- Symbols where portfolio beats HODL: **0/7**
- Symbols where portfolio beats SMA200 timing: **5/7**