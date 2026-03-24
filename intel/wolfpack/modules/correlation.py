"""Correlation & Cross-Asset Intel — Pair correlation, beta, tail risk, diversification, stat arb signals."""

from typing import Literal

import numpy as np
from pydantic import BaseModel, Field


CorrelationRegime = Literal["crisis_lock", "highly_correlated", "normal", "decorrelated"]


class StatArbSignal(BaseModel):
    """Stat arb divergence signal — fed to agents when correlated assets diverge."""

    pair: str
    zscore: float = Field(description="Z-score of price ratio vs 30d mean. >2 or <-2 = significant")
    direction: str = Field(description="'long_eth_short_btc' or 'long_btc_short_eth' or 'neutral'")
    strength: str = Field(description="'strong' (|z|>=2.5), 'moderate' (|z|>=1.5), 'weak' (|z|>=1.0), 'neutral'")
    mean_reversion_target: float = Field(description="Expected ratio to revert to")
    current_ratio: float
    ratio_percentile: float = Field(description="Where current ratio sits in 30d distribution (0-100)")


class CorrelationOutput(BaseModel):
    pair: str
    correlation_30d: float
    correlation_7d: float
    beta_eth_to_btc: float
    tail_correlation: float
    diversification_benefit: float
    effective_exposure_multiplier: float
    correlation_regime: CorrelationRegime
    max_combined_position_pct: float
    stat_arb: StatArbSignal | None = Field(default=None, description="Stat arb divergence signal when assets diverge")


