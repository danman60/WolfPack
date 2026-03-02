"""Correlation & Cross-Asset Intel — Pair correlation, beta, tail risk, diversification analysis."""

from typing import Literal

import numpy as np
from pydantic import BaseModel


CorrelationRegime = Literal["crisis_lock", "highly_correlated", "normal", "decorrelated"]


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
