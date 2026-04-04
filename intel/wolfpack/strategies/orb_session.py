"""ORB Session Breakout -- crypto adaptation of Trader Tom's School Run Strategy.

Defines observation windows around major session opens (NY, London, Asia).
After the observation window, enters on breakout of the range high/low.
"""

from datetime import datetime, timezone, timedelta

from wolfpack.exchanges.base import Candle
from wolfpack.strategies.base import Strategy


# Session open times in UTC
SESSION_OPENS_UTC = {
    "ny": 13 * 60 + 30,      # 13:30 UTC (9:30 ET)
    "london": 8 * 60,         # 08:00 UTC
    "asia": 0,                # 00:00 UTC
}


class ORBSessionStrategy(Strategy):
    name = "orb_session"
    description = "Opening Range Breakout around major session opens (NY, London, Asia)"
    parameters = {
        "observation_minutes": {
            "type": "int",
            "default": 25,
            "min": 10,
            "max": 60,
            "desc": "Minutes after session open to observe the range",
        },
        "session": {
            "type": "str",
            "default": "ny",
            "min": None,
            "max": None,
            "desc": "Session to trade: ny, london, asia",
        },
        "size_pct": {
            "type": "float",
            "default": 12.0,
            "min": 1.0,
            "max": 25.0,
            "desc": "Position size as % of equity",
        },
        "stop_atr_mult": {
            "type": "float",
            "default": 1.5,
            "min": 0.5,
            "max": 5.0,
            "desc": "ATR multiplier for stop loss distance",
        },
        "use_anti_srs": {
            "type": "bool",
            "default": True,
            "min": None,
            "max": None,
            "desc": "Enable Anti-SRS: reverse breakout direction when inside overnight range",
        },
        "overnight_hours": {
            "type": "int",
            "default": 6,
            "min": 2,
            "max": 12,
            "desc": "Hours before session open to calculate overnight range",
        },
    }

    @property
    def warmup_bars(self) -> int:
        """Need enough bars for ATR (14 periods) + observation window."""
        return 20

    def evaluate(
        self, candles: list[Candle], current_idx: int, **params
    ) -> dict | None:
        """Evaluate ORB breakout at the current bar.

        Uses 5-minute candles. Determines session open, builds the observation
        range, then checks for breakout after the window closes.
        """
        observation_minutes = params.get("observation_minutes", 25)
        session = params.get("session", "ny")
        size_pct = params.get("size_pct", 12.0)
        stop_atr_mult = params.get("stop_atr_mult", 1.5)
        use_anti_srs = params.get("use_anti_srs", True)
        overnight_hours = params.get("overnight_hours", 6)

        visible = candles[: current_idx + 1]
        if len(visible) < self.warmup_bars:
            return None

        current = visible[-1]
        current_dt = self._ts_to_dt(current.timestamp)
        session_open_minutes = SESSION_OPENS_UTC.get(session, SESSION_OPENS_UTC["ny"])

        # Determine today's session open time
        session_open_dt = current_dt.replace(
            hour=session_open_minutes // 60,
            minute=session_open_minutes % 60,
            second=0,
            microsecond=0,
        )
        # If current time is before today's session open, use yesterday's
        if current_dt < session_open_dt:
            session_open_dt -= timedelta(days=1)

        observation_end_dt = session_open_dt + timedelta(minutes=observation_minutes)

        # Only trade after observation window closes, within the session day
        if current_dt <= observation_end_dt:
            return None

        # Don't trade more than 4 hours after session open (session is stale)
        if current_dt > session_open_dt + timedelta(hours=4):
            return None

        # Build observation range from candles within the window
        range_high = None
        range_low = None
        for c in visible:
            c_dt = self._ts_to_dt(c.timestamp)
            if session_open_dt <= c_dt < observation_end_dt:
                if range_high is None or c.high > range_high:
                    range_high = c.high
                if range_low is None or c.low < range_low:
                    range_low = c.low

        if range_high is None or range_low is None:
            return None

        # Check if we already traded this session (look for a breakout bar after obs window)
        for c in visible[:-1]:
            c_dt = self._ts_to_dt(c.timestamp)
            if c_dt > observation_end_dt and c_dt > session_open_dt:
                if c.close > range_high or c.close < range_low:
                    # Already had a breakout this session
                    return None

        # Calculate ATR for stop distance
        atr = self._compute_atr(visible, 14)
        if atr <= 0:
            return None

        stop_distance = atr * stop_atr_mult
        tp_distance = stop_distance * 2  # 2R target

        # Anti-SRS: calculate overnight range and classify
        reverse_breakout = False
        if use_anti_srs:
            onr_start_dt = session_open_dt - timedelta(hours=overnight_hours)
            onr_high = None
            onr_low = None
            for c in visible:
                c_dt = self._ts_to_dt(c.timestamp)
                if onr_start_dt <= c_dt < session_open_dt:
                    if onr_high is None or c.high > onr_high:
                        onr_high = c.high
                    if onr_low is None or c.low < onr_low:
                        onr_low = c.low

            if onr_high is not None and onr_low is not None:
                # Classify: ABOVE_ONR, BELOW_ONR, INSIDE_ONR
                if range_low > onr_high:
                    pass  # ABOVE_ONR: standard breakout
                elif range_high < onr_low:
                    pass  # BELOW_ONR: standard breakout
                else:
                    # INSIDE_ONR: reverse breakout direction
                    reverse_breakout = True

        # Check for breakout on current bar
        if current.close > range_high:
            direction = "short" if reverse_breakout else "long"
            if direction == "long":
                return {
                    "symbol": "",
                    "direction": "long",
                    "conviction": 75,
                    "entry_price": current.close,
                    "stop_loss": round(current.close - stop_distance, 2),
                    "take_profit": round(current.close + tp_distance, 2),
                    "size_pct": size_pct,
                }
            else:
                return {
                    "symbol": "",
                    "direction": "short",
                    "conviction": 70,
                    "entry_price": current.close,
                    "stop_loss": round(current.close + stop_distance, 2),
                    "take_profit": round(current.close - tp_distance, 2),
                    "size_pct": size_pct,
                }
        elif current.close < range_low:
            direction = "long" if reverse_breakout else "short"
            if direction == "short":
                return {
                    "symbol": "",
                    "direction": "short",
                    "conviction": 75,
                    "entry_price": current.close,
                    "stop_loss": round(current.close + stop_distance, 2),
                    "take_profit": round(current.close - tp_distance, 2),
                    "size_pct": size_pct,
                }
            else:
                return {
                    "symbol": "",
                    "direction": "long",
                    "conviction": 70,
                    "entry_price": current.close,
                    "stop_loss": round(current.close - stop_distance, 2),
                    "take_profit": round(current.close + tp_distance, 2),
                    "size_pct": size_pct,
                }

        return None

    @staticmethod
    def _ts_to_dt(timestamp: int) -> datetime:
        """Convert candle timestamp (epoch ms or seconds) to UTC datetime."""
        if timestamp > 1e12:
            # Epoch milliseconds
            return datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)

    @staticmethod
    def _compute_atr(candles: list[Candle], period: int = 14) -> float:
        """Compute Average True Range over the last `period` candles."""
        if len(candles) < period + 1:
            return 0.0

        true_ranges: list[float] = []
        for i in range(len(candles) - period, len(candles)):
            c = candles[i]
            prev_close = candles[i - 1].close
            tr = max(
                c.high - c.low,
                abs(c.high - prev_close),
                abs(c.low - prev_close),
            )
            true_ranges.append(tr)

        return sum(true_ranges) / len(true_ranges) if true_ranges else 0.0
