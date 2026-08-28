# Trend vs Mean-Reversion Regime Classification

**Status:** research brief for WolfPack regime classifier upgrade
**Target data:** 1h OHLCV candles, 7 crypto perpetual pairs, real-time rolling
**Goal:** replace crude ATR-percentile "ranging" detector with a statistically defensible TREND_SCORE that prevents `mean_reversion` strategies from firing inside slow drifts.

---

## Executive summary

Three tests are most actionable for crypto 1h data and cheap to compute on a rolling window:

1. **Half-life of mean reversion (OU / AR(1) fit)** — the single most actionable number because it has a direct physical unit (bars) and can be compared against your lookback. Trend when `half_life > lookback` or negative; mean-revert when `half_life < lookback/3`.
2. **Hurst exponent (simplified variance-of-lagged-differences)** — cheap, noisy alone, but a good ensemble member with bias-aware thresholds `H < 0.43` revert / `H > 0.57` trend.
3. **Lag-1 autocorrelation of log returns** — near-zero-cost sanity check that is surprisingly informative on 1h crypto because microstructure noise is weaker than on intraday equities.

Stationarity tests (ADF/KPSS) are **not recommended as the primary filter** — they answer a different question (unit root vs trend-stationary) and on 1h crypto the low-power / structural-break problems dominate. Lo-MacKinlay variance ratio is academically the cleanest but is noisier on small rolling windows than a simple Hurst+half-life combo.

Recommended ensemble: weighted blend of `half_life_score + hurst_score + autocorr_score` into a single `TREND_SCORE ∈ [-1, +1]`, refreshed every 5 bars on a 200-bar window. Hard-gate `mean_reversion` strategies on `TREND_SCORE < -0.2`.

---

## Test 1: Hurst exponent

### Formula / computation

