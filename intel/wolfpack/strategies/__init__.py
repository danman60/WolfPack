"""Strategy registry for the backtesting system."""

from wolfpack.strategies.base import Strategy
from wolfpack.strategies.ema_crossover import EMACrossoverStrategy
from wolfpack.strategies.orb_session import ORBSessionStrategy
from wolfpack.strategies.regime_momentum import RegimeMomentumStrategy
from wolfpack.strategies.vol_breakout import VolBreakoutStrategy

STRATEGIES: dict[str, type[Strategy]] = {
    "regime_momentum": RegimeMomentumStrategy,
    "ema_crossover": EMACrossoverStrategy,
    "vol_breakout": VolBreakoutStrategy,
    "orb_session": ORBSessionStrategy,
}

__all__ = ["STRATEGIES", "Strategy"]
