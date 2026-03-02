"""Volatility & Risk Budget — Realized vol, vol regime detection, and exposure scaling."""

from typing import Literal

import numpy as np
from pydantic import BaseModel


VolRegime = Literal["low", "normal", "elevated", "extreme"]
RiskState = Literal["full_risk", "reduced", "minimal", "emergency"]


class VolatilityOutput(BaseModel):
    asset: str
    realized_vol_1d: float
    realized_vol_7d: float
    realized_vol_30d: float
    vol_zscore: float
    vol_regime: VolRegime
    target_vol_pct: float
    vol_scalar: float
    current_drawdown_pct: float
    drawdown_scalar: float
    combined_exposure_multiplier: float
    risk_state: RiskState


class VolatilitySignal:
    """Computes realized volatility at multiple horizons and derives position sizing scalars.

    Key computations:
    - Log returns for all vol calculations
    - Vol_1d = std(last 24 returns) * sqrt(8760) * 100  (annualized from hourly)
    - Vol z-score = (vol_1d - mean(30d rolling vols)) / std(30d rolling vols)
    - Vol regime from absolute thresholds: >80 extreme, >50 elevated, >20 normal, <=20 low
    - Vol scalar = target_vol / max(realized, floor), capped [0.1, 1.5]
    - Drawdown scalar: linear interpolation from 1.0 at dd<=5% to 0.0 at dd>=10%
    - Combined = min(vol_scalar, drawdown_scalar)
    - Risk state from combined multiplier and drawdown
    """

    def __init__(self, target_vol_pct: float = 30.0, vol_floor_pct: float = 10.0):
        self.target_vol_pct = target_vol_pct
        self.vol_floor_pct = vol_floor_pct

    def analyze(
        self,
        asset: str,
        closes: list[float],
        current_drawdown_pct: float = 0.0,
    ) -> VolatilityOutput:
        """Analyze volatility from hourly close prices.

        Args:
            asset: Asset symbol (e.g. "BTC").
            closes: Hourly close prices, most recent last. Need >=720+1 for 30d.
            current_drawdown_pct: Current portfolio drawdown as positive percentage.
        """
        prices = np.array(closes, dtype=np.float64)

        if len(prices) < 2:
            return self._empty_output(asset, current_drawdown_pct)

        # --- Log returns ---
        log_returns = np.diff(np.log(prices))

        # --- Realized vol at multiple horizons (hourly data, annualized) ---
        annualize_factor = np.sqrt(8760) * 100

        # 1d = 24 hourly returns
        vol_1d = self._windowed_vol(log_returns, 24) * annualize_factor
        # 7d = 168 hourly returns
        vol_7d = self._windowed_vol(log_returns, 168) * annualize_factor
        # 30d = 720 hourly returns
        vol_30d = self._windowed_vol(log_returns, 720) * annualize_factor

        # --- Vol z-score: how unusual is current vol vs 30d distribution ---
        vol_zscore = self._compute_vol_zscore(log_returns, vol_1d, annualize_factor)

        # --- Vol regime ---
        vol_regime = self._classify_regime(vol_1d)

        # --- Vol scalar ---
        effective_vol = max(vol_1d, self.vol_floor_pct)
        vol_scalar = float(np.clip(self.target_vol_pct / effective_vol, 0.1, 1.5))

        # --- Drawdown scalar: linear 1.0 at dd<=5%, 0.0 at dd>=10% ---
        dd = current_drawdown_pct
        if dd <= 5.0:
            drawdown_scalar = 1.0
        elif dd >= 10.0:
            drawdown_scalar = 0.0
        else:
            drawdown_scalar = 1.0 - (dd - 5.0) / 5.0

        # --- Combined exposure multiplier ---
        combined = min(vol_scalar, drawdown_scalar)

        # --- Risk state ---
        risk_state = self._classify_risk_state(combined, dd)

        return VolatilityOutput(
            asset=asset,
            realized_vol_1d=round(vol_1d, 2),
            realized_vol_7d=round(vol_7d, 2),
            realized_vol_30d=round(vol_30d, 2),
            vol_zscore=round(vol_zscore, 2),
            vol_regime=vol_regime,
            target_vol_pct=self.target_vol_pct,
            vol_scalar=round(vol_scalar, 4),
            current_drawdown_pct=round(dd, 2),
            drawdown_scalar=round(drawdown_scalar, 4),
            combined_exposure_multiplier=round(combined, 4),
            risk_state=risk_state,
        )

    def _windowed_vol(self, log_returns: np.ndarray, window: int) -> float:
        """Compute std of the last `window` log returns. Returns 0 if insufficient data."""
        if len(log_returns) < 2:
            return 0.0
        n = min(window, len(log_returns))
        return float(np.std(log_returns[-n:], ddof=1))

    def _compute_vol_zscore(
        self, log_returns: np.ndarray, current_vol_1d: float, annualize: float
    ) -> float:
        """Z-score of 1d vol vs rolling 30d distribution of daily vols.

        Computes 24-hour rolling vol for each day in the last 30 days,
        then z-scores current vol against that distribution.
        """
        window = 24  # 1d in hours
        total_needed = 720  # 30 days of hourly data

        if len(log_returns) < window * 2:
            return 0.0

        # Compute rolling 1d vols over available history (up to 30d)
        usable = min(len(log_returns), total_needed)
        data = log_returns[-usable:]

        rolling_vols = []
        for i in range(window, len(data) + 1, window):
            chunk = data[i - window : i]
            if len(chunk) >= 2:
                v = float(np.std(chunk, ddof=1)) * annualize
                rolling_vols.append(v)

        if len(rolling_vols) < 3:
            return 0.0

        vol_arr = np.array(rolling_vols)
        mean_vol = float(np.mean(vol_arr))
        std_vol = float(np.std(vol_arr, ddof=1))

        if std_vol < 1e-12:
            return 0.0

        return (current_vol_1d - mean_vol) / std_vol

    @staticmethod
    def _classify_regime(vol_1d: float) -> VolRegime:
        if vol_1d > 80:
            return "extreme"
        elif vol_1d > 50:
            return "elevated"
        elif vol_1d > 20:
            return "normal"
        else:
            return "low"

    @staticmethod
    def _classify_risk_state(combined: float, drawdown_pct: float) -> RiskState:
        if combined <= 0 or drawdown_pct >= 10.0:
            return "emergency"
        elif combined <= 0.3:
            return "minimal"
        elif combined < 0.8:
            return "reduced"
        else:
            return "full_risk"

    def _empty_output(self, asset: str, drawdown: float) -> VolatilityOutput:
        return VolatilityOutput(
            asset=asset,
            realized_vol_1d=0.0,
            realized_vol_7d=0.0,
            realized_vol_30d=0.0,
            vol_zscore=0.0,
            vol_regime="low",
            target_vol_pct=self.target_vol_pct,
            vol_scalar=1.5,
            current_drawdown_pct=drawdown,
            drawdown_scalar=1.0 if drawdown <= 5.0 else max(0.0, 1.0 - (drawdown - 5.0) / 5.0),
            combined_exposure_multiplier=1.5 if drawdown <= 5.0 else max(0.0, 1.0 - (drawdown - 5.0) / 5.0),
            risk_state="full_risk" if drawdown < 5.0 else "reduced",
        )
