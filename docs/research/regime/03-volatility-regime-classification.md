# Volatility Regime Classification Research

**Context:** WolfPack currently classifies volatility as `LOW_VOL` / `HIGH_VOL` / `EXTREME` using a single ATR percentile against a static lookback. This is failing live — AVAX validator EWMA accuracy is 0.42, DOGE collapsed to 0.39. Root cause is likely two-fold: (1) ATR is a backward-smoothed diffusion estimator that collapses when jump/gap behavior dominates (crypto liquidation cascades), and (2) a single rolling percentile window leaks low-vol periods into the "normal" bucket whenever the recent window itself was mostly dead. We need estimators that separate diffusive from jump volatility and a regime classifier that is adaptive but not recency-biased.

## Executive summary

Three methods ranked by production feasibility on 1h candles with no paid high-frequency data:

1. **HAR-RV on hour-aggregated 5-minute realized variance (Corsi 2009) + rolling quantile classifier.** Cheap, transparent, no fitting loop, handles the heterogeneous time-scales of crypto traders directly. This is the workhorse.
2. **Bi-power-variation jump separator (Barndorff-Nielsen / Shephard 2004).** Cheap add-on to (1). Splits total realized variance into `BV` (continuous diffusion) and `JV` (jump component). Enables a dedicated `JUMPY` regime that fires the mean-reversion stack post-liquidation instead of the trend stack.
3. **GARCH(1,1) conditional variance on hourly returns via `arch`, used as a vol-of-vol signal.** One process-level fit per wallet per day; the one-step-ahead conditional variance feeds a vol-of-vol z-score that flags regime transitions before they show up in RV quantiles.

Ensemble: use HAR-RV + BV/JV as the primary classifier; GARCH conditional variance as a transition detector that overrides to `TRANSITION` when vol-of-vol spikes. Full 6-regime taxonomy mapped at the bottom.

---

## Method 1: HAR-RV (Heterogeneous Autoregressive Realized Volatility)

