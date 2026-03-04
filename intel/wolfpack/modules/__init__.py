"""
WolfPack Quantitative Modules — 8 intelligence modules from the WolfPack Toolkit spec.

Each module processes raw exchange data and produces structured signals
that feed into the LLM agents for interpretation.
"""

from wolfpack.modules.regime import RegimeDetector
from wolfpack.modules.liquidity import LiquidityIntel
from wolfpack.modules.funding import FundingIntel
from wolfpack.modules.correlation import CorrelationIntel
from wolfpack.modules.volatility import VolatilitySignal
from wolfpack.modules.circuit_breaker import CircuitBreaker
from wolfpack.modules.execution import ExecutionTiming
from wolfpack.modules.backtest import BacktestHarness
from wolfpack.modules.social_sentiment import SocialSentimentAnalyzer
from wolfpack.modules.whale_tracker import WhaleTracker

__all__ = [
    "RegimeDetector",
    "LiquidityIntel",
    "FundingIntel",
    "CorrelationIntel",
    "VolatilitySignal",
    "CircuitBreaker",
    "ExecutionTiming",
    "BacktestHarness",
    "SocialSentimentAnalyzer",
    "WhaleTracker",
]
