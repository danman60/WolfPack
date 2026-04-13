"""Regime classification accuracy feedback loop.

Validates whether the regime detector's classifications actually match
realized price behavior. For each classification, we anchor the current
price and re-check after `lookahead_bars` bars whether the subsequent
move is consistent with the classified regime.

Scoring rules (per classification):
  - `TRENDING_UP`   — score 1.0 if realized move > +0.5% over N bars,
                      0.0 if move < -0.5%, linear in between
  - `TRENDING_DOWN` — mirror
  - `RANGING_LOW_VOL`  — score 1.0 if |max move| < 1 ATR, 0.0 if > 2 ATR
  - `RANGING_HIGH_VOL` — score 1.0 if 1 ATR < |max move| < 2.5 ATR (true wide chop)
  - `VOLATILE`      — score 1.0 if realized ATR > anchor ATR * 1.5
  - `TRANSITION`    — not scored (inherently noisy)

Accuracy is tracked as an EWMA over the last ~20 classifications so
recent regime-detection quality dominates. Exposed via
`get_accuracy(symbol)` for the /regime/state endpoint.

Pure in-memory per process — lost on restart but recoverable in a
few cycles. Future work could persist to a table for longitudinal
analysis.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# How many bars forward we wait before scoring a classification.
# At 1h candles this is 5 hours forward — long enough for a trend to
# either confirm or fail, short enough to react quickly.
LOOKAHEAD_BARS = 5

# EWMA alpha for the rolling accuracy score. Higher = more reactive.
EWMA_ALPHA = 0.15


@dataclass
class PendingValidation:
    symbol: str
    regime: str
    anchor_price: float
    anchor_atr: float
    anchor_time: datetime
    bars_elapsed: int = 0
    max_excursion_up: float = 0.0      # max % move above anchor
    max_excursion_down: float = 0.0    # max % move below anchor
    realized_atr_peak: float = 0.0     # max ATR observed during lookahead


@dataclass
class SymbolAccuracy:
    ewma: float = 0.5                  # starts at neutral
    sample_count: int = 0
    last_regime: str = ""
    last_score: float = 0.0
    last_update: datetime | None = None


# Per-symbol state
_pending: dict[str, list[PendingValidation]] = {}
_accuracy: dict[str, SymbolAccuracy] = {}


def _get_pending(symbol: str) -> list[PendingValidation]:
    return _pending.setdefault(symbol, [])


def _get_accuracy(symbol: str) -> SymbolAccuracy:
    if symbol not in _accuracy:
        _accuracy[symbol] = SymbolAccuracy()
    return _accuracy[symbol]


def record_classification(
    symbol: str,
    regime: str,
    anchor_price: float,
    anchor_atr: float,
) -> None:
    """Register a regime classification for future validation.

    Only tracks specific sub-regimes (TRENDING_UP/DOWN, RANGING_*, VOLATILE).
    TRANSITION is skipped — it's by definition an unstable bridge state.
    """
    if not regime or regime in ("TRANSITION", "unknown"):
        return
    pv = PendingValidation(
        symbol=symbol,
        regime=regime,
        anchor_price=float(anchor_price),
        anchor_atr=float(anchor_atr),
        anchor_time=datetime.now(timezone.utc),
    )
    _get_pending(symbol).append(pv)


def tick(symbol: str, current_price: float, current_atr: float) -> None:
    """Called each cycle with the latest price/ATR for the symbol.

    Advances any pending validations. When a validation reaches
    LOOKAHEAD_BARS, it's scored and absorbed into the EWMA accuracy
    for that symbol, then removed.
    """
    pending = _get_pending(symbol)
    if not pending:
        return

    still_pending: list[PendingValidation] = []
    for pv in pending:
        # Track max excursion in both directions
        up = (current_price - pv.anchor_price) / pv.anchor_price
        if up > pv.max_excursion_up:
            pv.max_excursion_up = up
        if up < pv.max_excursion_down:
            pv.max_excursion_down = up
        if current_atr > pv.realized_atr_peak:
            pv.realized_atr_peak = current_atr

        pv.bars_elapsed += 1

        if pv.bars_elapsed >= LOOKAHEAD_BARS:
            score = _score_classification(pv, current_price)
            _apply_score(pv.symbol, pv.regime, score)
        else:
            still_pending.append(pv)

    _pending[symbol] = still_pending


def _score_classification(pv: PendingValidation, final_price: float) -> float:
    """Score one pending validation in [0, 1]."""
    realized_move_pct = (final_price - pv.anchor_price) / pv.anchor_price * 100.0
    max_excursion = max(abs(pv.max_excursion_up), abs(pv.max_excursion_down)) * 100.0

    if pv.regime == "TRENDING_UP":
        # Reward sustained upward realized move
        if realized_move_pct >= 0.5:
            return 1.0
        if realized_move_pct <= -0.5:
            return 0.0
        return (realized_move_pct + 0.5) / 1.0

    if pv.regime == "TRENDING_DOWN":
        if realized_move_pct <= -0.5:
            return 1.0
        if realized_move_pct >= 0.5:
            return 0.0
        return (0.5 - realized_move_pct) / 1.0

    if pv.regime == "RANGING_LOW_VOL":
        # True low-vol chop should not produce >1 ATR excursions in either
        # direction. Anything up to 1 ATR is fine, penalize beyond 2 ATR.
        if pv.anchor_atr <= 0:
            return 0.5
        excursion_atrs = max_excursion * pv.anchor_price / 100.0 / pv.anchor_atr
        if excursion_atrs <= 1.0:
            return 1.0
        if excursion_atrs >= 2.0:
            return 0.0
        return 1.0 - (excursion_atrs - 1.0)

    if pv.regime == "RANGING_HIGH_VOL":
        # Wide chop should have 1-2.5 ATR excursions — not quiet, not trending
        if pv.anchor_atr <= 0:
            return 0.5
        excursion_atrs = max_excursion * pv.anchor_price / 100.0 / pv.anchor_atr
        if 1.0 <= excursion_atrs <= 2.5:
            return 1.0
        if excursion_atrs < 0.5:
            return 0.3  # actually low vol, mis-classified as high
        if excursion_atrs > 3.5:
            return 0.0  # broke into volatile/trending
        return 0.6

    if pv.regime == "VOLATILE":
        # ATR should remain elevated during the lookahead
        if pv.anchor_atr <= 0:
            return 0.5
        atr_ratio = pv.realized_atr_peak / pv.anchor_atr if pv.anchor_atr > 0 else 1.0
        if atr_ratio >= 1.5:
            return 1.0
        if atr_ratio <= 0.8:
            return 0.0
        return (atr_ratio - 0.8) / 0.7

    return 0.5


def _apply_score(symbol: str, regime: str, score: float) -> None:
    acc = _get_accuracy(symbol)
    acc.ewma = (1 - EWMA_ALPHA) * acc.ewma + EWMA_ALPHA * score
    acc.sample_count += 1
    acc.last_regime = regime
    acc.last_score = score
    acc.last_update = datetime.now(timezone.utc)
    logger.info(
        f"[regime-validator] {symbol}: {regime} scored {score:.2f} "
        f"(accuracy EWMA {acc.ewma:.2f}, n={acc.sample_count})"
    )


def get_accuracy(symbol: str) -> dict:
    """Return current accuracy stats for a symbol for /regime/state."""
    acc = _get_accuracy(symbol)
    return {
        "ewma_accuracy": round(acc.ewma, 3),
        "sample_count": acc.sample_count,
        "pending_count": len(_get_pending(symbol)),
        "last_regime": acc.last_regime,
        "last_score": round(acc.last_score, 3),
        "last_update": acc.last_update.isoformat() if acc.last_update else None,
    }
