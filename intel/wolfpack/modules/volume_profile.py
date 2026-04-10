"""Volume Profile — OHLCV-approximated volume distribution analysis.

Computes POC, Value Area, HVN/LVN, and profile shape from candle data
(no tick data required).
"""

import numpy as np
from pydantic import BaseModel

from wolfpack.exchanges.base import Candle


class VolumeProfile(BaseModel):
    # Point of Control — price with highest volume concentration
    poc: float

    # Value Area (70% of total volume)
    value_area_high: float
    value_area_low: float

    # Volume nodes
    hvn: list[float]  # High Volume Nodes (top 3-5 price levels by volume)
    lvn: list[float]  # Low Volume Nodes (bottom 3-5, fast-move zones)

    # Context
    price_vs_poc: str  # "above_poc", "below_poc", "at_poc"
    price_in_value_area: bool

    # Volume profile shape
    profile_shape: str  # "normal", "bimodal", "ledge"

    timeframe: str  # "1d", "5d"
    total_volume: float
    num_bins: int


# Module-level cache: symbol -> (last_candle_timestamp, VolumeProfile)
_profile_cache: dict[str, tuple[int, VolumeProfile]] = {}


class VolumeProfileModule:
    """Approximates volume profile from OHLCV candle data."""

    def __init__(self, num_bins: int = 50):
        self.num_bins = num_bins

    def analyze(
        self, candles_1h: list[Candle], symbol: str, window: int = 24
    ) -> VolumeProfile | None:
        if len(candles_1h) < 10:
            return None

        latest_ts = candles_1h[-1].timestamp
        if symbol in _profile_cache and _profile_cache[symbol][0] == latest_ts:
            return _profile_cache[symbol][1]

        n = min(window, len(candles_1h))
        candles = candles_1h[-n:]
        timeframe = "1d" if window <= 24 else "5d"

        result = self._compute(candles, timeframe)
        if result:
            _profile_cache[symbol] = (latest_ts, result)
        return result

    def _compute(self, candles: list[Candle], timeframe: str) -> VolumeProfile | None:
        current_price = candles[-1].close

        price_low = min(c.low for c in candles)
        price_high = max(c.high for c in candles)
        price_range = price_high - price_low

        if price_range <= 0:
            return None

        bin_size = price_range / self.num_bins
        bins = np.zeros(self.num_bins, dtype=np.float64)

        # Distribute each candle's volume across the bins its range covers
        for c in candles:
            if c.volume <= 0:
                continue
            low_bin = max(0, int((c.low - price_low) / bin_size))
            high_bin = min(self.num_bins - 1, int((c.high - price_low) / bin_size))
            if high_bin < low_bin:
                high_bin = low_bin
            num_covered = high_bin - low_bin + 1
            vol_per_bin = c.volume / num_covered
            for b in range(low_bin, high_bin + 1):
                bins[b] += vol_per_bin

        total_volume = float(np.sum(bins))
        if total_volume <= 0:
            return None

        # POC: bin with highest volume
        poc_idx = int(np.argmax(bins))
        poc_price = price_low + (poc_idx + 0.5) * bin_size

        # Value Area: expand from POC until 70% of volume captured
        va_low_idx = poc_idx
        va_high_idx = poc_idx
        va_volume = float(bins[poc_idx])
        target_volume = total_volume * 0.70

        while va_volume < target_volume:
            look_down = bins[va_low_idx - 1] if va_low_idx > 0 else -1
            look_up = bins[va_high_idx + 1] if va_high_idx < self.num_bins - 1 else -1

            if look_down < 0 and look_up < 0:
                break

            if look_up >= look_down:
                va_high_idx += 1
                va_volume += float(bins[va_high_idx])
            else:
                va_low_idx -= 1
                va_volume += float(bins[va_low_idx])

        va_high = price_low + (va_high_idx + 1) * bin_size
        va_low = price_low + va_low_idx * bin_size

        # HVN: top 5 bins by volume (midpoint prices)
        sorted_indices = np.argsort(bins)[::-1]
        nonzero_bins = [i for i in sorted_indices if bins[i] > 0]
        hvn_indices = nonzero_bins[:5]
        hvn = [round(price_low + (i + 0.5) * bin_size, 2) for i in hvn_indices]

        # LVN: bottom 5 non-zero bins
        lvn_indices = list(reversed(nonzero_bins))[:5]
        lvn = [round(price_low + (i + 0.5) * bin_size, 2) for i in lvn_indices]

        # Price vs POC
        poc_tolerance = bin_size
        if abs(current_price - poc_price) < poc_tolerance:
            price_vs_poc = "at_poc"
        elif current_price > poc_price:
            price_vs_poc = "above_poc"
        else:
            price_vs_poc = "below_poc"

        price_in_va = va_low <= current_price <= va_high

        # Profile shape classification
        profile_shape = self._classify_shape(bins)

        return VolumeProfile(
            poc=round(poc_price, 2),
            value_area_high=round(va_high, 2),
            value_area_low=round(va_low, 2),
            hvn=hvn,
            lvn=lvn,
            price_vs_poc=price_vs_poc,
            price_in_value_area=price_in_va,
            profile_shape=profile_shape,
            timeframe=timeframe,
            total_volume=round(total_volume, 2),
            num_bins=self.num_bins,
        )

    def _classify_shape(self, bins: np.ndarray) -> str:
        """Classify the volume profile shape."""
        if len(bins) < 3:
            return "normal"

        sorted_indices = np.argsort(bins)[::-1]
        top1 = sorted_indices[0]
        top2 = sorted_indices[1]

        # Bimodal: top 2 bins are non-adjacent
        if abs(int(top1) - int(top2)) > 1:
            return "bimodal"

        # Ledge: top 3 adjacent and within 10% volume of each other
        if len(sorted_indices) >= 3:
            top3 = sorted_indices[2]
            top3_vals = sorted([int(top1), int(top2), int(top3)])
            if top3_vals[2] - top3_vals[0] <= 2:  # adjacent
                vols = [float(bins[i]) for i in [top1, top2, top3]]
                max_vol = max(vols)
                if max_vol > 0 and all(v >= max_vol * 0.90 for v in vols):
                    return "ledge"

        return "normal"