Simplified variance-of-lagged-differences estimator (the one used in Mottl's `hurst` library and most QuantConnect / TradingView Pine implementations):

```
for lag in lags:
    tau[lag] = sqrt( std( x[lag:] - x[:-lag] ) )
slope, _ = polyfit(log(lags), log(tau), 1)
H = 2 * slope
```

R/S analysis (Mandelbrot) is equivalent in spirit but slower and more biased on short windows. The simplified estimator on log-prices is the standard shortcut in crypto Pine Script / QC forums.

### Optimal lookback for crypto 1h

- **Lookback window:** 200 bars (≈ 8.3 days of 1h data). This is long enough to get a stable H and short enough to track regime shifts. Robot Wealth and QuantConnect community posts converge on 100–300 bars for intraday data; 200 is the sweet spot.
- **Lag range:** `lags ∈ [2, 20]`. The default in Mottl's library and MATLAB reference implementations. Critically — Robot Wealth's own analysis shows lag 2–20 gives a fundamentally different answer than lag 300–400 on the same series (0.436 vs 0.668 on SPY). For a 200-bar window the 2–20 band is the only one that fits without running out of data.
- **Refresh:** recompute every 5 bars, not every bar — the estimator is noisy and bar-by-bar refresh produces chattery regime flips.

### Actionable thresholds (bias-aware)

The textbook `H < 0.5 / H > 0.5` is wrong in practice because R/S and simplified estimators have a **known upward bias in finite samples** (Anis-Lloyd correction literature; confirmed by multiple crypto Pine Script indicators that widen the neutral band).

- `H < 0.43` → mean-reverting (strong enough to risk a reversion entry)
- `0.43 ≤ H ≤ 0.57` → neutral / noise (do nothing regime-driven)
- `H > 0.57` → trending

The HM2 Hurst Exponent Channel on TradingView hard-codes 0.45 / 0.55 as trend-lock thresholds. 0.43 / 0.57 is slightly more conservative and appropriate for crypto where microstructure noise inflates H.

### Known issues

- **Upward bias** on windows < 300 bars — pre-computed correction tables exist but for a 200-bar window the fixed 0.57 threshold absorbs it.
- **Lag-band sensitivity** — Robot Wealth showed lag band dominates the answer more than the window itself. Fix lags and never tune them per-symbol.
- **Illiquid crypto microstructure noise** inflates estimates; prefer log-price over raw price.
- **Random walks with visible trends** can show `H ≈ 0.5` — you cannot sanity-check visually.

### Python library

`hurst` by Mottl (`pip install hurst`): `compute_Hc(series, kind='price', simplified=True, min_window=10)`. For real-time we'll inline the simplified variant (10 lines of numpy) to avoid the library call overhead on every refresh.

### Sources

- https://github.com/Mottl/hurst
- https://robotwealth.com/demystifying-the-hurst-exponent-part-2/
- https://www.tradingview.com/script/2CGo9sKp-HM2-Hurst-Exponent-Channel/
- https://letianzj.github.io/mean-reversion.html

---

## Test 2: Variance Ratio (Lo-MacKinlay 1988)

### Formula / computation

```
VR(k) = Var(r_t(k)) / (k * Var(r_t(1)))
Z(k)  = (VR(k) - 1) / sqrt(phi(k))
```

where `r_t(k)` is the k-period log return. Under homoscedastic null:

```
phi(k)_homo = 2 * (2k - 1) * (k - 1) / (3 * k * T)
```

Heteroscedasticity-robust version (the one you want for crypto) replaces this with a sum of weighted squared-return autocovariances — see Lo-MacKinlay 1988 eq. 18 or the `vrtest` R package / Mingze Gao's Python port.

### Optimal parameters for crypto 1h

- **k values:** `[2, 4, 8, 16]`. Standard daily choice is `(2, 5, 10, 20, 40)`; for hourly perps compressing by ~2.5x lands at 2/4/8/16. Keeps the longest horizon ≈ 2/3 of a day, well inside the 200-bar window.
- **Window T:** 200 bars minimum. Finite-sample size distortion is severe below T=100 per Lo-MacKinlay's own Monte Carlo; at T=200 the heteroscedasticity-robust version is usable.
- **p-value cutoff:** two-sided `|Z(k)| > 1.96` (5%) to flag non-random-walk. Direction: `VR(k) > 1` ⇒ positive autocorr ⇒ trend. `VR(k) < 1` ⇒ negative autocorr ⇒ revert.
- **Always use the HET version** for crypto — volatility clustering breaks the iid version.

### Is it noisy on hourly crypto?

Yes. Kim (2009) showed the automatic VR test has **significant size distortion** under heteroscedasticity in small samples, and wild-bootstrap is the recommended fix — but wild-bootstrap on every 5-bar refresh is too expensive for real-time. Our plan: use VR(k) only as a tiebreaker between Hurst and half-life when they disagree, not as a primary input.

### Known issues

- Size distortion in small samples with vol clustering (crypto = worst case)
- Single-k tests under-power vs multi-k; aggregating across k is statistically messy
- Sensitive to outliers and jumps — crypto has both

### Python library

No perfect Python equivalent of R's `vrtest`. Options: (a) Lautaro Parada's `variance-test` GitHub repo, (b) `arch` package has variance ratio utilities, (c) hand-roll from numpy in ~30 lines (easiest for our hot path).

### Sources

- https://mingze-gao.com/posts/lomackinlay1988/
- https://github.com/LautaroParada/variance-test
- https://www.nber.org/papers/t0066 (Lo-MacKinlay finite-sample Monte Carlo)
- https://www.sciencedirect.com/science/article/abs/pii/S154461230900018X (Kim 2009 wild bootstrap)

---

## Test 3: Half-life of mean reversion

### Formula / computation

Fit AR(1) via OLS on first-differences against the lagged level (equivalent to OU discrete-time fit):

```
delta_y = y[1:] - y[:-1]
y_lag   = y[:-1]
# OLS: delta_y = alpha + lambda * y_lag + eps
lambda_hat = OLS slope
half_life  = -ln(2) / lambda_hat
```

If `lambda_hat >= 0`: the series is not mean-reverting (random walk or explosive) — treat as trending, `half_life = +inf`.

### Optimal parameters for crypto 1h

- **Fit window:** 200 bars (same as Hurst, reuse the buffer).
- **Input series:** log price, NOT raw price — de-scales across the 7 pairs and kills level effects.
- **Refresh:** every 5 bars.

### Actionable thresholds

Half-life is beautifully interpretable — it has units of bars.

- `half_life < 20 bars` → strong mean-revert (reversion completes in < 1 day; `mean_reversion` strategies OK)
- `20 ≤ half_life < 60` → mild mean-revert (fade the extremes, but expect slow fills)
- `60 ≤ half_life < 200` → basically random walk within our window
- `half_life ≥ 200` or `lambda_hat >= 0` → trending (do NOT fire reversion strategies)

The `half_life > window` rule is from pairs-trading folklore: if the OU half-life exceeds your holding window, the mean never arrives. Flare9x's SPY example landed at 11.24 days (~270 bars on 1h) — clearly not mean-reverting over a short window.

### Known issues

- **One-parameter OLS is optimistic.** Hudson & Thames documents known calibration caveats for OU on real data.
- **Assumes linearity** — crypto regime shifts break this, but that's fine because we're refreshing every 5 bars.
- **Needs de-trending** for assets with a strong drift — we handle by fitting on log returns' running mean zero-adjusted series, or simply accept that trending periods produce `lambda >= 0` and correctly classify as trend.
- Can flip sign noisily near zero — apply a small deadband around `lambda = 0`.

### Python library

Pure numpy. Zero dependencies. The regression is a 2-column OLS — `np.linalg.lstsq` in 3 lines.

### Sources

- https://flare9xblog.wordpress.com/2017/09/27/half-life-of-mean-reversion-ornstein-uhlenbeck-formula-for-mean-reverting-process/
- https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/cointegration_approach/half_life.html
- https://hudsonthames.org/caveats-in-calibrating-the-ou-process/
- https://letianzj.github.io/mean-reversion.html

---

## Test 4: Autocorrelation (lag 1-5)

### Formula / computation

```
r = np.diff(np.log(prices))
rho[k] = corrcoef(r[:-k], r[k:])[0,1]  for k in 1..5
```

Standard error under null `≈ 1/sqrt(T)`. At T=200, 2-sigma band ≈ ±0.14.

### Optimal parameters

- **Window:** 200 bars of log returns.
- **Lags:** 1, 2, 3, 5 (skip 4 — classic practice).
- **Refresh:** every bar (cheap enough).

### Actionable thresholds

- `rho[1] > +0.10` → momentum regime (trending)
- `rho[1] < -0.10` → reversion regime
- `|rho[1]| < 0.10` → noise band
- Boost confidence if `rho[2]`, `rho[3]` agree in sign

Crypto 1h lag-1 autocorrelations are typically mildly positive during trends and mildly negative during ranging consolidations — see the Panoptic spot-vol study and the Lewellen momentum-autocorrelation paper.

### Known issues

- Single lag is weak — use the pattern across lags 1–5
- Jumps dominate the correlation and produce spurious zeros
- Fails completely during news-driven gaps

### Python library

`numpy.corrcoef` or `statsmodels.tsa.stattools.acf`. Prefer inline numpy.

### Sources

- https://blog.quantinsti.com/autocorrelation/
- https://faculty.tuck.dartmouth.edu/images/uploads/faculty/jonathan-lewellen/Momentum.pdf
- https://panoptic.xyz/research/spot-vol-correlation

---

## Test 5: ADF / KPSS stationarity

### Why this is in the paper but shouldn't be in our classifier

ADF tests the null of a unit root; KPSS tests the null of trend-stationarity. They answer `is this series stationary?` — not `is it trending vs mean-reverting within my trading horizon?`. A slow drift with tiny noise is **unit-root non-stationary** (ADF fails to reject) AND yet profitable for a momentum strategy. That is exactly WolfPack's current failure mode.

### Known issues

- **Low power in small samples** — statsmodels docs warn about this explicitly
- **Structural break blindness** — crypto has regime shifts every few days, breaks the test
- **Contradictory results** — ADF and KPSS frequently disagree; interpreting the 4-cell matrix adds complexity without a clean actionable output
- **Cointegration, not regime** — the canonical use is testing pair spreads, not single-asset classification

### Recommendation

Do not use ADF or KPSS in the primary classifier. If we ever add pair-trade strategies for cross-asset spreads, ADF becomes appropriate there. For single-asset regime: skip.

### Sources

- https://www.statsmodels.org/dev/examples/notebooks/generated/stationarity_detrending_adf_kpss.html
- https://0xboz.github.io/blog/how-to-run-stationarity-tests-on-cryptocurrencies-trading-data/

---

## Recommended ensemble

Collapse the three primary tests into a single `TREND_SCORE ∈ [-1, +1]`. Negative = mean-reverting, positive = trending, zero = noise.

### Sub-scores (each in `[-1, +1]`)

```
hurst_score    = clip( (H - 0.50) / 0.10 , -1, +1 )
# H=0.40 → -1.0, H=0.50 → 0.0, H=0.60 → +1.0

halflife_score:
    if lambda_hat >= 0:      halflife_score = +1.0   # explosive / trend
    elif half_life > 200:    halflife_score = +0.8
    elif half_life > 60:     halflife_score = +0.3
    elif half_life > 20:     halflife_score = -0.4
    else:                    halflife_score = -1.0

autocorr_score = clip( rho[1] / 0.15 , -1, +1 )
```

### Weighted blend

```
TREND_SCORE = 0.45 * halflife_score + 0.35 * hurst_score + 0.20 * autocorr_score
```

Half-life gets the highest weight because it has a direct physical unit (bars) and because Hurst alone has repeatedly been the cause of misclassification in retail quant literature.

### Gating rules for strategies

- `TREND_SCORE > +0.35` → allow `trend_continuation`, `breakout`, `trend_pullback`; BLOCK `mean_reversion`
- `-0.20 ≤ TREND_SCORE ≤ +0.35` → neutral; trend strategies only if other filters (ATR, regime) green
- `TREND_SCORE < -0.20` → allow `mean_reversion`, `range_fade`; BLOCK `trend_continuation`

The asymmetric band (-0.20 vs +0.35) is deliberate: **false-positive mean-reversion entries are the current bleeder**, so we bias toward blocking reversion unless the evidence is clear.

### Refresh schedule

- Full recompute: every 5 bars (12 times/day)
- Lightweight autocorr recompute: every bar
- Per-wallet: no — this is a market property, computed once per pair per refresh and cached

---

## Code sketch (pseudocode, numpy only)

```python
import numpy as np

def trend_score(log_prices: np.ndarray, window: int = 200) -> dict:
    """
    Inputs:  log_prices = 1-D np.ndarray of last `window+1` log prices.
    Output:  dict with half_life, hurst, rho1, trend_score in [-1, +1].
    """
    x = log_prices[-(window + 1):]
    r = np.diff(x)                    # log returns, len = window

    # ---- Test 1: Hurst (simplified, lags 2..20) ----
    lags = np.arange(2, 21)
    tau  = np.array([
        np.sqrt(np.std(x[lag:] - x[:-lag])) for lag in lags
    ])
    slope_h = np.polyfit(np.log(lags), np.log(tau), 1)[0]
    H = 2.0 * slope_h
    hurst_score = np.clip((H - 0.50) / 0.10, -1.0, 1.0)

    # ---- Test 2: Half-life via OLS AR(1) on levels ----
    y_lag   = x[:-1]
    delta_y = np.diff(x)
    A = np.column_stack([np.ones_like(y_lag), y_lag])
    coefs, *_ = np.linalg.lstsq(A, delta_y, rcond=None)
    lam = coefs[1]
    if lam >= -1e-6:
        half_life = float("inf")
        hl_score  = 1.0
    else:
        half_life = -np.log(2) / lam
        if half_life > 200:  hl_score = 0.8
        elif half_life > 60: hl_score = 0.3
        elif half_life > 20: hl_score = -0.4
        else:                hl_score = -1.0

    # ---- Test 3: Lag-1 autocorrelation of returns ----
    r0, r1 = r[:-1], r[1:]
    rho1 = float(np.corrcoef(r0, r1)[0, 1])
    ac_score = np.clip(rho1 / 0.15, -1.0, 1.0)

    # ---- Ensemble ----
    trend_score = 0.45 * hl_score + 0.35 * hurst_score + 0.20 * ac_score

    return {
        "H":            float(H),
        "half_life":    float(half_life),
        "lambda":       float(lam),
        "rho1":         rho1,
        "hurst_score":  float(hurst_score),
        "hl_score":     float(hl_score),
        "ac_score":     float(ac_score),
        "trend_score":  float(trend_score),
    }
```

~55 lines, numpy-only, single pass. Call once per pair every 5 bars. Cache `trend_score` in the regime classifier and gate `mean_reversion` strategies on `trend_score >= -0.20`.

---

## Crypto-specific adjustments

1. **Always log-prices**, never raw — kills the cross-pair scale differences and stabilizes the OU fit.
2. **200-bar window** (not 500–1000 as in equity lit) — crypto regime shifts are faster, longer windows smear regimes together.
3. **Widen Hurst neutral band** (0.43/0.57 not 0.45/0.55 or 0.5/0.5) because microstructure noise inflates the estimate on illiquid perps.
4. **Skip wild-bootstrap VR test** for real-time — too expensive, and Hurst + half-life cover the same space at a fraction of the cost.
5. **Refresh every 5 bars, not every bar** — the estimators are noisy and chattery regime flips destroy strategies. 5 bars ≈ 5 hours is fast enough.
6. **Never trust a single test** — this is the entire motivation for the ensemble. Any one of Hurst, half-life, autocorr can and will give a wrong answer on a given bar; combined they're robust.

---

## Sources

- Lo & MacKinlay, "Stock Market Prices Do Not Follow Random Walks," *Review of Financial Studies* (1988) — https://www.nber.org/papers/t0066
- Lo & MacKinlay (1989) "Size and Power of the Variance Ratio Test" — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=396681
- Kim (2009) "Automatic variance ratio test under conditional heteroskedasticity" — https://www.sciencedirect.com/science/article/abs/pii/S154461230900018X
- Mingze Gao, "Variance Ratio Test — Lo & MacKinlay (1988)" — https://mingze-gao.com/posts/lomackinlay1988/
- Lautaro Parada, `variance-test` GitHub — https://github.com/LautaroParada/variance-test
- Mottl, `hurst` Python library — https://github.com/Mottl/hurst
- Robot Wealth, "Demystifying the Hurst Exponent Part 2" — https://robotwealth.com/demystifying-the-hurst-exponent-part-2/
- Robot Wealth, "Rolling and Expanding Windows" — https://robotwealth.com/rolling-and-expanding-windows-for-dummies/
- Hudson & Thames, "Half-life of Mean Reversion" — https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/cointegration_approach/half_life.html
- Hudson & Thames, "Caveats in Calibrating the OU Process" — https://hudsonthames.org/caveats-in-calibrating-the-ou-process/
- Flare9x, "Half life of Mean Reversion – OU Formula" — https://flare9xblog.wordpress.com/2017/09/27/half-life-of-mean-reversion-ornstein-uhlenbeck-formula-for-mean-reverting-process/
- Letian Zhang, "Mean Reversion" — https://letianzj.github.io/mean-reversion.html
- TradingView HM2 Hurst Exponent Channel — https://www.tradingview.com/script/2CGo9sKp-HM2-Hurst-Exponent-Channel/
- Harbourfront Quant, "Detecting Trends and Risks in Crypto Using the Hurst Exponent" — https://harbourfrontquant.substack.com/p/detecting-trends-and-risks-in-crypto
- MDPI 2025, "Stylized Facts of High-Frequency Bitcoin Time Series" — https://www.mdpi.com/2504-3110/9/10/635
- Mensi et al. (2025) "Hourly Asymmetric Multifractality and Dynamic Efficiency in Cryptocurrency Markets" — https://onlinelibrary.wiley.com/doi/10.1111/1467-8454.12390
- Panoptic, "Spot-Vol Correlation & Risk Reversals" — https://panoptic.xyz/research/spot-vol-correlation
- Velasquez, "Momentum or Reversion? Detecting Predictability Zones" — https://medium.com/@crisvelasquez/momentum-or-reversion-detecting-predictability-zones-5143ef9eddd2
- Lewellen, "Momentum and Autocorrelation in Stock Returns" — https://faculty.tuck.dartmouth.edu/images/uploads/faculty/jonathan-lewellen/Momentum.pdf
- statsmodels ADF/KPSS notebook — https://www.statsmodels.org/dev/examples/notebooks/generated/stationarity_detrending_adf_kpss.html
- 0xboz, "How to Run Stationarity Tests on Cryptocurrencies" — https://0xboz.github.io/blog/how-to-run-stationarity-tests-on-cryptocurrencies-trading-data/
- MDPI "Microstructure noise and idiosyncratic volatility anomalies in cryptocurrencies" — https://link.springer.com/article/10.1007/s10479-022-04568-9
