"""Performance tracker -- rolling scorecard per symbol+direction and per strategy.

Reads wp_trade_history, computes rolling stats, provides dynamic
conviction thresholds, sizing multipliers, and strategy allocations
based on recent performance.
"""

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class StrategyScore:
    strategy: str
    trades: int
    wins: int
    win_rate: float
    net_pnl: float
    edge: float  # expectancy: (WR * avg_win) - ((1-WR) * abs(avg_loss))
    sharpe: float | None  # rolling Sharpe ratio (None if < 10 trades)


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
    """Tracks rolling performance and provides adaptive thresholds.

    Three-tier hierarchical grading with sample-size-aware fallback:
      1. (symbol, direction, regime) — most specific, needs ≥ MIN_TRIPLE trades
      2. (symbol, direction) — current behavior, needs ≥ MIN_PAIR trades
      3. (direction, regime) — regime-wide pattern, needs ≥ MIN_DIR_REGIME trades
      4. base_threshold — no signal
    """

    # Minimum sample sizes per tier
    MIN_TRIPLE = 5
    MIN_PAIR = 10
    MIN_DIR_REGIME = 9

    def __init__(self, rolling_window: int = 50):
        self.rolling_window = rolling_window
        self._scorecard_triple: dict[tuple[str, str, str], SymbolScore] = {}
        self._scorecard_pair: dict[tuple[str, str], SymbolScore] = {}
        self._scorecard_dir_regime: dict[tuple[str, str], SymbolScore] = {}
        # Backward-compat alias: string-keyed (e.g. "BTC_long") view of the pair tier
        self._scorecard: dict[str, SymbolScore] = {}
        self._last_refresh: datetime | None = None
        self._refresh_interval_seconds = 300  # refresh every 5 min max
        self._strategy_cache: dict[str, StrategyScore] = {}
        self._strategy_cache_time: datetime | None = None
        self._strategy_cache_ttl = 300  # 5 min

    @staticmethod
    def _compute_score(symbol: str, direction: str, pnls: list[float]) -> SymbolScore:
        """Grade a list of P&Ls into a SymbolScore."""
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

        if net > 0 and rr >= 2.5:
            grade = "STRONG"
        elif net > 0:
            grade = "MARGINAL"
        elif net < 0 and rr >= 1.0:
            grade = "UNDERPERFORMING"
        else:
            grade = "TOXIC"

        return SymbolScore(
            symbol=symbol, direction=direction,
            trades=trades, wins=win_count, win_rate=wr,
            net_pnl=net, avg_win=avg_win, avg_loss=avg_loss,
            rr_ratio=rr, edge=edge, grade=grade,
        )

    def refresh(self) -> dict[str, SymbolScore]:
        """Refresh scorecard from DB. Rate-limited to avoid excessive queries."""
        now = datetime.now(timezone.utc)
        if self._last_refresh and (now - self._last_refresh).total_seconds() < self._refresh_interval_seconds:
            return self._scorecard

        try:
            from wolfpack.db import get_db
            db = get_db()

            # Get recent closed trades with regime tag
            result = db.table("wp_trade_history").select(
                "symbol, direction, pnl_usd, regime_at_entry"
            ).order("closed_at", desc=True).limit(self.rolling_window * 10).execute()

            if not result.data:
                return self._scorecard

            # Build three grouping dicts
            triples: dict[tuple[str, str, str], list[float]] = {}
            pairs: dict[tuple[str, str], list[float]] = {}
            dir_regimes: dict[tuple[str, str], list[float]] = {}

            for row in result.data:
                symbol = row["symbol"]
                direction = row["direction"]
                pnl = float(row["pnl_usd"])
                regime = row.get("regime_at_entry")

                pk = (symbol, direction)
                if len(pairs.setdefault(pk, [])) < self.rolling_window:
                    pairs[pk].append(pnl)

                if regime and regime not in ("unknown", ""):
                    tk = (symbol, direction, regime)
                    if len(triples.setdefault(tk, [])) < self.rolling_window:
                        triples[tk].append(pnl)
                    drk = (direction, regime)
                    if len(dir_regimes.setdefault(drk, [])) < self.rolling_window:
                        dir_regimes[drk].append(pnl)

            # Compute scores for each tier
            self._scorecard_pair = {
                pk: self._compute_score(pk[0], pk[1], pnls)
                for pk, pnls in pairs.items()
            }
            self._scorecard_triple = {
                tk: self._compute_score(tk[0], tk[1], pnls)
                for tk, pnls in triples.items()
            }
            self._scorecard_dir_regime = {
                drk: self._compute_score("*", drk[0], pnls)
                for drk, pnls in dir_regimes.items()
            }
            # Backward-compat string-keyed alias
            self._scorecard = {
                f"{pk[0]}_{pk[1]}": score for pk, score in self._scorecard_pair.items()
            }

            self._last_refresh = now
            logger.info(
                f"[perf-tracker] Refreshed: {len(self._scorecard_triple)} triples, "
                f"{len(self._scorecard_pair)} pairs, "
                f"{len(self._scorecard_dir_regime)} dir_regimes"
            )

        except Exception as e:
            logger.warning(f"[perf-tracker] Failed to refresh: {e}")

        return self._scorecard

    def _lookup_grade(
        self, symbol: str, direction: str, regime: str | None
    ) -> tuple[SymbolScore | None, str]:
        """Hierarchical lookup. Returns (score, tier) — tier ∈ {triple, pair, dir_regime, none}."""
        if regime and regime not in ("unknown", ""):
            score = self._scorecard_triple.get((symbol, direction, regime))
            if score and score.trades >= self.MIN_TRIPLE:
                return score, "triple"

        score = self._scorecard_pair.get((symbol, direction))
        if score and score.trades >= self.MIN_PAIR:
            return score, "pair"

        if regime and regime not in ("unknown", ""):
            score = self._scorecard_dir_regime.get((direction, regime))
            if score and score.trades >= self.MIN_DIR_REGIME:
                return score, "dir_regime"

        return None, "none"

    def get_threshold(
        self,
        symbol: str,
        direction: str,
        base_threshold: int = 55,
        regime: str | None = None,
    ) -> int:
        """Get dynamic conviction threshold for a symbol+direction (+ regime).

        STRONG: lower by 10 from base (take more)
        MARGINAL: keep at base
        UNDERPERFORMING: raise to base+15 (be selective)
        TOXIC: raise to 999 (block entirely — data says it loses money)
        """
        self.refresh()
        score, _tier = self._lookup_grade(symbol, direction, regime)
        if score is None:
            return base_threshold

        thresholds = {
            "STRONG": max(base_threshold - 10, 35),
            "MARGINAL": base_threshold,
            "UNDERPERFORMING": base_threshold + 15,
            "TOXIC": 999,
        }
        return thresholds.get(score.grade, base_threshold)

    def get_size_multiplier(
        self, symbol: str, direction: str, regime: str | None = None
    ) -> float:
        """Get sizing multiplier based on edge strength.

        STRONG: 1.0 (full size)
        MARGINAL: 0.7
        UNDERPERFORMING: 0.4
        TOXIC: 0.15
        """
        self.refresh()
        score, _tier = self._lookup_grade(symbol, direction, regime)
        if score is None:
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

    # ── Strategy-level performance ──────────────────────────────────

    def _refresh_strategy_scores(self) -> dict[str, StrategyScore]:
        """Refresh per-strategy performance from DB. Rate-limited."""
        now = datetime.now(timezone.utc)
        if (
            self._strategy_cache_time
            and (now - self._strategy_cache_time).total_seconds() < self._strategy_cache_ttl
            and self._strategy_cache
        ):
            return self._strategy_cache

        try:
            from wolfpack.db import get_db
            db = get_db()

            result = db.table("wp_trade_history").select(
                "strategy, pnl_usd"
            ).not_.is_("strategy", "null").order(
                "closed_at", desc=True
            ).limit(self.rolling_window * 20).execute()

            if not result.data:
                return self._strategy_cache

            # Group by strategy
            groups: dict[str, list[float]] = {}
            for row in result.data:
                strat = row["strategy"]
                if strat not in groups:
                    groups[strat] = []
                if len(groups[strat]) < self.rolling_window:
                    groups[strat].append(float(row["pnl_usd"]))

            self._strategy_cache = {}
            for strat, pnls in groups.items():
                wins = [p for p in pnls if p > 0]
                losses = [p for p in pnls if p < 0]
                trades = len(pnls)
                win_count = len(wins)
                wr = win_count / trades if trades > 0 else 0
                avg_win = sum(wins) / len(wins) if wins else 0
                avg_loss = sum(losses) / len(losses) if losses else 0
                net = sum(pnls)
                edge = (wr * avg_win) - ((1 - wr) * abs(avg_loss))

                # Sharpe ratio (annualized, assuming ~6 trades/day)
                sharpe = None
                if trades >= 10:
                    mean_pnl = net / trades
                    variance = sum((p - mean_pnl) ** 2 for p in pnls) / trades
                    std = math.sqrt(variance) if variance > 0 else 0
                    if std > 0:
                        sharpe = round((mean_pnl / std) * math.sqrt(252 * 6), 2)

                self._strategy_cache[strat] = StrategyScore(
                    strategy=strat,
                    trades=trades,
                    wins=win_count,
                    win_rate=wr,
                    net_pnl=net,
                    edge=edge,
                    sharpe=sharpe,
                )

            self._strategy_cache_time = now
            logger.info(f"[perf-tracker] Refreshed strategy scores: {list(self._strategy_cache.keys())}")

        except Exception as e:
            logger.warning(f"[perf-tracker] Failed to refresh strategy scores: {e}")

        return self._strategy_cache

    def get_strategy_performance(self, strategy_name: str) -> dict:
        """Return performance dict for a single strategy.

        Returns: {trades, win_rate, net_pnl, edge, sharpe}
        """
        scores = self._refresh_strategy_scores()
        score = scores.get(strategy_name)
        if score is None:
            return {"trades": 0, "win_rate": 0.0, "net_pnl": 0.0, "edge": 0.0, "sharpe": None}
        return {
            "trades": score.trades,
            "win_rate": score.win_rate,
            "net_pnl": score.net_pnl,
            "edge": score.edge,
            "sharpe": score.sharpe,
        }

    def get_strategy_allocations(
        self,
        default_allocations: dict[str, float] | None = None,
        min_total_trades: int = 30,
        min_strategy_trades: int = 10,
        min_alloc: float = 0.02,
        max_alloc: float = 0.35,
        strategy_budget: float = 0.75,
    ) -> dict[str, float]:
        """Compute dynamic allocation weights based on strategy edge strength.

        Args:
            default_allocations: Static fallback allocations.
            min_total_trades: Minimum total trades across all strategies before
                              dynamic allocation kicks in.
            min_strategy_trades: Minimum trades per strategy to influence allocation.
            min_alloc: Floor per strategy (default 2%).
            max_alloc: Ceiling per strategy (default 35%).
            strategy_budget: Total budget for strategies (remainder is Brief-driven).

        Returns:
            Dict mapping strategy_name -> allocation weight (sums to ~strategy_budget).
        """
        if default_allocations is None:
            default_allocations = {}

        scores = self._refresh_strategy_scores()

        # Check if we have enough total trades
        total_trades = sum(s.trades for s in scores.values())
        if total_trades < min_total_trades:
            logger.info(
                f"[perf-tracker] Only {total_trades} total strategy trades "
                f"(need {min_total_trades}), using static allocations"
            )
            return dict(default_allocations)

        # Separate strategies with enough data vs those that fall back to defaults
        eligible: dict[str, float] = {}  # strategy -> raw edge weight
        fallback_strategies: dict[str, float] = {}  # strategy -> static alloc

        for strat_name in default_allocations:
            score = scores.get(strat_name)
            if score is None or score.trades < min_strategy_trades:
                fallback_strategies[strat_name] = default_allocations[strat_name]
            else:
                eligible[strat_name] = score.edge

        # If ALL eligible strategies have negative edge, use equal allocation
        # to avoid zeroing everything out
        if eligible and all(e <= 0 for e in eligible.values()):
            logger.info("[perf-tracker] All strategies underperforming, using equal allocation")
            equal_alloc = strategy_budget / len(default_allocations) if default_allocations else 0
            return {s: equal_alloc for s in default_allocations}

        # Budget available for dynamically allocated strategies
        fallback_budget = sum(fallback_strategies.values())
        dynamic_budget = strategy_budget - fallback_budget

        if not eligible or dynamic_budget <= 0:
            return dict(default_allocations)

        # Shift edges so the minimum is at least 0.01 (avoid negatives dominating)
        min_edge = min(eligible.values())
        shifted = {}
        for s, e in eligible.items():
            shifted[s] = max(e - min_edge + 0.01, 0.01)

        # Normalize to dynamic_budget
        total_weight = sum(shifted.values())
        allocations: dict[str, float] = {}

        for s, w in shifted.items():
            raw = (w / total_weight) * dynamic_budget
            allocations[s] = round(max(min_alloc, min(max_alloc, raw)), 4)

        # Re-normalize after clamping to hit dynamic_budget
        clamped_sum = sum(allocations.values())
        if clamped_sum > 0 and abs(clamped_sum - dynamic_budget) > 0.001:
            scale = dynamic_budget / clamped_sum
            allocations = {
                s: round(max(min_alloc, min(max_alloc, v * scale)), 4)
                for s, v in allocations.items()
            }

        # Merge with fallback strategies
        result = {**fallback_strategies, **allocations}
        return result
