"""Regime Detection — Classifies market into trending, choppy, panic, or low-vol regimes.

Implements the full WolfPack Toolkit specification:
- EMA Trend Score (20/50 spread + slope)
- ADX Proxy (14-period directional index)
- ATR Percentile (14-period ATR vs 60-bar rolling)
- RSI(14)
- Breakout Strength (distance from 20-bar extremes / ATR)
- Multi-Timeframe Agreement voting
"""

from enum import Enum
from typing import Literal

import numpy as np
from pydantic import BaseModel, Field

from wolfpack.exchanges.base import Candle


class Regime(str, Enum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    CHOPPY = "choppy"
    PANIC = "panic"
    LOW_VOL_GRIND = "low_vol_grind"


RSI_ZONE = Literal["oversold", "overbought", "neutral"]
STRATEGY_TYPE = Literal["momentum", "mean_reversion", "breakout", "reduce_only", "passive"]


class SubSignals(BaseModel):
    ema_trend_score: float = Field(description="EMA crossover + slope score in [-1, 1]")
    adx_proxy: float = Field(description="14-period ADX proxy value")
    rsi_zone: RSI_ZONE = Field(description="RSI classification: oversold, overbought, neutral")
    atr_percentile: float = Field(description="Current ATR percentile vs 60-bar lookback [0, 1]")
    breakout_strength: float = Field(description="Distance from 20-bar high/low normalized by ATR")
    multi_tf_agreement: float = Field(description="Cross-timeframe directional agreement [0.5, 1.0]")
    bucket_momentum: float = Field(
        default=0.0,
        description="Discrete bucketing momentum score [-1, 1] — noise-reduced trend signal",
    )


class RegimeSignal(BaseModel):
    asset: str
    regime: Regime
    confidence: float = Field(ge=0.0, le=1.0)
    risk_scalar: float = Field(ge=0.0, le=1.2)
    sub_signals: SubSignals
    recommended_strategy_type: STRATEGY_TYPE


# ---------------------------------------------------------------------------
# Timeframe weights for multi-TF voting
# ---------------------------------------------------------------------------
_TF_WEIGHTS: dict[str, float] = {"1h": 0.3, "4h": 0.4, "1d": 0.3}

# Minimum bars needed to compute all indicators (60 for ATR percentile lookback)
_MIN_BARS = 61


def _to_arrays(candles: list[Candle]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Extract OHLC numpy arrays from a list of Candle models."""
    opens = np.array([c.open for c in candles], dtype=np.float64)
    highs = np.array([c.high for c in candles], dtype=np.float64)
    lows = np.array([c.low for c in candles], dtype=np.float64)
    closes = np.array([c.close for c in candles], dtype=np.float64)
    return opens, highs, lows, closes


# ---------------------------------------------------------------------------
# Indicator computations (pure numpy, no external TA libs)
# ---------------------------------------------------------------------------


def _ema(values: np.ndarray, period: int) -> np.ndarray:
    """Exponential moving average using the standard multiplier 2/(period+1)."""
    alpha = 2.0 / (period + 1)
    out = np.empty_like(values)
    out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = alpha * values[i] + (1.0 - alpha) * out[i - 1]
    return out


def _ema_trend_score(closes: np.ndarray) -> float:
    """EMA trend score: 0.6 * tanh(spread*100) + 0.4 * tanh(slope*200).

    - spread = (EMA20 - EMA50) / price, last bar
    - slope  = mean of last-5-bar differences of EMA20, normalized by price
    """
    if len(closes) < 50:
        return 0.0

    ema_fast = _ema(closes, 20)
    ema_slow = _ema(closes, 50)

    price = closes[-1]
    if price == 0:
        return 0.0

    spread = (ema_fast[-1] - ema_slow[-1]) / price

    # Slope of fast EMA over last 5 bars (average bar-to-bar change / price)
    if len(ema_fast) >= 5:
        diffs = np.diff(ema_fast[-5:])
        slope = np.mean(diffs) / price
    else:
        slope = 0.0

    score = 0.6 * np.tanh(spread * 100) + 0.4 * np.tanh(slope * 200)
    return float(np.clip(score, -1.0, 1.0))


def _adx_proxy(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> float:
    """Simplified ADX proxy — 14-period mean of DX values.

    Returns a value in [0, 100].
    """
    n = len(highs)
    if n < period + 1:
        return 0.0

    plus_dm = np.zeros(n)
    minus_dm = np.zeros(n)
    tr = np.zeros(n)

    for i in range(1, n):
        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]

        plus_dm[i] = up_move if (up_move > down_move and up_move > 0) else 0.0
        minus_dm[i] = down_move if (down_move > up_move and down_move > 0) else 0.0

        tr[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )

    # Use simple mean over the last `period` bars for smoothing
    tail = slice(-period, None)
    atr_val = np.mean(tr[tail])
    if atr_val == 0:
        return 0.0

    plus_di = np.mean(plus_dm[tail]) / atr_val * 100
    minus_di = np.mean(minus_dm[tail]) / atr_val * 100

    di_sum = plus_di + minus_di
    if di_sum == 0:
        return 0.0

    dx = abs(plus_di - minus_di) / di_sum * 100
    return float(dx)


def _atr_percentile(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    atr_period: int = 14,
    lookback: int = 60,
) -> float:
    """Current ATR(14) as a percentile of the last 60 ATR values. Returns [0, 1]."""
    n = len(highs)
    if n < atr_period + 1:
        return 0.5  # neutral default

    # True Range series
    tr = np.zeros(n)
    for i in range(1, n):
        tr[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )

    # Rolling ATR (simple mean over atr_period)
    if n < atr_period + lookback:
        # Use whatever history we have
        start = atr_period
    else:
        start = n - lookback

    atr_series = []
    for i in range(max(start, atr_period), n):
        atr_series.append(np.mean(tr[i - atr_period + 1 : i + 1]))

    if not atr_series:
        return 0.5

    atr_arr = np.array(atr_series)
    current_atr = atr_arr[-1]
    percentile = float(np.mean(atr_arr <= current_atr))
    return np.clip(percentile, 0.0, 1.0)


def _rsi(closes: np.ndarray, period: int = 14) -> tuple[float, RSI_ZONE]:
    """RSI(14). Returns (rsi_value, zone_label)."""
    if len(closes) < period + 1:
        return 50.0, "neutral"

    deltas = np.diff(closes)
    tail = deltas[-(period):]

    gains = np.where(tail > 0, tail, 0.0)
    losses = np.where(tail < 0, -tail, 0.0)

    avg_gain = np.mean(gains)
    avg_loss = np.mean(losses)

    if avg_loss == 0:
        rsi_val = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi_val = 100.0 - 100.0 / (1.0 + rs)

    if rsi_val < 30:
        zone: RSI_ZONE = "oversold"
    elif rsi_val > 70:
        zone = "overbought"
    else:
        zone = "neutral"

    return float(rsi_val), zone


def _breakout_strength(
    closes: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    bar_lookback: int = 20,
    atr_period: int = 14,
) -> float:
    """Distance from 20-bar high/low, normalized by ATR. Returns [-1, 1].

    Positive = near highs (bullish breakout), negative = near lows (bearish breakout).
    """
    if len(closes) < max(bar_lookback, atr_period + 1):
        return 0.0

    high_20 = np.max(highs[-bar_lookback:])
    low_20 = np.min(lows[-bar_lookback:])
    price = closes[-1]

    rng = high_20 - low_20
    if rng == 0:
        return 0.0

    # Where the price sits in the 20-bar range, centered to [-1, 1]
    position = (price - low_20) / rng * 2 - 1  # -1 at low, +1 at high

    # Normalize by ATR to capture volatility-adjusted significance
    tr = np.zeros(len(closes))
    for i in range(1, len(closes)):
        tr[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
    atr = np.mean(tr[-atr_period:])
    if atr == 0:
        return 0.0

    # Scale: breakout beyond range edge is amplified by ATR normalization
    distance_from_center = abs(price - (high_20 + low_20) / 2)
    strength = (distance_from_center / atr) * np.sign(position)
    return float(np.clip(strength, -1.0, 1.0))


# ---------------------------------------------------------------------------
# Single-timeframe analysis (produces direction score + sub-signals)
# ---------------------------------------------------------------------------


def _bucket_momentum(closes: np.ndarray) -> float:
    """Compute discrete bucket momentum score from close prices.

    Buckets prices into volatility-adaptive steps and detects monotonic
    movement across buckets, filtering tick-level noise.
    Returns [-1, 1]: positive = bullish momentum, negative = bearish.
    """
    if len(closes) < 5:
        return 0.0

    # Auto-select bucket size from recent volatility
    atr_period = min(14, len(closes) - 1)
    abs_returns = np.abs(np.diff(closes[-atr_period - 1:])) / closes[-atr_period - 1:-1]
    avg_return = np.mean(abs_returns)
    bucket_pct = float(np.clip(avg_return * 1.5, 0.003, 0.015))

    # Bucket the last 13 closes (swing detection window)
    lookback = min(13, len(closes))
    window = closes[-lookback:]
    step = window[-1] * bucket_pct
    if step <= 0:
        return 0.0

    bucketed = np.floor(window / step) * step
    transitions = np.diff(bucketed)

    # Count consecutive same-direction bucket moves from the end
    consecutive = 0
    if len(transitions) > 0:
        last_sign = np.sign(transitions[-1])
        if last_sign != 0:
            for i in range(len(transitions) - 1, -1, -1):
                if np.sign(transitions[i]) == last_sign:
                    consecutive += 1
                else:
                    break

    # Net velocity: direction of bucket changes
    nonzero = transitions[transitions != 0]
    if len(nonzero) > 0:
        velocity = float(np.sum(np.sign(nonzero))) / len(transitions)
    else:
        velocity = 0.0

    # Score: velocity weighted by consecutive streak
    streak_weight = min(consecutive / 4.0, 1.0)
    score = velocity * (0.5 + 0.5 * streak_weight)
    return float(np.clip(score, -1.0, 1.0))


def _analyze_single_tf(candles: list[Candle]) -> tuple[float, SubSignals]:
    """Run all indicators on one timeframe and return (direction_score, sub_signals).

    direction_score is in [-1, 1]: positive = bullish, negative = bearish.
    multi_tf_agreement is set to 1.0 here (overridden at the multi-TF level).
    """
    _, highs, lows, closes = _to_arrays(candles)

    ema_score = _ema_trend_score(closes)
    adx = _adx_proxy(highs, lows, closes)
    atr_pct = _atr_percentile(highs, lows, closes)
    rsi_val, rsi_zone = _rsi(closes)
    breakout = _breakout_strength(closes, highs, lows)
    bucket_mom = _bucket_momentum(closes)

    # Direction score: weighted blend of EMA trend, breakout, and bucket momentum
    # Bucket momentum gets 15% weight — acts as noise-filtered confirmation
    direction_score = 0.60 * ema_score + 0.25 * breakout + 0.15 * bucket_mom

    sub = SubSignals(
        ema_trend_score=round(ema_score, 4),
        adx_proxy=round(adx, 2),
        rsi_zone=rsi_zone,
        atr_percentile=round(atr_pct, 4),
        breakout_strength=round(breakout, 4),
        multi_tf_agreement=1.0,  # placeholder
        bucket_momentum=round(bucket_mom, 4),
    )
    return direction_score, sub


# ---------------------------------------------------------------------------
# Regime classification + risk scalar
# ---------------------------------------------------------------------------

_RISK_BASES: dict[Regime, float] = {
    Regime.TRENDING_UP: 1.0,
    Regime.TRENDING_DOWN: 0.8,
    Regime.CHOPPY: 0.4,
    Regime.PANIC: 0.1,
    Regime.LOW_VOL_GRIND: 0.6,
}

_STRATEGY_MAP: dict[Regime, STRATEGY_TYPE] = {
    Regime.TRENDING_UP: "momentum",
    Regime.TRENDING_DOWN: "momentum",
    Regime.CHOPPY: "mean_reversion",
    Regime.PANIC: "reduce_only",
    Regime.LOW_VOL_GRIND: "passive",
}


def _classify_regime(adx: float, atr_pct: float, direction_score: float, atr_value: float = 0.0, price: float = 0.0) -> Regime:
    """Classify regime from indicator values per spec thresholds.

    PANIC requires BOTH high ATR percentile AND meaningful absolute move.
    A 2% day after a quiet week shouldn't trigger panic — crypto moves 2% regularly.
    """
    if atr_pct > 0.92:
        # Absolute check: ATR must be > 3% of price to be real panic (not just relative spike)
        if price > 0 and atr_value > 0 and (atr_value / price) < 0.03:
            pass  # Relative spike but absolute move is normal — don't panic
        else:
            return Regime.PANIC
    if adx > 25 and direction_score > 0.2:
        return Regime.TRENDING_UP
    if adx > 25 and direction_score < -0.2:
        return Regime.TRENDING_DOWN
    if atr_pct < 0.20:
        return Regime.LOW_VOL_GRIND
    return Regime.CHOPPY


def _compute_risk_scalar(regime: Regime, confidence: float) -> float:
    """Position sizing multiplier: base * (0.5 + 0.5 * confidence), clamped [0, 1.2]."""
    base = _RISK_BASES[regime]
    raw = base * (0.5 + 0.5 * confidence)
    return float(np.clip(raw, 0.0, 1.2))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class RegimeDetector:
    """Detects market regime using EMA trend, ADX, ATR percentile, RSI,
    breakout strength, and multi-timeframe agreement voting.

    Supports both single-timeframe and multi-timeframe analysis.
    """

    def __init__(self, lookback: int = 60):
        """
        Args:
            lookback: Minimum number of bars required for reliable analysis.
                      Defaults to 60 (enough for ATR percentile).
        """
        self.lookback = lookback

    # ------------------------------------------------------------------
    # Multi-timeframe entry point
    # ------------------------------------------------------------------

    def detect(
        self,
        candles_by_tf: dict[str, list[Candle]] | list[Candle],
        asset: str = "BTC",
    ) -> RegimeSignal:
        """Detect market regime.

        Args:
            candles_by_tf: Either a dict mapping timeframe labels (e.g. "1h", "4h", "1d")
                           to lists of Candle objects, or a single list of Candles (treated
                           as a single-timeframe analysis).
            asset: Asset symbol for the output label.

        Returns:
            RegimeSignal with regime classification, confidence, risk scalar,
            sub-signals, and recommended strategy type.
        """
        # Normalize input: single list -> dict with default key
        if isinstance(candles_by_tf, list):
            candles_by_tf = {"1h": candles_by_tf}

        # Analyse each timeframe
        tf_results: list[tuple[str, float, SubSignals]] = []
        for tf_label, candles in candles_by_tf.items():
            if len(candles) < _MIN_BARS:
                # Not enough data for this timeframe — produce neutral fallback
                direction = 0.0
                sub = SubSignals(
                    ema_trend_score=0.0,
                    adx_proxy=0.0,
                    rsi_zone="neutral",
                    atr_percentile=0.5,
                    breakout_strength=0.0,
                    multi_tf_agreement=0.5,
                )
            else:
                direction, sub = _analyze_single_tf(candles)
            tf_results.append((tf_label, direction, sub))

        # ----- Multi-Timeframe voting -----
        # Weight each timeframe
        weighted_direction = 0.0
        total_weight = 0.0
        directions: list[float] = []

        for tf_label, direction, _ in tf_results:
            w = _TF_WEIGHTS.get(tf_label, 0.3)  # fallback weight
            weighted_direction += w * direction
            total_weight += w
            directions.append(direction)

        if total_weight > 0:
            direction_score = weighted_direction / total_weight
        else:
            direction_score = 0.0

        # Agreement: 1.0 if all TFs have the same sign, else 0.5
        if len(directions) > 1:
            signs = [np.sign(d) for d in directions if d != 0]
            if signs and all(s == signs[0] for s in signs):
                agreement = 1.0
            else:
                agreement = 0.5
        else:
            agreement = 1.0

        # ----- Pick primary TF sub-signals for output -----
        # Prefer 4h, then 1h, then whatever is available
        primary_tf = "4h" if "4h" in candles_by_tf else next(iter(candles_by_tf))
        primary_sub: SubSignals | None = None
        for tf_label, _, sub in tf_results:
            if tf_label == primary_tf:
                primary_sub = sub
                break
        if primary_sub is None:
            primary_sub = tf_results[0][2]

        # Override agreement in sub-signals
        primary_sub = primary_sub.model_copy(update={"multi_tf_agreement": round(agreement, 2)})

        # ----- Classify regime -----
        # Pass absolute ATR + price so panic requires real absolute move, not just relative spike
        _, p_highs, p_lows, p_closes = _to_arrays(candles_by_tf[primary_tf])
        _raw_atr = float(np.mean([
            max(p_highs[i] - p_lows[i], abs(p_highs[i] - p_closes[i-1]), abs(p_lows[i] - p_closes[i-1]))
            for i in range(max(1, len(p_closes)-14), len(p_closes))
        ])) if len(p_closes) > 14 else 0.0

        regime = _classify_regime(
            adx=primary_sub.adx_proxy,
            atr_pct=primary_sub.atr_percentile,
            direction_score=direction_score,
            atr_value=_raw_atr,
            price=float(p_closes[-1]) if len(p_closes) > 0 else 0.0,
        )

        # ----- Confidence -----
        # Blended from ADX strength (trend clarity), TF agreement, and RSI extremity
        adx_conf = min(primary_sub.adx_proxy / 50.0, 1.0)  # 50 = "very strong"
        rsi_extremity = 0.0
        if primary_sub.rsi_zone == "overbought":
            rsi_extremity = 0.3
        elif primary_sub.rsi_zone == "oversold":
            rsi_extremity = 0.3

        confidence = float(np.clip(
            0.4 * adx_conf + 0.35 * agreement + 0.15 * abs(direction_score) + 0.1 * rsi_extremity,
            0.0,
            1.0,
        ))

        # ----- Risk scalar + strategy -----
        risk_scalar = _compute_risk_scalar(regime, confidence)
        strategy = _STRATEGY_MAP[regime]

        return RegimeSignal(
            asset=asset,
            regime=regime,
            confidence=round(confidence, 4),
            risk_scalar=round(risk_scalar, 4),
            sub_signals=primary_sub,
            recommended_strategy_type=strategy,
        )
