"""Performance tracker -- rolling scorecard per symbol+direction.

Reads wp_trade_history, computes rolling stats, provides dynamic
conviction thresholds and sizing multipliers based on recent performance.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class SymbolScore:
    symbol: str
    direction: str
    trades: int
    wins: int
    win_rate: float
    net_pnl: float
    avg_win: float
    avg_loss: float
    rr_ratio: float  # avg_win / abs(avg_loss)
    edge: float  # (WR * avg_win) - ((1-WR) * abs(avg_loss))
    grade: str  # STRONG, MARGINAL, UNDERPERFORMING, TOXIC


class PerformanceTracker:
    """Tracks rolling performance and provides adaptive thresholds."""

    def __init__(self, rolling_window: int = 50):
        self.rolling_window = rolling_window
        self._scorecard: dict[str, SymbolScore] = {}
        self._last_refresh: datetime | None = None
        self._refresh_interval_seconds = 300  # refresh every 5 min max

    def refresh(self) -> dict[str, SymbolScore]:
        """Refresh scorecard from DB. Rate-limited to avoid excessive queries."""
        now = datetime.now(timezone.utc)
        if self._last_refresh and (now - self._last_refresh).total_seconds() < self._refresh_interval_seconds:
            return self._scorecard

        try:
            from wolfpack.db import get_db
            db = get_db()

            # Get recent closed trades
            result = db.table("wp_trade_history").select(
                "symbol, direction, pnl_usd"
            ).order("closed_at", desc=True).limit(self.rolling_window * 10).execute()

            if not result.data:
                return self._scorecard

            # Group by symbol+direction
            groups: dict[str, list[float]] = {}
            for row in result.data:
                key = f"{row['symbol']}_{row['direction']}"
                if key not in groups:
                    groups[key] = []
                if len(groups[key]) < self.rolling_window:
                    groups[key].append(float(row['pnl_usd']))

            # Compute scores
            self._scorecard = {}
            for key, pnls in groups.items():
                symbol, direction = key.rsplit("_", 1)
                wins = [p for p in pnls if p > 0]
                losses = [p for p in pnls if p < 0]

                trades = len(pnls)
                win_count = len(wins)
                wr = win_count / trades if trades > 0 else 0
                avg_win = sum(wins) / len(wins) if wins else 0
                avg_loss = sum(losses) / len(losses) if losses else 0
                rr = avg_win / abs(avg_loss) if avg_loss != 0 else 0
                net = sum(pnls)
                edge = (wr * avg_win) - ((1 - wr) * abs(avg_loss))

                # Grade
                if net > 0 and rr >= 2.5:
                    grade = "STRONG"
                elif net > 0:
                    grade = "MARGINAL"
                elif net < 0 and rr >= 1.0:
                    grade = "UNDERPERFORMING"
                else:
                    grade = "TOXIC"

                score = SymbolScore(
                    symbol=symbol, direction=direction,
                    trades=trades, wins=win_count, win_rate=wr,
                    net_pnl=net, avg_win=avg_win, avg_loss=avg_loss,
                    rr_ratio=rr, edge=edge, grade=grade,
                )
                self._scorecard[key] = score

            self._last_refresh = now
            logger.info(f"[perf-tracker] Refreshed scorecard: {len(self._scorecard)} combos")

        except Exception as e:
            logger.warning(f"[perf-tracker] Failed to refresh: {e}")

        return self._scorecard

    def get_threshold(self, symbol: str, direction: str, base_threshold: int = 55) -> int:
        """Get dynamic conviction threshold for a symbol+direction.

        STRONG: lower to 45 (take more)
        MARGINAL: keep at base (55)
        UNDERPERFORMING: raise to 70 (be selective)
        TOXIC: raise to 85 (almost never trade)
        """
        self.refresh()
        key = f"{symbol}_{direction}"
        score = self._scorecard.get(key)

        if score is None or score.trades < 10:
            return base_threshold  # not enough data

        thresholds = {
            "STRONG": max(base_threshold - 10, 35),
            "MARGINAL": base_threshold,
            "UNDERPERFORMING": min(base_threshold + 15, 85),
            "TOXIC": 85,
        }
        return thresholds.get(score.grade, base_threshold)

    def get_size_multiplier(self, symbol: str, direction: str) -> float:
        """Get sizing multiplier based on edge strength.

        STRONG: 1.0 (full size)
        MARGINAL: 0.7
        UNDERPERFORMING: 0.4
        TOXIC: 0.15
        """
        self.refresh()
        key = f"{symbol}_{direction}"
        score = self._scorecard.get(key)

        if score is None or score.trades < 10:
            return 0.7  # conservative default

        multipliers = {
            "STRONG": 1.0,
            "MARGINAL": 0.7,
            "UNDERPERFORMING": 0.4,
            "TOXIC": 0.15,
        }
        return multipliers.get(score.grade, 0.7)

    def get_performance_summary(self) -> str:
        """Get human-readable summary for Brief agent prompt injection."""
        self.refresh()
        if not self._scorecard:
            return "No performance data available yet."

        lines = ["Recent trading performance:"]
        for key, score in sorted(self._scorecard.items(), key=lambda x: x[1].net_pnl, reverse=True):
            lines.append(
                f"- {score.symbol} {score.direction}: {score.grade} | "
                f"{score.trades} trades, {score.win_rate:.0%} WR, "
                f"${score.net_pnl:+,.0f} net, "
                f"R:R {score.rr_ratio:.1f}:1"
            )
        return "\n".join(lines)