class CorrelationIntel:
    """Computes rolling correlations, beta, tail correlation, and diversification metrics.

    Key computations:
    - Log returns for both assets
    - Pearson correlation on 30d and 7d windows (hourly data: 720h and 168h)
    - Beta via OLS regression (ETH returns ~ BTC returns)
    - Tail correlation: Pearson on days where BTC return is in bottom 5%
    - Diversification benefit: 1 - sqrt(0.5 * (1 + rho))
    - Effective exposure: sqrt(2 * (1 + rho))
    - Regime and position limits from tail correlation + 7d correlation
    """

    def __init__(self, hours_per_day: int = 24):
        self.hours_per_day = hours_per_day

    def analyze(
        self,
        btc_closes: list[float],
        eth_closes: list[float],
    ) -> CorrelationOutput:
        """Analyze BTC/ETH correlation from hourly close prices.

        Args:
            btc_closes: Hourly BTC closes, most recent last.
            eth_closes: Hourly ETH closes, most recent last. Must match btc_closes length.
        """
        btc = np.array(btc_closes, dtype=np.float64)
        eth = np.array(eth_closes, dtype=np.float64)

        # Trim to matching length
        n = min(len(btc), len(eth))
        if n < 3:
            return self._empty_output()

        btc = btc[-n:]
        eth = eth[-n:]

        # --- Log returns ---
        btc_log_ret = np.diff(np.log(btc))
        eth_log_ret = np.diff(np.log(eth))

        # --- Pearson correlations ---
        corr_30d = self._pearson(btc_log_ret, eth_log_ret, window=720)
        corr_7d = self._pearson(btc_log_ret, eth_log_ret, window=168)

        # --- Beta via OLS: ETH = alpha + beta * BTC + epsilon ---
        beta = self._ols_beta(btc_log_ret, eth_log_ret, window=720)

        # --- Tail correlation: bottom 5% of BTC returns ---
        tail_corr = self._tail_correlation(btc_log_ret, eth_log_ret, percentile=5)

        # --- Diversification benefit: 1 - sqrt(0.5 * (1 + rho)) ---
        rho = corr_7d  # Use shorter-term for current regime
        div_benefit = 1.0 - np.sqrt(0.5 * (1 + rho))

        # --- Effective exposure multiplier: sqrt(2 * (1 + rho)) ---
        eff_exposure = float(np.sqrt(2.0 * (1.0 + rho)))

        # --- Regime classification ---
        regime, max_pos = self._classify_regime(corr_7d, tail_corr)

        # --- Stat arb divergence detection ---
        stat_arb = self._detect_stat_arb(btc, eth, corr_7d)

        return CorrelationOutput(
            pair="BTC/ETH",
            correlation_30d=round(corr_30d, 4),
            correlation_7d=round(corr_7d, 4),
            beta_eth_to_btc=round(beta, 4),
            tail_correlation=round(tail_corr, 4),
            diversification_benefit=round(div_benefit, 4),
            effective_exposure_multiplier=round(eff_exposure, 4),
            correlation_regime=regime,
            max_combined_position_pct=max_pos,
            stat_arb=stat_arb,
        )

    @staticmethod
    def _pearson(x: np.ndarray, y: np.ndarray, window: int) -> float:
        """Pearson correlation on the last `window` observations."""
        n = min(window, len(x), len(y))
        if n < 3:
            return 0.0

        x_w = x[-n:]
        y_w = y[-n:]

        # Use numpy corrcoef
        corr_matrix = np.corrcoef(x_w, y_w)
        rho = corr_matrix[0, 1]

        if np.isnan(rho):
            return 0.0
        return float(np.clip(rho, -1.0, 1.0))

    @staticmethod
    def _ols_beta(x: np.ndarray, y: np.ndarray, window: int) -> float:
        """OLS regression beta: y = alpha + beta * x."""
        n = min(window, len(x), len(y))
        if n < 3:
            return 1.0

        x_w = x[-n:]
        y_w = y[-n:]

        # beta = cov(x,y) / var(x)
        x_mean = np.mean(x_w)
        y_mean = np.mean(y_w)
        cov_xy = np.mean((x_w - x_mean) * (y_w - y_mean))
        var_x = np.var(x_w, ddof=0)

        if var_x < 1e-18:
            return 1.0

        return float(cov_xy / var_x)

    @staticmethod
    def _tail_correlation(
        btc_ret: np.ndarray, eth_ret: np.ndarray, percentile: int = 5
    ) -> float:
        """Pearson correlation only on days where BTC return is in the bottom percentile."""
        if len(btc_ret) < 20:
            return 0.0

        threshold = np.percentile(btc_ret, percentile)
        mask = btc_ret <= threshold

        btc_tail = btc_ret[mask]
        eth_tail = eth_ret[mask]

        if len(btc_tail) < 3:
            return 0.0

        corr_matrix = np.corrcoef(btc_tail, eth_tail)
        rho = corr_matrix[0, 1]

        if np.isnan(rho):
            return 0.0
        return float(np.clip(rho, -1.0, 1.0))

    @staticmethod
    def _classify_regime(
        corr_7d: float, tail_corr: float
    ) -> tuple[CorrelationRegime, float]:
        """Classify correlation regime and set max combined position limit.

        Returns (regime, max_combined_position_pct).
        """
        if tail_corr > 0.90 and corr_7d > 0.75:
            return "crisis_lock", 30.0
        elif corr_7d > 0.75:
            return "highly_correlated", 37.5
        elif corr_7d < 0.30:
            return "decorrelated", 50.0
        else:
            return "normal", 50.0

    @staticmethod
    def _detect_stat_arb(
        btc: np.ndarray, eth: np.ndarray, corr_7d: float
    ) -> StatArbSignal | None:
        """Detect stat arb opportunities from price ratio divergence.

        Only fires when correlation is high enough that mean reversion is expected.
        Uses z-score of ETH/BTC price ratio vs 30d rolling mean.
        """
        # Only look for stat arb when assets are meaningfully correlated
        if corr_7d < 0.50 or len(btc) < 168:  # Need 7d+ of data and correlation
            return None

        # Price ratio: ETH/BTC
        # Filter out zero prices
        mask = (btc > 0) & (eth > 0)
        if np.sum(mask) < 168:
            return None

        ratio = eth[mask] / btc[mask]

        # 30d window (720h) or whatever we have
        window = min(720, len(ratio))
        ratio_window = ratio[-window:]
        current_ratio = float(ratio[-1])

        mean_ratio = float(np.mean(ratio_window))
        std_ratio = float(np.std(ratio_window, ddof=1))

        if std_ratio < 1e-10:
            return None

        zscore = (current_ratio - mean_ratio) / std_ratio

        # Percentile of current ratio in distribution
        percentile = float(np.mean(ratio_window <= current_ratio) * 100)

        # Direction and strength
        if zscore >= 1.5:
            # ETH expensive relative to BTC — expect reversion down
            direction = "long_btc_short_eth"
        elif zscore <= -1.5:
            # ETH cheap relative to BTC — expect reversion up
            direction = "long_eth_short_btc"
        else:
            direction = "neutral"

        abs_z = abs(zscore)
        if abs_z >= 2.5:
            strength = "strong"
        elif abs_z >= 1.5:
            strength = "moderate"
        elif abs_z >= 1.0:
            strength = "weak"
        else:
            strength = "neutral"

        return StatArbSignal(
            pair="ETH/BTC",
            zscore=round(zscore, 3),
            direction=direction,
            strength=strength,
            mean_reversion_target=round(mean_ratio, 6),
            current_ratio=round(current_ratio, 6),
            ratio_percentile=round(percentile, 1),
        )

    @staticmethod
    def _empty_output() -> CorrelationOutput:
        return CorrelationOutput(
            pair="BTC/ETH",
            correlation_30d=0.0,
            correlation_7d=0.0,
            beta_eth_to_btc=1.0,
            tail_correlation=0.0,
            diversification_benefit=0.293,  # 1 - sqrt(0.5)
            effective_exposure_multiplier=1.0,
            correlation_regime="normal",
            max_combined_position_pct=50.0,
        )
