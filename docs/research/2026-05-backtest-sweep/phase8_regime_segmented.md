# Phase 8: regime-segmented funding-squeeze-long

Does funding-z-low-long beat HODL in SIDEWAYS / BEAR markets, even though it loses to BULL HODL?

**Regime classification:** rolling 30d return on the symbol itself. BULL > +10%, BEAR < -10%, else SIDEWAYS.

**Strategy:** enter when 30d funding z < -2.0; exit at first of {3% SL, 2% TP, 48h time-stop}.

**HODL_avg_48h:** mean 48h forward return on bars within the same regime — the proper apples-to-apples HODL baseline.


## BTC

Regime distribution across 28 months: {'SIDEWAYS': 2917, 'UNKNOWN': 180, 'BEAR': 761, 'BULL': 1143}

Total strategy trades: 75

| regime | trades | WR% | strat avg/trade | HODL avg 48h | edge vs HODL |
|---|---|---|---|---|---|
| SIDEWAYS | 42 | 66.7 | +0.46% | +0.05% | **+0.41%** |
| BEAR | 31 | 74.2 | +0.83% | +0.16% | **+0.67%** |

## ETH

Regime distribution across 28 months: {'SIDEWAYS': 1943, 'UNKNOWN': 180, 'BEAR': 1526, 'BULL': 1352}

Total strategy trades: 133

| regime | trades | WR% | strat avg/trade | HODL avg 48h | edge vs HODL |
|---|---|---|---|---|---|
| BULL | 9 | 22.2 | -1.69% | +0.67% | **-2.35%** |
| SIDEWAYS | 51 | 60.8 | -0.01% | -0.07% | **+0.06%** |
| BEAR | 73 | 52.1 | -0.52% | -0.28% | **-0.24%** |

## SOL

Regime distribution across 28 months: {'SIDEWAYS': 1591, 'UNKNOWN': 180, 'BEAR': 1586, 'BULL': 1644}

Total strategy trades: 110

| regime | trades | WR% | strat avg/trade | HODL avg 48h | edge vs HODL |
|---|---|---|---|---|---|
| BULL | 11 | 45.5 | -0.83% | +0.11% | **-0.94%** |
| SIDEWAYS | 41 | 58.5 | -0.13% | +0.41% | **-0.55%** |
| BEAR | 58 | 55.2 | -0.34% | -0.10% | **-0.24%** |

## LINK

Regime distribution across 28 months: {'SIDEWAYS': 1921, 'UNKNOWN': 180, 'BEAR': 1713, 'BULL': 1187}

Total strategy trades: 115

| regime | trades | WR% | strat avg/trade | HODL avg 48h | edge vs HODL |
|---|---|---|---|---|---|
| SIDEWAYS | 45 | 66.7 | +0.32% | -0.02% | **+0.35%** |
| BEAR | 66 | 56.1 | -0.30% | -0.22% | **-0.08%** |

## AVAX

Regime distribution across 28 months: {'SIDEWAYS': 1521, 'UNKNOWN': 180, 'BEAR': 1942, 'BULL': 1358}

Total strategy trades: 148

| regime | trades | WR% | strat avg/trade | HODL avg 48h | edge vs HODL |
|---|---|---|---|---|---|
| BULL | 5 | 60.0 | -0.10% | +0.26% | **-0.36%** |
| SIDEWAYS | 42 | 52.4 | -0.36% | -0.16% | **-0.20%** |
| BEAR | 101 | 57.4 | -0.21% | -0.34% | **+0.13%** |

## ARB

Regime distribution across 28 months: {'SIDEWAYS': 1270, 'UNKNOWN': 180, 'BEAR': 2519, 'BULL': 1032}

Total strategy trades: 136

| regime | trades | WR% | strat avg/trade | HODL avg 48h | edge vs HODL |
|---|---|---|---|---|---|
| BULL | 9 | 44.4 | -0.88% | -0.25% | **-0.63%** |
| SIDEWAYS | 23 | 65.2 | +0.16% | +0.20% | **-0.04%** |
| BEAR | 104 | 51.9 | -0.50% | -0.79% | **+0.29%** |

## DOGE

Regime distribution across 28 months: {'SIDEWAYS': 1622, 'UNKNOWN': 180, 'BEAR': 1855, 'BULL': 1344}

Total strategy trades: 95

| regime | trades | WR% | strat avg/trade | HODL avg 48h | edge vs HODL |
|---|---|---|---|---|---|
| SIDEWAYS | 30 | 66.7 | +0.33% | -0.01% | **+0.34%** |
| BEAR | 61 | 55.7 | -0.31% | -0.25% | **-0.06%** |