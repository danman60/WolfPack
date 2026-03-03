"""Base class for backtest strategies.

Strategies produce recommendation dicts identical to what The Brief agent outputs.
This ensures production parity — the backtest engine processes recommendations
through PaperTradingEngine the same way the approval endpoint does.
"""

from abc import ABC, abstractmethod

from wolfpack.exchanges.base import Candle


class Strategy(ABC):
    """Abstract strategy that evaluates candles bar-by-bar.

    Subclasses implement evaluate() which receives all candles up to
    current_idx (look-back window) and returns a recommendation dict
    or None. This prevents look-ahead bias.
    """

    name: str
    description: str
    parameters: dict[str, dict]  # {name: {type, default, min, max, desc}}

    @abstractmethod
    def evaluate(
        self, candles: list[Candle], current_idx: int, **params
    ) -> dict | None:
        """Evaluate at a single bar.

        Args:
            candles: Full candle array (only use candles[:current_idx+1])
            current_idx: Index of the current bar
            **params: Strategy-specific parameters

        Returns:
            Recommendation dict (matches Brief agent output) or None:
            {
                "symbol": str,
                "direction": "long" | "short" | "close",
                "conviction": 0-100,
                "entry_price": float,
                "stop_loss": float | None,
                "take_profit": float | None,
                "size_pct": float,
            }
        """
        ...

    @property
    def warmup_bars(self) -> int:
        """Minimum bars needed before strategy can produce signals."""
        return 61  # default: enough for regime detection
