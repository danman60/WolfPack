"""Data freshness tracker — per-symbol, per-source staleness detection with price freeze alerts.

Tracks when each data source was last updated for each symbol and provides
freshness checks with configurable thresholds. Detects price freezes by
monitoring consecutive identical closes.
"""

import time
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Configurable thresholds per source (seconds)
DEFAULT_THRESHOLDS = {
    "candles": 600,       # 10 minutes
    "funding": 1800,      # 30 minutes
    "orderbook": 120,     # 2 minutes
    "whale_trades": 3600, # 1 hour
}

# Price freeze detection: if last N closes identical within tolerance
FREEZE_WINDOW = 5
FREEZE_TOLERANCE = 0.0001  # 0.01%


class FreshnessTracker:
    """Tracks data freshness per symbol per source, with price freeze detection."""

    def __init__(self, thresholds: Optional[Dict[str, int]] = None):
        self.thresholds = thresholds or DEFAULT_THRESHOLDS
        self._timestamps: Dict[str, Dict[str, float]] = {}   # symbol -> source -> timestamp
        self._recent_closes: Dict[str, List[float]] = {}     # symbol -> last N close prices

    def record_update(self, symbol: str, source: str, timestamp: Optional[float] = None):
        """Record that we received fresh data for a symbol from a source."""
        if symbol not in self._timestamps:
            self._timestamps[symbol] = {}
        self._timestamps[symbol][source] = timestamp or time.time()

    def record_close_price(self, symbol: str, close: float):
        """Track recent close prices for freeze detection."""
        if symbol not in self._recent_closes:
            self._recent_closes[symbol] = []
        self._recent_closes[symbol].append(close)
        # Keep only last FREEZE_WINDOW prices
        if len(self._recent_closes[symbol]) > FREEZE_WINDOW:
            self._recent_closes[symbol] = self._recent_closes[symbol][-FREEZE_WINDOW:]

    def is_price_frozen(self, symbol: str) -> bool:
        """Detect if price is frozen (consecutive identical closes)."""
        closes = self._recent_closes.get(symbol, [])
        if len(closes) < FREEZE_WINDOW:
            return False

        ref = closes[0]
        if ref == 0:
            return True

        for c in closes[1:]:
            if abs(c - ref) / ref > FREEZE_TOLERANCE:
                return False

        logger.warning(
            f"Price freeze detected for {symbol}: last {FREEZE_WINDOW} closes identical ({ref})"
        )
        return True

    def check_freshness(self, symbol: str) -> dict:
        """Check data freshness for a symbol across all sources."""
        now = time.time()
        sources = self._timestamps.get(symbol, {})
        stale_sources = []
        age_seconds = {}

        for source, threshold in self.thresholds.items():
            last_update = sources.get(source)
            if last_update is None:
                stale_sources.append(source)
                age_seconds[source] = None  # never received
            else:
                age = now - last_update
                age_seconds[source] = round(age, 1)
                if age > threshold:
                    stale_sources.append(source)

        frozen = self.is_price_frozen(symbol)
        if frozen:
            stale_sources.append("price_frozen")

        return {
            "is_fresh": len(stale_sources) == 0,
            "stale_sources": stale_sources,
            "age_seconds": age_seconds,
            "price_frozen": frozen,
        }

    def get_all_freshness(self) -> Dict[str, dict]:
        """Get freshness status for all tracked symbols."""
        return {symbol: self.check_freshness(symbol) for symbol in self._timestamps}

    def should_skip_symbol(self, symbol: str) -> Tuple[bool, str]:
        """Determine if a symbol should be skipped this cycle."""
        freshness = self.check_freshness(symbol)

        if freshness["price_frozen"]:
            return True, f"Price frozen for {symbol} (last {FREEZE_WINDOW} closes identical)"

        # Skip if candles are stale (primary data source)
        if "candles" in freshness["stale_sources"]:
            age = freshness["age_seconds"].get("candles")
            reason = f"Candle data stale for {symbol}" + (
                f" ({age:.0f}s old)" if age else " (never received)"
            )
            return True, reason

        return False, ""

    def get_max_data_age(self, symbol: str) -> float:
        """Return the age (seconds) of the oldest tracked source for a symbol.

        Used for backward-compatible data_age_s parameter in circuit_breaker.check().
        Returns 0.0 if no data has been recorded yet.
        """
        sources = self._timestamps.get(symbol, {})
        if not sources:
            return 0.0
        now = time.time()
        return max(now - ts for ts in sources.values())
