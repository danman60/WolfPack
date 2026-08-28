# Phase 4: Edge Provenance Validator Results

**5 hypotheses × 7 symbols × 1 timeframes** = 35 cells.

**Round-trip cost**: 10.0 bps. **Forward horizons**: [1, 4, 12, 24] bars.

**Acceptance gates:**
- Gate 1: t-stat > 2 AND |effect| > 10.0bps AND n >= 30 AND positive direction
- Gate 2: walk-forward IS/OOS same-sign AND OOS effect >= 0.5×IS AND OOS positive
- Gate 3: net Sharpe > 0.5 (annualized) AND cumulative > 0 net of cost
- Gate 4: Gate 1 survives ±20% on every numeric parameter, ≥75% perturbation pass

## Verdict counts
| Gate reached | Count |
|---|---|
| Passed through Gate 4 | 5 |
| Passed through Gate 3 | 0 |
| Passed through Gate 2 | 0 |
| Passed through Gate 1 | 30 |

## Survivors (5 cells passed all 4 gates)
| hypothesis | sym | tf | n | h | mean% | t | Sharpe | cum% | HODL% | beats |
|---|---|---|---|---|---|---|---|---|---|---|
| H3_inside_bar_compression | LINK | 4h | 196 | 4 | +0.613 | 2.85 | 3.99 | +100.5 | -30.5 | ✓ |
| H1_capitulation_flush | AVAX | 4h | 313 | 4 | +0.869 | 3.01 | 3.52 | +240.6 | -69.1 | ✓ |
| H1_capitulation_flush | DOGE | 4h | 307 | 12 | +1.569 | 3.77 | 2.72 | +451.0 | +39.5 | ✓ |
| H1_capitulation_flush | LINK | 4h | 302 | 12 | +1.022 | 2.53 | 1.77 | +278.4 | -30.5 | ✓ |
| H2_blowoff_top | AVAX | 4h | 295 | 24 | +1.397 | 2.71 | 1.40 | +382.7 | -69.1 | ✓ |

## Cells that passed Gate 1 (statistical signal exists)

7 of 35 cells.

| hypothesis | sym | tf | n | h | mean% | t-stat | next_gate_failed | reason |
|---|---|---|---|---|---|---|---|---|
| H1_capitulation_flush | DOGE | 4h | 307 | 12 | +1.569 | 3.77 | passed all |  |
| H1_capitulation_flush | AVAX | 4h | 313 | 4 | +0.869 | 3.01 | passed all |  |
| H3_inside_bar_compression | LINK | 4h | 196 | 4 | +0.613 | 2.85 | passed all |  |
| H2_blowoff_top | AVAX | 4h | 295 | 24 | +1.397 | 2.71 | passed all |  |
| H1_capitulation_flush | BTC | 4h | 330 | 4 | +0.376 | 2.60 | Gate 1 | IS=+0.609% OOS=-0.138% same_sign=False oos_meaningful=False |
| H1_capitulation_flush | LINK | 4h | 302 | 12 | +1.022 | 2.53 | passed all |  |
| H1_capitulation_flush | SOL | 4h | 314 | 12 | +0.883 | 2.48 | Gate 1 | IS=+1.041% OOS=+0.491% same_sign=True oos_meaningful=False |

## By hypothesis — gate funnel
| hypothesis | cells | G1 pass | G2 pass | G3 pass | G4 pass |
|---|---|---|---|---|---|
| H1_capitulation_flush | 7 | 5 | 3 | 3 | 3 |
| H2_blowoff_top | 7 | 1 | 1 | 1 | 1 |
| H3_inside_bar_compression | 7 | 1 | 1 | 1 | 1 |
| H4_volume_climax_reversal | 7 | 0 | 0 | 0 | 0 |
| H5_streak_exhaustion | 7 | 0 | 0 | 0 | 0 |