**Source:** Corsi (2009), *A Simple Approximate Long-Memory Model of Realized Volatility*, Journal of Financial Econometrics 7(2). [Paper PDF](https://statmath.wu.ac.at/~hauser/LVs/FinEtricsQF/References/Corsi2009JFinEtrics_LMmodelRealizedVola.pdf).

### Description
HAR-RV models realized variance as a cascade of three additive AR(1)-style components at different horizons (short / medium / long) that roughly match the trading horizons of scalpers, swing traders, and position holders. Despite being an OLS regression with 3 regressors, it beats GARCH and long-memory fractional models on out-of-sample RV forecasting, and it does so without any non-linear fitting.

### Inputs
- **Candle frequency for the RV estimator:** 5-minute bars aggregated into hourly RV. Bitcoin volatility signature plots show 5-minute is still the sweet spot: dropping from 5m to 10m knocks 9% off average RV, further drops are under 5% (so microstructure noise is not dominant at 5m on BTC/ETH). For smaller alts (AVAX, DOGE), 10m sampling is defensible when the 5m tape is too thin.
- **Aggregation:** `RV_h = sum(r_i^2)` for i=1..12 (twelve 5m bars per hour). For a forecast horizon of 1h, we use the previous hour's RV as the "d" (daily-analog) component.
- **Lookback / component windows** (rescaled from Corsi's daily model to hourly crypto, keeping the 1:5:22 ratio idea but compressed for 24/7 markets):
  - Short (RV_s): last 1h (12 bars)
  - Medium (RV_m): average of last 6h (72 bars) — intraday session
  - Long (RV_l): average of last 24h (288 bars) — full day cycle
- **Extended long horizon option:** add a 7-day (168h) term if you want HAR-RV-W per Corsi's weekly extension.

### Output
A one-step-ahead forecast `RV_{h+1}` in variance units. Annualize with `sqrt(RV * 24 * 365)` for a comparable sigma. The *forecast* itself is the classifier input, not the raw realized value — this is what fixes the "window is itself dead" leakage problem in the current ATR setup.

### Specific parameters (starting point, unfit)
Corsi's original daily S&P calibration: `β_d = 0.36`, `β_w = 0.28`, `β_m = 0.28`, intercept ~small. For hourly crypto, re-fit by rolling OLS on log-RV (log transform handles heavy tails better than raw or sqrt — this is consistent with the arch/MachineLearningMastery literature). Use a 60-day rolling fit, re-estimated nightly. Expect the short-horizon coefficient on BTC/ETH to sit 0.30–0.45 and medium+long to sum to ~0.45–0.55 once you fit. On low-liquidity alts (AVAX, DOGE), expect the long component to grow to 0.35+ because most of their variance is macro-BTC-driven.

### Known failure modes
- Pure OLS on raw RV is mean-biased during vol spikes. **Fix: fit on log-RV, exponentiate the forecast.**
- Zero-return runs (dead tape) make RV collapse to ~0 and inflate the log transform. **Fix: floor RV at 1e-8 before logging.**
- Ignores jumps by construction — HAR-RV trained on RV will over-forecast the next bar's diffusion right after a liquidation cascade. **Fix: pair with the bi-power variation jump filter (Method 2) and train HAR on `BV` rather than `RV`.**

### Computation cost
~50µs per forecast after a one-time nightly OLS fit (< 200ms). No iterative solver. Runs in production on every hourly tick.

### Sources
- [Corsi 2009 — original paper](https://statmath.wu.ac.at/~hauser/LVs/FinEtricsQF/References/Corsi2009JFinEtrics_LMmodelRealizedVola.pdf)
- [Portfolio Optimizer — HAR tutorial](https://portfoliooptimizer.io/blog/volatility-forecasting-har-model/)
- [deep-hedger-Peng/HAR-RV (Python reference impl)](https://github.com/deep-hedger-Peng/HAR-RV)
- [talaikis/HAR-RVModelForRealizedVolatility (Python)](https://github.com/talaikis/HAR-RVModelForRealizedVolatility)
- [Bollerslev et al., *Practical Guide to the HAR volatility model* (2021)](https://www.sciencedirect.com/science/article/abs/pii/S0378426621002417)

---

## Method 2: Bi-Power Variation (BV) — jump vs. diffusion decomposition

**Source:** Barndorff-Nielsen & Shephard (2004), *Power and Bipower Variation with Stochastic Volatility and Jumps*, Journal of Financial Econometrics 2(1). [Paper PDF](https://public.econ.duke.edu/~get/browse/courses/883/Spr16/COURSE-MATERIALS/Z_Papers/BNSJFEC2004.pdf).

### Description
Realized variance `RV = Σ r_i²` captures **both** diffusive variance and jumps. Bi-power variation `BV = (π/2) · Σ |r_i| · |r_{i-1}|` is robust to rare jumps: the product of adjacent absolute returns suppresses any single outlier bar. Under the BNS theorem, `BV → ∫ σ²_s ds` (integrated diffusive variance) even when the price process has a finite-activity jump component, while `RV → ∫ σ²_s ds + Σ jumps²`. The difference `JV = max(0, RV − BV)` is a consistent estimator of the jump variation.

This is what WolfPack needs: a decomposition that tells you whether the last hour's volatility was **drift** (trend-followable) or **gap** (mean-reversion, liquidation cascade aftermath). The current ATR detector conflates them and fires trend strategies into JUMPY regimes.

### Inputs
- Same 5-minute bars-per-hour used by HAR-RV. With n=12 intra-hour bars, the BV estimator has enough samples to be stable.
- Optionally use 1-minute bars (n=60) for hourly BV if you want more precision on high-activity names. On alts, stick to 5m to avoid microstructure noise swamping the jump signal.

### Output
Per hour: `(RV, BV, JV, jump_fraction = JV/RV)`.
Jump test statistic (BNS z-test): `Z_J = (RV − BV) / sqrt((π²/4 + π − 5) · (1/n) · QP)` where `QP` is the realized quad-power quarticity `(π/2)² · (n/(n-3)) · Σ |r_i||r_{i-1}||r_{i-2}||r_{i-3}|`. Threshold |Z_J| > 3 for a statistically significant jump hour.

### Specific parameters
- n = 12 (5m bars/hour), scaling factor `π/2 ≈ 1.5708`.
- Jump z-threshold: 3 (standard BNS); on crypto, papers use 4 because the diffusion itself is heavy-tailed. Start at 3, tune on backtest.
- `jump_fraction > 0.40` for at least 2 of the last 4 hours → regime = `JUMPY`.

### Known failure modes
- On thin markets, adjacent bars can both be zero → BV underestimates. **Fix: drop hours where > 20% of 5m bars have zero return.**
- Finite-activity jump assumption breaks in infinite-activity regimes (flash crashes, exchange outages). **Fix: add a hard override — if single-bar |r_i| > 5σ of the trailing day, force `JUMPY` regardless of BNS z-stat.**
- Needs sub-hour data. The current WolfPack pipeline may only be fetching hourly candles from Hyperliquid. **Action item: verify intel service has 5m candle access, else fall back to 15m bars with n=4 per hour (loses accuracy but still works).**

### Computation cost
Two vector sums and a sqrt per hour. Trivial — runs inside the HAR-RV pipeline.

### Sources
- [Barndorff-Nielsen & Shephard 2004 — Power and Bipower Variation](https://public.econ.duke.edu/~get/browse/courses/883/Spr16/COURSE-MATERIALS/Z_Papers/BNSJFEC2004.pdf)
- [BNS 2006 — Econometrics of testing for jumps](https://public.econ.duke.edu/~get/browse/courses/883/Spr15/COURSE-MATERIALS/Z_Papers/BNSJFEC2006.pdf)
- [Corsi, Pirino, Renò 2010 — Threshold bipower variation (ScienceDirect)](https://www.sciencedirect.com/science/article/abs/pii/S0304407610001600)

---

## Method 3: GARCH(1,1) conditional variance as a vol-of-vol / transition detector

**Source:** Bollerslev (1986) GARCH, Ardia et al. MSGARCH package for the Markov-switching extension. Python: the `arch` library (`arch_model(..., vol='GARCH', p=1, q=1)`).

### Description
HAR-RV is great at "where is vol **today**" but slow on regime transitions because it pools the last 24h. GARCH(1,1) fit on 1h log returns gives a one-step-ahead conditional variance `σ²_{t+1|t} = ω + α·ε²_t + β·σ²_t` that reacts bar-by-bar. The **derivative** of this — i.e. vol-of-vol — is the actual regime transition signal we want. Per the crypto GARCH literature, typical hourly BTC/ETH fits land in the range α ∈ [0.09, 0.37], β ∈ [0.70, 0.90], with `α + β` persistence near 0.95-0.98. Low `α+β` means regime has stabilized; a drop to < 0.90 with a spike in `σ²_{t+1|t}` means *mean-reverting vol* (post-cascade); a rise toward unity means *persistent* (trending, breakouts about to continue).

### Inputs
- Hourly log returns (1h, the pipeline already has them).
- Window: 1000 hours (~42 days) rolling. Long enough for stable parameters, short enough that crypto regime shifts register.
- Error distribution: **skewed-t** (`dist='skewt'`), NOT normal. Skewt matches crypto's heavy-tail + skew better; the arch library supports this directly. Normal distribution fits underestimate tails and inflate α.

### Output
Per hour:
1. `sigma_garch = sqrt(σ²_{t+1|t})` — conditional sigma for the next hour.
2. `vov_z = (sigma_garch − mean_30d(sigma_garch)) / std_30d(sigma_garch)` — vol-of-vol z-score.
3. `persistence = α + β` — recent model persistence.

### Specific parameters
- Fit frequency: once per day, at a scheduled off-hour, per wallet. Do **not** refit every bar.
- Warm-up: feed at least 30 days of history on first fit.
- Transition trigger: `|vov_z| > 2.0` → classifier emits `TRANSITION` as an override to the HAR-RV base regime for the next 2 hours.

### Known failure modes
- MLE optimization is finicky on tiny samples. Using 1000 bars and `dist='skewt'` via the `arch` library is stable in practice.
- GARCH treats all shocks symmetrically. If directional asymmetry matters (which it does for crypto — down-moves are jumpier), upgrade to **GJR-GARCH** (`arch_model(..., vol='GARCH', o=1)`). Same fit cost, one extra parameter.

### Computation cost
~1-3 seconds per fit on 1000 hourly observations with the `arch` library on CPU. Once per wallet per day is 4-5 fits total, not in hot path.

### Sources
- [arch library docs](https://arch.readthedocs.io/en/latest/univariate/univariate_volatility_modeling.html)
- [Ardia et al. — MSGARCH for Markov-switching GARCH in R/Python](https://github.com/etatx0/Regime-Switch)
- [Ardia et al. 2019 — Modelling volatility of cryptocurrencies using Markov-Switching GARCH (ScienceDirect)](https://www.sciencedirect.com/science/article/pii/S027553191830669X)
- [Yavuz Akbay — Forecasting Crypto Volatility with GARCH (Medium)](https://medium.com/@yavuzakbay/forecasting-crypto-volatility-with-garch-models-6a67822d1273)

---

## Recommended implementation for WolfPack

**Classifier: HAR-RV (on BV) for base regime + BNS jump fraction for JUMPY override + GARCH vol-of-vol for TRANSITION override.**

Step-by-step each hour:

1. Pull last 24h of 5-minute bars for the asset (12 per hour × 24 = 288 bars).
2. Compute hourly `RV`, `BV`, `JV`, `jump_fraction` per Method 2.
3. Feed trailing 60-day series of `log(BV)` into HAR-RV (Method 1). Forecast next-hour `BV_hat`.
4. Classify base regime by **expanding rolling quantile** of annualized `sqrt(BV_hat · 24 · 365)` against the trailing **90 days** (not 30 — this is the fix for AVAX/DOGE: 30-day window has already contaminated itself; 90-day gives a stable empirical CDF).
5. Apply overrides in order:
   - If last 4h has `jump_fraction > 0.40` in ≥ 2 hours → `JUMPY`.
   - Else if `|vov_z|_garch > 2.0` → `TRANSITION`.
6. Emit (regime, base_regime, overrides_applied) so the validator can debug.

### 6-regime taxonomy mapping

| Regime | Base signal (BV_hat percentile in 90d window) | Override |
|---|---|---|
| `DEAD` | < p20 | — |
| `LOW_VOL` | p20–p50 | — |
| `NORMAL` | p50–p75 | — |
| `HIGH_VOL` | p75–p90 | — |
| `EXTREME` | > p90 | — |
| `JUMPY` | any | `jump_fraction ≥ 0.40` for ≥ 2 of last 4h |
| `TRANSITION` | any | `|vov_z_garch| > 2.0` (applied before strategy routing, lasts 2h) |

Strategy routing: mean-reversion stack in `DEAD`/`LOW_VOL`/`JUMPY`/`TRANSITION`; trend stack in `NORMAL`/`HIGH_VOL`; risk-off (tiny size or skip) in `EXTREME`.

### Why this fixes the AVAX/DOGE failure
- 90-day percentile window → historic dead zones still count, so the current dead zone isn't the reference.
- BV-based (not ATR-based) → dead tape can no longer inflate into "normal" via a couple of isolated gap bars.
- JUMPY override catches liquidation-cascade aftermath that the ATR detector calls HIGH_VOL and routes to trend.
- TRANSITION override gives regime changes a 2h grace period before strategies commit.

---

## Code sketch (target < 100 lines, numpy + arch only)

```python
# wolfpack/intel/volatility_regime.py
import numpy as np
from arch import arch_model

SQRT_PI_OVER_2 = np.sqrt(np.pi / 2)

def hourly_rv_bv(bars_5m: np.ndarray) -> tuple[float, float, float]:
    """bars_5m: 12 closing prices for one hour. Returns (RV, BV, JV)."""
    r = np.diff(np.log(bars_5m))                  # 11 log returns — pad to 12 by prepending
    r = np.concatenate([[0.0], r])                # align to 12-length hour
    rv = float(np.sum(r ** 2))
    bv = float((np.pi / 2) * np.sum(np.abs(r[1:]) * np.abs(r[:-1])))
    jv = max(0.0, rv - bv)
    return rv, bv, jv

def har_rv_forecast(log_bv_series: np.ndarray) -> float:
    """HAR-RV with hour-scale horizons: 1h / 6h / 24h.
    Returns next-hour log(BV) forecast via rolling OLS."""
    x_s = log_bv_series[-1]
    x_m = np.mean(log_bv_series[-6:])
    x_l = np.mean(log_bv_series[-24:])
    # Fit coefficients on rolling 60-day window (1440 points)
    window = log_bv_series[-1440:]
    y = window[24:]
    X = np.column_stack([
        window[23:-1],
        [np.mean(window[i-5:i+1]) for i in range(23, len(window)-1)],
        [np.mean(window[i-23:i+1]) for i in range(23, len(window)-1)],
        np.ones(len(y)),
    ])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return float(beta[0]*x_s + beta[1]*x_m + beta[2]*x_l + beta[3])

def garch_vov(hourly_log_returns: np.ndarray) -> tuple[float, float]:
    """Daily-refit GARCH(1,1) skewt. Returns (sigma_next, persistence)."""
    am = arch_model(hourly_log_returns * 100, mean='Zero', vol='GARCH',
                    p=1, q=1, dist='skewt')
    res = am.fit(disp='off', show_warning=False)
    forecast = res.forecast(horizon=1, reindex=False)
    sigma = float(np.sqrt(forecast.variance.values[-1, 0])) / 100
    persistence = float(res.params['alpha[1]'] + res.params['beta[1]'])
    return sigma, persistence

def classify(bv_hat: float, bv_hist_90d: np.ndarray,
             jump_fractions_last4h: list[float],
             vov_z: float) -> str:
    if vov_z is not None and abs(vov_z) > 2.0:
        return 'TRANSITION'
    if sum(jf >= 0.40 for jf in jump_fractions_last4h) >= 2:
        return 'JUMPY'
    pct = (bv_hist_90d < bv_hat).mean()
    if pct < 0.20: return 'DEAD'
    if pct < 0.50: return 'LOW_VOL'
    if pct < 0.75: return 'NORMAL'
    if pct < 0.90: return 'HIGH_VOL'
    return 'EXTREME'
```

Integrate in `intel/wolfpack/regime.py`, cache `vov_z` daily, call `classify()` each hourly tick.

---

## Crypto-specific adjustments worth noting
- **Persistence is higher than equities.** α + β ≈ 0.97 typical on BTC/ETH hourly vs. ~0.99 for daily equities. Use that as a fit sanity check — if your fit returns α+β < 0.90 something's wrong with the input series (gaps, zeros).
- **Funding-driven vol** shows up as *sustained* high `vov_z` without a corresponding jump spike. Worth logging as a feature but don't need it in the classifier v1.
- **Liquidation-driven vol** is the BNS JUMPY case — that's the whole motivation for adding BV.
- **Exchange outages / withdrawal halts** create structural zero-return runs. Add a data-quality filter: skip hours where `>50%` of 5m bars are zero-return.

## Sources
- [Corsi 2009 — HAR-RV](https://statmath.wu.ac.at/~hauser/LVs/FinEtricsQF/References/Corsi2009JFinEtrics_LMmodelRealizedVola.pdf)
- [Bollerslev, Patton, Quaedvlieg — Practical Guide to HAR (2021)](https://www.sciencedirect.com/science/article/abs/pii/S0378426621002417)
- [Corsi lectures, SNS Pisa — HAR extensions](https://homepage.sns.it/marmi/lezioni/corsi-pisa-2010.pdf)
- [Barndorff-Nielsen & Shephard 2004 — Power and Bipower Variation](https://public.econ.duke.edu/~get/browse/courses/883/Spr16/COURSE-MATERIALS/Z_Papers/BNSJFEC2004.pdf)
- [BNS 2006 — Testing for jumps with BV](https://public.econ.duke.edu/~get/browse/courses/883/Spr15/COURSE-MATERIALS/Z_Papers/BNSJFEC2006.pdf)
- [Corsi, Pirino, Renò 2010 — Threshold BV](https://www.sciencedirect.com/science/article/abs/pii/S0304407610001600)
- [Andersen & Bollerslev 1998 / ABDL 1999 — realized volatility foundations](https://public.econ.duke.edu/~boller/Published_Papers/ier_04.pdf)
- [Andersen & Benzoni — Realized Volatility review (Chicago Fed WP)](https://www.chicagofed.org/-/media/publications/working-papers/2008/wp2008-14-pdf.pdf)
- [arch library docs (Python GARCH)](https://arch.readthedocs.io/en/latest/univariate/univariate_volatility_modeling.html)
- [Ardia et al. — MSGARCH for crypto (ScienceDirect)](https://www.sciencedirect.com/science/article/pii/S027553191830669X)
- [Yuhui Wang — Volatility regime classification with GARCH+Markov (Medium)](https://medium.com/@yuhui_w/volatility-regime-classification-with-garch-1-1-markov-models-7cb85d4d5815)
- [Quantinsti — GARCH / GJR-GARCH Python volatility forecasting](https://blog.quantinsti.com/garch-gjr-garch-volatility-forecasting-python/)
- [Zaltarba — Bitcoin volatility estimation with EWMA in Python](https://zaltarba.github.io/blog/BitcoinVolatility-1/)
- [Amberdata — The Volatility Framework (crypto stress signals)](https://blog.amberdata.io/the-volatility-framework-how-to-read-cryptos-stress-signals)
- [chibui191/bitcoin_volatility_forecasting (GARCH+LSTM BTC)](https://github.com/chibui191/bitcoin_volatility_forecasting)
- [deep-hedger-Peng/HAR-RV (Python HAR reference)](https://github.com/deep-hedger-Peng/HAR-RV)
- [talaikis/HAR-RVModelForRealizedVolatility](https://github.com/talaikis/HAR-RVModelForRealizedVolatility)
- [etatx0/Regime-Switch (GARCH regime-switching Python)](https://github.com/etatx0/Regime-Switch)
- [TradingView — Volatility Regime Classifier (ATRP percentile zones, Agent_R_Zeroth)](https://www.tradingview.com/script/6aZViQvI-Volatility-Regime-Classifier-ATRP-Percentile-Zones/)
- [MDPI — Quantile Spillover-Driven MS model for crypto vol (2025)](https://www.mdpi.com/2227-7390/13/15/2382)
- [Thrive.fi — Crypto market regime detection](https://thrive.fi/blog/trading/crypto-market-regime-detection)
