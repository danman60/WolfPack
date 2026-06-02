# GEX-Proxy Kill-Test Spike

Vol-regime proxy for GEX. 3 symbols x 1h candles (requested 2160). RV window 24b, trend baseline 168b, warmup 192b.

Proxy: **mr-regime** = positive-gamma proxy = low/falling realized vol (expect mean-reversion). **trend-regime** = negative-gamma proxy = high/rising vol (expect momentum).

## (a) Model-free: lag-1 autocorr of forward 1h returns by regime
Negative autocorr = mean-reverting; positive = trending. Proxy works if mr-regime autocorr is *more negative* than trend-regime.

| symbol | mr-regime autocorr (n) | trend-regime autocorr (n) | gap (trend - mr) |
|---|---|---|---|
| BTC | -0.0083 (983) | -0.0068 (984) | +0.0015 |
| ETH | -0.0304 (983) | +0.0132 (984) | +0.0436 |
| SOL | +0.0487 (983) | +0.0089 (984) | -0.0398 |

## (b) Strategy-conditioned: per-regime expectancy ($/trade)

### mean_reversion
| symbol | mr-regime n/WR/exp$ | trend-regime n/WR/exp$ |
|---|---|---|
| BTC | 7 / 14% / -20.02 | 17 / 41% / +10.96 |
| ETH | 8 / 38% / -0.12 | 17 / 53% / +24.66 |
| SOL | 4 / 25% / -5.34 | 13 / 31% / -1.79 |

### range_breakout
| symbol | mr-regime n/WR/exp$ | trend-regime n/WR/exp$ |
|---|---|---|
| BTC | 26 / 50% / -0.38 | 35 / 34% / -3.45 |
| ETH | 35 / 34% / -5.29 | 32 / 50% / -0.61 |
| SOL | 33 / 42% / +1.03 | 32 / 38% / -7.05 |

## VERDICT

### FAIL

Effect sizes (averaged across symbols, positive = proxy works as hypothesized):

- Autocorr gap (trend - mr), want > 0.02: **+0.00179** (n=3) -> NO
- mean_reversion expectancy gap (mr - trend), want > 0.0: **-27.88316** (n=2) -> NO
- range_breakout expectancy gap (trend - mr), want > 0.0: **-2.15872** (n=3) -> NO

PASS requires all three checks OK. FAIL if all point wrong/flat. INCONCLUSIVE if mixed or insufficient sample.

### Caveats
- Sample: 2160 1h bars requested (~90 days) per symbol. Short window; one vol epoch.
- Proxy is realized-vol, NOT true dealer gamma. A null result kills the *proxy*, not necessarily true GEX (but removes the cheap justification to buy options history).
- Strategy-conditioned test depends on the in-repo mean_reversion / range_breakout signal logic and trade counts; thin per-regime buckets reduce reliability. (vol_breakout fired only 1-2x/90d on 1h, hence range_breakout for the momentum leg.)