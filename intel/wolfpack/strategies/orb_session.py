"""ORB Session Breakout -- crypto adaptation of Trader Tom's School Run Strategy.

Defines observation windows around major session opens (NY, London, Asia).
After the observation window, enters on breakout of the range high/low.

With FVG filter enabled (default), requires:
  1. Fair Value Gap (3-candle displacement) on breakout
  2. Price retests the FVG zone
  3. Engulfing confirmation candle before entry
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
        "require_fvg": {
            "type": "bool",
            "default": True,
            "min": None,
            "max": None,
            "desc": "Require Fair Value Gap displacement + retest engulfing for entry",
        },
        "target_rr": {
            "type": "float",
            "default": 3.0,
            "min": 1.0,
            "max": 10.0,
            "desc": "Risk:reward ratio for take-profit target",
        },
    }

    def __init__(self):
        self._fvg_zone = None          # (fvg_high, fvg_low)
        self._fvg_direction = None     # "long" or "short"
        self._retest_candle = None     # candle that retested the FVG
        self._awaiting_retest = False
        self._awaiting_engulf = False
        self._session_ts = None        # reset state per session
        self._breakout_bar_idx = None
        self._session_traded = False

    def _reset_fvg_state(self):
        """Clear all FVG tracking state."""
        self._fvg_zone = None
        self._fvg_direction = None
        self._retest_candle = None
        self._awaiting_retest = False
        self._awaiting_engulf = False
        self._breakout_bar_idx = None
        self._session_traded = False

    def _detect_fvg(self, candles, breakout_idx, direction, atr):
        """Check if candles around breakout_idx form a Fair Value Gap.

        Bullish FVG: candles[i-1].high < candles[i+1].low (gap above and below expansive middle candle)
        Bearish FVG: candles[i-1].low > candles[i+1].high
        Middle candle body must be > 0.5 * ATR (expansive).

        Returns (fvg_high, fvg_low) or None.
        """
        if breakout_idx < 1 or breakout_idx + 1 >= len(candles):
            return None

        prev_c = candles[breakout_idx - 1]
        mid_c = candles[breakout_idx]
        next_c = candles[breakout_idx + 1]

        # Middle candle must be expansive
        body = abs(mid_c.close - mid_c.open)
        if body < 0.5 * atr:
            return None

        if direction == "long":
            # Bullish FVG: gap between prev high and next low
            if prev_c.high < next_c.low:
                fvg_high = next_c.low
                fvg_low = prev_c.high
                return (fvg_high, fvg_low)
        else:
            # Bearish FVG: gap between prev low and next high
            if prev_c.low > next_c.high:
                fvg_high = prev_c.low
                fvg_low = next_c.high
                return (fvg_high, fvg_low)

        return None

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
        require_fvg = params.get("require_fvg", True)
        target_rr = params.get("target_rr", 3.0)

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

        # Reset FVG state on new session
        session_key = session_open_dt.isoformat()
        if self._session_ts != session_key:
            self._session_ts = session_key
            self._reset_fvg_state()

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

        # Calculate ATR for stop distance
        atr = self._compute_atr(visible, 14)
        if atr <= 0:
            return None

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
                if range_low > onr_high:
                    pass  # ABOVE_ONR: standard breakout
                elif range_high < onr_low:
                    pass  # BELOW_ONR: standard breakout
                else:
                    # INSIDE_ONR: reverse breakout direction
                    reverse_breakout = True

        # --- FVG mode ---
        if require_fvg:
            return self._evaluate_fvg_mode(
                visible, current, current_idx, current_dt,
                observation_end_dt, session_open_dt,
                range_high, range_low, atr,
                reverse_breakout, size_pct, target_rr,
            )

        # --- Legacy mode (no FVG) ---
        # Check if we already traded this session
        for c in visible[:-1]:
            c_dt = self._ts_to_dt(c.timestamp)
            if c_dt > observation_end_dt and c_dt > session_open_dt:
                if c.close > range_high or c.close < range_low:
                    return None

        stop_distance = atr * stop_atr_mult
        tp_distance = stop_distance * target_rr

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

    def _evaluate_fvg_mode(
        self, visible, current, current_idx, current_dt,
        observation_end_dt, session_open_dt,
        range_high, range_low, atr,
        reverse_breakout, size_pct, target_rr,
    ) -> dict | None:
        """FVG displacement + retest engulfing entry logic."""

        # Already completed an entry this session
        if self._session_traded:
            return None

        # Timeout: >20 bars since breakout with no completed entry
        if self._breakout_bar_idx is not None:
            bars_since = current_idx - self._breakout_bar_idx
            if bars_since > 20:
                self._reset_fvg_state()
                return None

        # --- State: awaiting engulfing confirmation ---
        if self._awaiting_engulf and self._retest_candle is not None:
            if self._fvg_direction == "long":
                if current.close > self._retest_candle.high:
                    entry = current.close
                    stop = round(self._retest_candle.low * 0.999, 2)
                    risk = entry - stop
                    tp = round(entry + risk * target_rr, 2)
                    self._session_traded = True
                    return {
                        "symbol": "",
                        "direction": "long",
                        "conviction": 80,
                        "entry_price": entry,
                        "stop_loss": stop,
                        "take_profit": tp,
                        "size_pct": size_pct,
                    }
            else:  # short
                if current.close < self._retest_candle.low:
                    entry = current.close
                    stop = round(self._retest_candle.high * 1.001, 2)
                    risk = stop - entry
                    tp = round(entry - risk * target_rr, 2)
                    self._session_traded = True
                    return {
                        "symbol": "",
                        "direction": "short",
                        "conviction": 80,
                        "entry_price": entry,
                        "stop_loss": stop,
                        "take_profit": tp,
                        "size_pct": size_pct,
                    }
            return None

        # --- State: awaiting retest ---
        if self._awaiting_retest and self._fvg_zone is not None:
            fvg_high, fvg_low = self._fvg_zone
            if self._fvg_direction == "long":
                # Price dips into FVG zone
                if current.low <= fvg_high:
                    self._retest_candle = current
                    self._awaiting_retest = False
                    self._awaiting_engulf = True
            else:  # short
                # Price rallies into FVG zone
                if current.high >= fvg_low:
                    self._retest_candle = current
                    self._awaiting_retest = False
                    self._awaiting_engulf = True
            return None

        # --- State: no FVG yet — look for breakout + FVG ---
        # Check for breakout on current bar
        is_breakout_high = current.close > range_high
        is_breakout_low = current.close < range_low

        if not is_breakout_high and not is_breakout_low:
            return None

        # Check we haven't already had a breakout bar earlier this session
        for c in visible[:-1]:
            c_dt = self._ts_to_dt(c.timestamp)
            if c_dt > observation_end_dt and c_dt > session_open_dt:
                if c.close > range_high or c.close < range_low:
                    # Already had a breakout — mark session as done
                    self._session_traded = True
                    return None

        if is_breakout_high:
            direction = "short" if reverse_breakout else "long"
        else:
            direction = "long" if reverse_breakout else "short"

        # Try to detect FVG around the breakout bar
        # current_idx is the breakout bar; we need idx+1 to exist for FVG detection.
        # Since we're evaluating bar-by-bar, check with the bars we have.
        # Use visible indices: breakout is at len(visible)-1
        bo_idx = len(visible) - 1
        fvg = self._detect_fvg(visible, bo_idx - 1, direction, atr)
        if fvg is None:
            # Also try with breakout bar as middle
            fvg = self._detect_fvg(visible, bo_idx, direction, atr)

        if fvg is not None:
            self._fvg_zone = fvg
            self._fvg_direction = direction
            self._awaiting_retest = True
            self._breakout_bar_idx = current_idx
        # If no FVG found, no trade — state stays reset, next bar can try again

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
