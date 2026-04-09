"""Measured Move ORB Strategy -- session-open measured move with consolidation breakout.

Measures the initial move after session open, waits for consolidation, then trades
the breakout with measured-move targets. Pure numpy implementation.
"""

from datetime import datetime, timedelta, timezone

from wolfpack.exchanges.base import Candle
from wolfpack.price_utils import round_price
from wolfpack.strategies.base import Strategy

# Session open times in UTC (minutes from midnight)
SESSION_OPENS_UTC = {
    "ny": 13 * 60 + 30,      # 13:30 UTC (9:30 ET)
    "london": 8 * 60,         # 08:00 UTC
    "asia": 0,                # 00:00 UTC
}


class MeasuredMoveStrategy(Strategy):
    name = "measured_move"
    description = "Measured move breakout after session-open consolidation"
    parameters = {
        "session": {
            "type": "str",
            "default": "ny",
            "min": None,
            "max": None,
            "desc": "Session to trade: ny, london, asia",
        },
        "opening_range_minutes": {
            "type": "int",
            "default": 15,
            "min": 5,
            "max": 30,
            "desc": "Minutes after session open to measure the initial move",
        },
        "consolidation_lookback": {
            "type": "int",
            "default": 6,
            "min": 3,
            "max": 12,
            "desc": "Number of bars to check for consolidation",
        },
        "consolidation_threshold": {
            "type": "float",
            "default": 0.50,
            "min": 0.2,
            "max": 1.0,
            "desc": "Max consolidation range as fraction of measured move",
        },
        "max_risk_pct": {
            "type": "float",
            "default": 0.30,
            "min": 0.1,
            "max": 0.5,
            "desc": "Max risk as fraction of measured move",
        },
        "size_pct": {
            "type": "float",
            "default": 12.0,
            "min": 1.0,
            "max": 25.0,
            "desc": "Position size as % of equity",
        },
        "max_trades_per_session": {
            "type": "int",
            "default": 3,
            "min": 1,
            "max": 5,
            "desc": "Maximum trades per session window",
        },
    }

    @property
    def warmup_bars(self) -> int:
        return 20

    def evaluate(
        self, candles: list[Candle], current_idx: int, **params
    ) -> dict | None:
        session = params.get("session", "ny")
        opening_range_minutes = params.get("opening_range_minutes", 15)
        consolidation_lookback = params.get("consolidation_lookback", 6)
        consolidation_threshold = params.get("consolidation_threshold", 0.50)
        max_risk_pct = params.get("max_risk_pct", 0.30)
        size_pct = params.get("size_pct", 12.0)

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
        if current_dt < session_open_dt:
            session_open_dt -= timedelta(days=1)

        opening_end_dt = session_open_dt + timedelta(minutes=opening_range_minutes)

        # Only trade after opening range, within 4 hours of session open
        if current_dt <= opening_end_dt:
            return None
        if current_dt > session_open_dt + timedelta(hours=4):
            return None

        # Find the first candle after session open and measure high-low
        or_high = None
        or_low = None
        for c in visible:
            c_dt = self._ts_to_dt(c.timestamp)
            if session_open_dt <= c_dt < opening_end_dt:
                if or_high is None or c.high > or_high:
                    or_high = c.high
                if or_low is None or c.low < or_low:
                    or_low = c.low

        if or_high is None or or_low is None:
            return None

        measured_move = or_high - or_low
        if measured_move <= 0:
            return None

        # Check consolidation: last N bars range < threshold * measured_move
        if len(visible) < consolidation_lookback:
            return None

        lookback = visible[-consolidation_lookback:]
        consol_high = max(c.high for c in lookback)
        consol_low = min(c.low for c in lookback)
        consol_range = consol_high - consol_low

        if consol_range >= consolidation_threshold * measured_move:
            return None  # not consolidated enough

        # Check for prior breakouts this session (limit trades)
        breakout_count = 0
        for c in visible[:-1]:
            c_dt = self._ts_to_dt(c.timestamp)
            if c_dt > opening_end_dt and c_dt > session_open_dt:
                if c.close > consol_high or c.close < consol_low:
                    breakout_count += 1
        max_trades = params.get("max_trades_per_session", 3)
        if breakout_count >= max_trades:
            return None

        risk = measured_move * max_risk_pct

        # Long breakout above consolidation high
        if current.close > consol_high:
            return {
                "symbol": "",
                "direction": "long",
                "conviction": 70,
                "entry_price": current.close,
                "stop_loss": round_price(current.close - risk),
                "take_profit": round_price(consol_low + measured_move),
                "size_pct": size_pct,
            }

        # Short breakout below consolidation low
        if current.close < consol_low:
            return {
                "symbol": "",
                "direction": "short",
                "conviction": 70,
                "entry_price": current.close,
                "stop_loss": round_price(current.close + risk),
                "take_profit": round_price(consol_high - measured_move),
                "size_pct": size_pct,
            }

        return None

    @staticmethod
    def _ts_to_dt(timestamp: int) -> datetime:
        """Convert candle timestamp (epoch ms or seconds) to UTC datetime."""
        if timestamp > 1e12:
            return datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
