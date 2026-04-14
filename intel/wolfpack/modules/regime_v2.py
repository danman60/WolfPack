"""
regime_v2 — evidence-based trend / volatility regime classifier.

Module A of WolfPack's research-backed regime framework. Replaces the broken
ATR-percentile RANGING/TRENDING detector in regime_router.py with a weighted
ensemble of three statistical tests plus a BNS bipower-variation vol model.

Research:
  - docs/research/regime/02-mean-reversion-vs-trend-detection.md
        half-life OU fit, simplified Hurst, lag-1 autocorrelation ensemble.
  - docs/research/regime/03-volatility-regime-classification.md
        BNS bipower variation, jump fraction, 90-bar percentile classifier.

Design:
  - Pure numpy. No scipy, statsmodels, arch.
  - Pure functions, no global state.
  - Defensive: short windows / zero variance / NaN-inf inputs return safe defaults.
  - Single public entry point: analyze_regime(closes, highs, lows) -> RegimeAnalysis.

Units:
  - closes/highs/lows: linear price, shape (N,), most-recent last, N~=200 ideal.
  - half_life: bars (1h candles => hours).
  - realized_vol / bipower_vol: sqrt of variance on log returns (per-window).
  - trend_score: dimensionless in [-1, +1]. Negative = reverting, positive = trending.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

# Tunables (doc 02 ensemble + doc 03 taxonomy)
HURST_LAG_MIN: int = 2
HURST_LAG_MAX: int = 20
HURST_WINDOW: int = 200
HALFLIFE_WINDOW: int = 200
AUTOCORR_LAG1_DEADBAND: float = 0.10

W_HALFLIFE: float = 0.45
W_HURST: float = 0.35
W_AUTOCORR: float = 0.20

REVERT_THRESHOLD: float = -0.20
TREND_THRESHOLD: float = +0.35

VOL_WINDOW: int = 90
JUMP_FRACTION_FLAG: float = 0.40

PCT_DEAD: float = 0.10
PCT_LOW: float = 0.35
PCT_NORMAL: float = 0.65
PCT_HIGH: float = 0.90


@dataclass
class RegimeAnalysis:
    """Aggregated regime snapshot returned by analyze_regime()."""
    trend_score: float
    half_life: float | None
    hurst: float | None
    lag1_autocorr: float
    jump_fraction: float
    realized_vol: float
    bipower_vol: float
    vol_regime: str          # DEAD | LOW_VOL | NORMAL | HIGH_VOL | EXTREME
    is_jumpy: bool
    label: str               # e.g. "TRENDING_UP_HIGH_VOL", "REVERTING_LOW_VOL", "JUMPY_NORMAL"


def _safe_log_prices(closes: np.ndarray | None) -> np.ndarray | None:
    """log(closes) with NaN/inf/non-positive screened out; None if <2 valid points."""
    if closes is None:
        return None
    arr = np.asarray(closes, dtype=float)
    if arr.ndim != 1 or arr.size < 2:
        return None
    mask = np.isfinite(arr) & (arr > 0)
    if not mask.all():
        arr = arr[mask]
        if arr.size < 2:
            return None
    return np.log(arr)


# --- Test 1: half-life of mean reversion (OU/AR(1) OLS) ---------------------
def half_life_mean_reversion(log_prices: np.ndarray) -> tuple[float | None, float | None]:
    """OU half-life via AR(1) OLS: delta_y = alpha + lambda*y_lag + eps;
    half_life = -ln(2)/lambda_hat.  Doc 02 Test 3. Weight 0.45 in ensemble.
    Returns (half_life_bars, lambda_hat). half_life=None for explosive /
    random-walk / short-window cases."""
    if log_prices is None or log_prices.size < max(30, HALFLIFE_WINDOW // 4):
        return None, None
    x = log_prices[-HALFLIFE_WINDOW:] if log_prices.size > HALFLIFE_WINDOW else log_prices
    y_lag = x[:-1]
    delta_y = np.diff(x)
    if y_lag.size < 10:
        return None, None
    if not (np.isfinite(y_lag).all() and np.isfinite(delta_y).all()):
        return None, None
    if np.var(y_lag) < 1e-18:
        return None, None
    A = np.column_stack([np.ones_like(y_lag), y_lag])
    try:
        coefs, *_ = np.linalg.lstsq(A, delta_y, rcond=None)
    except np.linalg.LinAlgError:
        return None, None
    lam = float(coefs[1])
    if lam >= -1e-6:                      # deadband around lambda=0
        return None, lam
    hl = -math.log(2.0) / lam
    if not math.isfinite(hl) or hl <= 0:
        return None, lam
    return float(hl), lam


def _halflife_score(half_life: float | None, lam: float | None) -> float:
    """Map half-life to [-1, +1] per doc 02 ensemble rules."""
    if lam is not None and lam >= -1e-6:
        return 1.0
    if half_life is None:
        return 0.0
    if half_life > 200:
        return 0.8
    if half_life > 60:
        return 0.3
    if half_life > 20:
        return -0.4
    return -1.0


# --- Test 2: simplified Hurst exponent --------------------------------------
def hurst_exponent(log_prices: np.ndarray) -> float | None:
    """Simplified variance-of-lagged-differences Hurst estimator.

    Doc 02 Test 1, Mottl/QC formulation:
        tau[lag] = std(x[lag:] - x[:-lag]),   lag ∈ [2..20]
        H        = 2 * polyfit(log(lags), log(tau), 1)[0]

    Note: doc 02 pseudocode wraps std() in an outer sqrt() — that is a typo.
    The Mottl `hurst` library (the canonical reference impl the doc cites)
    omits that extra sqrt. With the typo H collapses to ~0 on all real series
    and breaks the 0.43 / 0.57 thresholds the doc itself recommends. We
    implement the standard formula. Weight 0.35 in ensemble.

    Returns None on short/unstable windows."""
    if log_prices is None:
        return None
    x = log_prices[-HURST_WINDOW:] if log_prices.size > HURST_WINDOW else log_prices
    if x.size < HURST_LAG_MAX + 10:
        return None
    lags = np.arange(HURST_LAG_MIN, HURST_LAG_MAX + 1)
    taus: list[float] = []
    for lag in lags:
        sd = float(np.std(x[lag:] - x[:-lag]))
        if sd <= 0 or not math.isfinite(sd):
            return None
        taus.append(sd)
    tau_arr = np.asarray(taus, dtype=float)
    try:
        slope, _ = np.polyfit(np.log(lags.astype(float)), np.log(tau_arr), 1)
    except (np.linalg.LinAlgError, ValueError):
        return None
    H = 2.0 * float(slope)
    if not math.isfinite(H):
        return None
    return float(max(0.0, min(1.5, H)))


def _hurst_score(H: float | None) -> float:
    """Map Hurst to [-1, +1] centred at 0.50 with width 0.10 (doc 02)."""
    if H is None:
        return 0.0
    return float(np.clip((H - 0.50) / 0.10, -1.0, 1.0))


# --- Test 3: lag-1 autocorrelation of log returns ---------------------------
def lag1_autocorr(log_prices: np.ndarray) -> float:
    """Lag-1 autocorrelation of per-bar log returns. Doc 02 Test 4.
    Weight 0.20 in ensemble. Returns 0.0 on degenerate inputs."""
    if log_prices is None or log_prices.size < 30:
        return 0.0
    r = np.diff(log_prices)
    if r.size < 10:
        return 0.0
    r0, r1 = r[:-1], r[1:]
    if np.var(r0) < 1e-24 or np.var(r1) < 1e-24:
        return 0.0
    with np.errstate(invalid="ignore"):
        c = np.corrcoef(r0, r1)
    if c.shape != (2, 2) or not math.isfinite(c[0, 1]):
        return 0.0
    return float(c[0, 1])


def _autocorr_score(rho1: float) -> float:
    """±0.10 deadband per doc 02; linear ramp to saturation at |rho1|=0.25."""
    if abs(rho1) < AUTOCORR_LAG1_DEADBAND:
        return 0.0
    sign = 1.0 if rho1 > 0 else -1.0
    mag = (abs(rho1) - AUTOCORR_LAG1_DEADBAND) / 0.15
    return float(sign * min(1.0, max(0.0, mag)))


# --- Bipower variation + jump fraction (BNS 2004) ---------------------------
def bipower_variation(log_prices: np.ndarray) -> tuple[float, float, float]:
    """Realized variance, bipower variation, jump fraction.  Doc 03 Method 2.
        RV  = Σ r_i²
        BV  = (π/2) · Σ |r_i|·|r_{i-1}|
        JV  = max(0, RV - BV)
        jump_fraction = JV / RV   (0 if RV == 0)
    Returns (rv, bv, jump_fraction); all zero on degenerate input."""
    if log_prices is None or log_prices.size < 3:
        return 0.0, 0.0, 0.0
    r = np.diff(log_prices)
    if not np.isfinite(r).all():
        r = r[np.isfinite(r)]
    if r.size < 2:
        return 0.0, 0.0, 0.0
    rv = float(np.sum(r * r))
    bv = float((math.pi / 2.0) * np.sum(np.abs(r[1:]) * np.abs(r[:-1])))
    bv = max(0.0, bv)
    if rv <= 0 or not math.isfinite(rv):
        return 0.0, bv, 0.0
    jf = max(0.0, min(1.0, (rv - bv) / rv))
    return rv, bv, jf


# --- Vol regime classification (log-BV percentile, 90-bar window) -----------
def vol_regime_from_bv(log_prices: np.ndarray) -> tuple[str, float, float]:
    """Classify vol via percentile of log(BV) in a 90-bar rolling window.
    Doc 03 recommends 90 bars (not 30) to prevent recent-window self-
    contamination — this is the AVAX/DOGE fix.

    Splits log-returns into 5-return sub-windows, computes local BV per
    sub-window, then ranks the most-recent sub-window's log(BV) against
    the 90 most-recent history points.

    Returns (regime_label, current_bv, percentile_rank). Safe default
    ('NORMAL', 0.0, 0.5) on degenerate inputs."""
    default = ("NORMAL", 0.0, 0.5)
    if log_prices is None or log_prices.size < 20:
        return default
    r = np.diff(log_prices)
    if not np.isfinite(r).all():
        r = r[np.isfinite(r)]
    if r.size < 10:
        return default
    sub = 5
    usable = r.size - (r.size % sub)
    if usable < 2 * sub:
        return default
    chunks = r[-usable:].reshape(-1, sub)
    abs_c = np.abs(chunks)
    bv_chunks = (math.pi / 2.0) * np.sum(abs_c[:, 1:] * abs_c[:, :-1], axis=1)
    bv_chunks = np.maximum(bv_chunks, 1e-18)
    log_bv = np.log(bv_chunks)
    hist = log_bv[-min(VOL_WINDOW, log_bv.size):]
    if hist.size < 5:
        return "NORMAL", float(bv_chunks[-1]), 0.5
    current = float(log_bv[-1])
    current_bv = float(bv_chunks[-1])
    rank = float(np.mean(hist < current))
    if rank < PCT_DEAD:
        label = "DEAD"
    elif rank < PCT_LOW:
        label = "LOW_VOL"
    elif rank < PCT_NORMAL:
        label = "NORMAL"
    elif rank < PCT_HIGH:
        label = "HIGH_VOL"
    else:
        label = "EXTREME"
    return label, current_bv, rank


# --- Ensemble ---------------------------------------------------------------
def _combine_trend_score(
    half_life: float | None, lam: float | None, H: float | None, rho1: float
) -> float:
    """Weighted blend into [-1, +1]. Weights from doc 02 ensemble section."""
    score = (
        W_HALFLIFE * _halflife_score(half_life, lam)
        + W_HURST * _hurst_score(H)
        + W_AUTOCORR * _autocorr_score(rho1)
    )
    return float(np.clip(score, -1.0, 1.0))


def _trend_label(trend_score: float) -> str:
    """Asymmetric thresholds (doc 02): revert < -0.20, trend > +0.35."""
    if trend_score < REVERT_THRESHOLD:
        return "REVERTING"
    if trend_score > TREND_THRESHOLD:
        return "TRENDING"
    return "NEUTRAL"


def _direction_suffix(trend_score: float, log_prices: np.ndarray | None) -> str:
    """Cheap UP/DOWN tag for TRENDING regimes via 50-bar log-slope sign."""
    if trend_score <= TREND_THRESHOLD or log_prices is None or log_prices.size < 10:
        return ""
    tail = log_prices[-min(50, log_prices.size):]
    if tail.size < 3:
        return ""
    xs = np.arange(tail.size, dtype=float)
    try:
        slope, _ = np.polyfit(xs, tail, 1)
    except (np.linalg.LinAlgError, ValueError):
        return ""
    if not math.isfinite(slope):
        return ""
    return "_UP" if slope >= 0 else "_DOWN"


# --- Public entry point -----------------------------------------------------
def analyze_regime(
    closes: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
) -> RegimeAnalysis:
    """Run the full regime_v2 ensemble on the last ~200 bars of OHLC.

    Args:
        closes: close prices, shape (N,), most-recent last. N~=200 recommended.
        highs:  high prices, same shape. Reserved for future range-based
                extensions; validated but not consumed by v2 estimators.
        lows:   low prices, same shape. Same note as highs.

    Returns:
        RegimeAnalysis dataclass. Degenerate/short inputs return a neutral
        'UNKNOWN' snapshot rather than raising."""
    closes_arr = np.asarray(closes, dtype=float) if closes is not None else None
    if highs is not None:
        _ = np.asarray(highs, dtype=float)
    if lows is not None:
        _ = np.asarray(lows, dtype=float)

    log_prices = _safe_log_prices(closes_arr)
    if log_prices is None or log_prices.size < 30:
        return RegimeAnalysis(
            trend_score=0.0, half_life=None, hurst=None, lag1_autocorr=0.0,
            jump_fraction=0.0, realized_vol=0.0, bipower_vol=0.0,
            vol_regime="NORMAL", is_jumpy=False, label="UNKNOWN",
        )

    half_life, lam = half_life_mean_reversion(log_prices)
    H = hurst_exponent(log_prices)
    rho1 = lag1_autocorr(log_prices)
    trend_score = _combine_trend_score(half_life, lam, H, rho1)

    rv, bv, jump_fraction = bipower_variation(log_prices)
    realized_vol = math.sqrt(rv) if rv > 0 else 0.0
    bipower_vol = math.sqrt(bv) if bv > 0 else 0.0
    is_jumpy = jump_fraction > JUMP_FRACTION_FLAG

    vol_regime, _, _ = vol_regime_from_bv(log_prices)

    trend_lbl = _trend_label(trend_score)
    direction = _direction_suffix(trend_score, log_prices)
    label = f"JUMPY_{vol_regime}" if is_jumpy else f"{trend_lbl}{direction}_{vol_regime}"

    return RegimeAnalysis(
        trend_score=float(trend_score),
        half_life=float(half_life) if half_life is not None else None,
        hurst=float(H) if H is not None else None,
        lag1_autocorr=float(rho1),
        jump_fraction=float(jump_fraction),
        realized_vol=float(realized_vol),
        bipower_vol=float(bipower_vol),
        vol_regime=vol_regime,
        is_jumpy=bool(is_jumpy),
        label=label,
    )


# --- Smoke test -------------------------------------------------------------
if __name__ == "__main__":
    rng = np.random.default_rng(42)
    N = 250

    # 1) Trending up: drifted random walk (persistent positive innovations).
    innovations = 0.004 * rng.standard_normal(N) + 0.005
    trend_closes = np.exp(np.cumsum(innovations) + math.log(100.0))

    # 2) Reverting: AR(1) OU process around a constant mean.
    mean = math.log(100.0)
    phi, sigma = 0.85, 0.01
    x = np.zeros(N)
    x[0] = mean
    for t in range(1, N):
        x[t] = mean + phi * (x[t - 1] - mean) + sigma * rng.standard_normal()
    revert_closes = np.exp(x)

    # 3) Jumpy: tiny diffusion + persistent level jumps (isolated large returns).
    diffusive = np.cumsum(0.001 * rng.standard_normal(N))
    jump_sizes = np.zeros(N)
    jump_idx = rng.choice(np.arange(5, N - 5), size=15, replace=False)
    jump_sizes[jump_idx] = rng.choice([-1.0, 1.0], size=15) * 0.06
    jumpy_closes = 100.0 * np.exp(diffusive + np.cumsum(jump_sizes))

    cases = [
        ("trending_up", trend_closes),
        ("reverting", revert_closes),
        ("volatile_jumpy", jumpy_closes),
    ]
    for name, c in cases:
        ra = analyze_regime(c, c * 1.001, c * 0.999)
        print(f"[{name}]")
        print(f"  label        = {ra.label}")
        print(f"  trend_score  = {ra.trend_score:+.3f}")
        print(f"  half_life    = {ra.half_life}")
        print(f"  hurst        = {ra.hurst}")
        print(f"  lag1_ac      = {ra.lag1_autocorr:+.3f}")
        print(f"  jump_frac    = {ra.jump_fraction:.3f}")
        print(f"  realized_vol = {ra.realized_vol:.5f}")
        print(f"  bipower_vol  = {ra.bipower_vol:.5f}")
        print(f"  vol_regime   = {ra.vol_regime}")
        print(f"  is_jumpy     = {ra.is_jumpy}")
        print()
