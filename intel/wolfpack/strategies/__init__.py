"""Strategy registry for the backtesting system."""

from wolfpack.strategies.band_fade import BandFadeStrategy
from wolfpack.strategies.base import Strategy
from wolfpack.strategies.ema_crossover import EMACrossoverStrategy
from wolfpack.strategies.mean_reversion import MeanReversionStrategy
from wolfpack.strategies.measured_move import MeasuredMoveStrategy
from wolfpack.strategies.orb_session import ORBSessionStrategy
from wolfpack.strategies.range_breakout import RangeBreakoutStrategy
from wolfpack.strategies.regime_momentum import RegimeMomentumStrategy
from wolfpack.strategies.slow_drift_follow import SlowDriftFollowStrategy
from wolfpack.strategies.trend_pullback import TrendPullbackStrategy
from wolfpack.strategies.turtle_donchian import TurtleDonchianStrategy
from wolfpack.strategies.vol_breakout import VolBreakoutStrategy

STRATEGIES: dict[str, type[Strategy]] = {
    "regime_momentum": RegimeMomentumStrategy,
    "ema_crossover": EMACrossoverStrategy,
    "vol_breakout": VolBreakoutStrategy,
    "orb_session": ORBSessionStrategy,
    "turtle_donchian": TurtleDonchianStrategy,
    "measured_move": MeasuredMoveStrategy,
    "mean_reversion": MeanReversionStrategy,
    "band_fade": BandFadeStrategy,
    "trend_pullback": TrendPullbackStrategy,
    "slow_drift_follow": SlowDriftFollowStrategy,
    "range_breakout": RangeBreakoutStrategy,
}

__all__ = ["STRATEGIES", "Strategy"]
