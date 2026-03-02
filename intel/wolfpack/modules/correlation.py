"""Correlation & Cross-Asset Intel — Detects cross-asset relationships."""

from pydantic import BaseModel


class CorrelationPair(BaseModel):
    asset_a: str
    asset_b: str
    correlation: float
    rolling_window: int


class CorrelationOutput(BaseModel):
    pairs: list[CorrelationPair]
    btc_dominance_trend: str  # "rising", "falling", "stable"


class CorrelationIntel:
    """Computes rolling correlations between assets."""

    def __init__(self, window: int = 30):
        self.window = window

    def analyze(self, price_series: dict[str, list[float]]) -> CorrelationOutput:
        """
        Args:
            price_series: {"BTC": [close1, close2, ...], "ETH": [...], ...}
        """
        symbols = list(price_series.keys())
        pairs: list[CorrelationPair] = []

        for i, a in enumerate(symbols):
            for b in symbols[i + 1:]:
                corr = self._pearson(
                    price_series[a][-self.window:],
                    price_series[b][-self.window:],
                )
                pairs.append(
                    CorrelationPair(
                        asset_a=a,
                        asset_b=b,
                        correlation=round(corr, 4),
                        rolling_window=self.window,
                    )
                )

        return CorrelationOutput(pairs=pairs, btc_dominance_trend="stable")

    def _pearson(self, x: list[float], y: list[float]) -> float:
        n = min(len(x), len(y))
        if n < 3:
            return 0
        x, y = x[:n], y[:n]
        mx, my = sum(x) / n, sum(y) / n
        num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
        dx = sum((xi - mx) ** 2 for xi in x) ** 0.5
        dy = sum((yi - my) ** 2 for yi in y) ** 0.5
        return num / (dx * dy) if (dx * dy) > 0 else 0
