"""Unit tests for wolfpack.heuristics.HeuristicState.

No DB. load/save use a stub ``FakeDB`` that mimics the Supabase client
builder chain (``table().select()...execute()`` / ``table().upsert()...``).
Run with: ``python3 -m pytest intel/tests/test_heuristics.py -v``
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure intel/ is importable when running pytest from repo root
REPO = Path(__file__).resolve().parents[2]
INTEL = REPO / "intel"
if str(INTEL) not in sys.path:
    sys.path.insert(0, str(INTEL))

import pytest  # noqa: E402

from wolfpack.heuristics import HeuristicState, BASELINE  # noqa: E402


# ---------------------------------------------------------------------------
# Fake Supabase client
# ---------------------------------------------------------------------------


class _Result:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, db, table_name):
        self._db = db
        self._table = table_name
        self._op = None
        self._payload = None
        self._filters: list[tuple[str, str]] = []
        self._limit: int | None = None

    def select(self, _cols="*"):
        self._op = "select"
        return self

    def upsert(self, row, on_conflict=None):
        self._op = "upsert"
        self._payload = row
        self._on_conflict = on_conflict
        return self

    def insert(self, row):
        self._op = "insert"
        self._payload = row
        return self

    def eq(self, col, val):
        self._filters.append((col, val))
        return self

    def limit(self, n):
        self._limit = n
        return self

    def execute(self):
        store = self._db._data.setdefault(self._table, [])
        if self._op == "select":
            rows = list(store)
            for col, val in self._filters:
                rows = [r for r in rows if r.get(col) == val]
            if self._limit:
                rows = rows[: self._limit]
            return _Result(rows)
        if self._op == "upsert":
            key = self._on_conflict or "wallet_id"
            # Remove any existing row on the conflict key, then append
            new_key = self._payload.get(key)
            self._db._data[self._table] = [
                r for r in store if r.get(key) != new_key
            ]
            self._db._data[self._table].append(dict(self._payload))
            return _Result([dict(self._payload)])
        if self._op == "insert":
            store.append(dict(self._payload))
            return _Result([dict(self._payload)])
        return _Result([])


class FakeDB:
    def __init__(self):
        self._data: dict[str, list[dict]] = {}

    def table(self, name):
        return _Query(self, name)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def _state(**kwargs) -> HeuristicState:
    return HeuristicState(wallet_id="test-wallet", **kwargs)


# --- decay -----------------------------------------------------------------


def test_decay_pulls_toward_baseline():
    s = _state(hunger=1.0, satisfaction=0.0, fear=1.0, curiosity=0.0)
    s.decay(cycles=20, half_life_cycles=20)
    # Half the distance to baseline should be gone
    assert s.hunger == pytest.approx(0.75, abs=0.01)
    assert s.satisfaction == pytest.approx(0.25, abs=0.01)
    assert s.fear == pytest.approx(0.75, abs=0.01)
    assert s.curiosity == pytest.approx(0.25, abs=0.01)


def test_decay_clamps():
    s = _state(hunger=1.0)
    s.decay(cycles=1000, half_life_cycles=20)  # should converge to 0.5
    assert 0 <= s.hunger <= 1
    assert s.hunger == pytest.approx(BASELINE, abs=0.01)


def test_decay_zero_cycles_noop():
    s = _state(hunger=0.9, fear=0.1)
    s.decay(cycles=0)
    assert s.hunger == 0.9
    assert s.fear == 0.1


# --- on_target_progress ----------------------------------------------------


def test_target_progress_met():
    s = _state(hunger=0.8, satisfaction=0.2)
    s.on_target_progress(daily_pnl=300, target=300)
    assert s.satisfaction == 1.0
    assert s.hunger == 0.1


def test_target_progress_exceeded():
    s = _state()
    s.on_target_progress(daily_pnl=600, target=300)
    assert s.satisfaction == 1.0
    assert s.hunger == 0.1


def test_target_progress_negative():
    s = _state(hunger=0.5, satisfaction=0.5)
    s.on_target_progress(daily_pnl=-100, target=300)
    assert s.hunger == pytest.approx(0.65, abs=1e-6)
    assert s.satisfaction == 0.1


def test_target_progress_linear_midway():
    s = _state()
    s.on_target_progress(daily_pnl=150, target=300)  # 50% progress
    # hunger: 0.8 - 0.7*0.5 = 0.45 | satisfaction: 0.2 + 0.8*0.5 = 0.6
    assert s.hunger == pytest.approx(0.45, abs=1e-6)
    assert s.satisfaction == pytest.approx(0.6, abs=1e-6)


def test_target_progress_zero_target_noop():
    s = _state(hunger=0.3, satisfaction=0.7)
    s.on_target_progress(daily_pnl=500, target=0)
    assert s.hunger == 0.3
    assert s.satisfaction == 0.7


# --- on_trade_close --------------------------------------------------------


def test_trade_close_win_resets_losses():
    s = _state(loss_streak=2, win_streak=0, satisfaction=0.5, fear=0.5)
    s.on_trade_close(pnl=50, hold_hours=1)
    assert s.win_streak == 1
    assert s.loss_streak == 0
    assert s.satisfaction == pytest.approx(0.58, abs=1e-6)
    assert s.fear == pytest.approx(0.45, abs=1e-6)


def test_trade_close_loss_increments_streak_and_fear():
    s = _state(loss_streak=1, satisfaction=0.5, fear=0.5)
    s.on_trade_close(pnl=-50, hold_hours=1)
    assert s.loss_streak == 2
    assert s.win_streak == 0
    assert s.satisfaction == pytest.approx(0.45, abs=1e-6)
    assert s.fear == pytest.approx(0.6, abs=1e-6)


def test_trade_close_three_loss_streak_extra_fear():
    s = _state(loss_streak=2, fear=0.5)
    s.on_trade_close(pnl=-50, hold_hours=1)
    # loss_streak goes to 3 → extra +0.15 on top of the normal +0.1
    assert s.loss_streak == 3
    assert s.fear == pytest.approx(0.75, abs=1e-6)


def test_trade_close_clamps_fear_and_satisfaction():
    s = _state(fear=0.95, satisfaction=0.02)
    s.on_trade_close(pnl=-50, hold_hours=1)
    assert 0 <= s.fear <= 1
    assert s.fear == 1.0  # 0.95 + 0.1 clamped
    assert s.satisfaction == 0.0  # 0.02 - 0.05 clamped


# --- on_unfamiliar_setup ---------------------------------------------------


def test_on_unfamiliar_setup_increments_curiosity():
    s = _state(curiosity=0.5)
    s.on_unfamiliar_setup(tier="none")
    assert s.curiosity == pytest.approx(0.52, abs=1e-6)


def test_on_unfamiliar_setup_ignores_known_tier():
    s = _state(curiosity=0.5)
    s.on_unfamiliar_setup(tier="A")
    assert s.curiosity == 0.5


# --- conviction_modifier ---------------------------------------------------


def test_conviction_modifier_baseline():
    s = _state()
    # All drives at 0.5 baseline => 0 deviation => 0 modifier
    assert s.conviction_modifier() == 0


def test_conviction_modifier_hungry_reduces():
    s = _state(hunger=1.0, fear=0.0, satisfaction=0.0)
    # -15*(1-0.5) + 10*(0-0.5) + 5*(0-0.5) = -7.5 - 5 - 2.5 = -15
    assert s.conviction_modifier() == -15


def test_conviction_modifier_fearful_raises():
    s = _state(hunger=0.0, fear=1.0, satisfaction=0.0)
    # -15*(0-0.5) + 10*(1-0.5) + 5*(0-0.5) = 7.5 + 5 - 2.5 = 10
    assert s.conviction_modifier() == 10


def test_conviction_modifier_bounds():
    # Bounds clamp to [-15, +20]
    s = _state(hunger=1.0, fear=0.0, satisfaction=0.0)
    assert s.conviction_modifier() >= -15
    s2 = _state(hunger=0.0, fear=1.0, satisfaction=1.0)
    # 7.5 + 5 + 2.5 = 15, well within the +20 upper bound
    assert s2.conviction_modifier() <= 20


# --- size_modifier ---------------------------------------------------------


def test_size_modifier_baseline():
    s = _state()
    # 1.0 + 0.25*0.5 - 0.4*0.5 + 0.15*0.5 = 1.0 + 0.125 - 0.2 + 0.075 = 1.0
    assert s.size_modifier() == pytest.approx(1.0, abs=1e-6)


def test_size_modifier_bounds():
    s = _state(hunger=1.0, fear=0.0, curiosity=1.0)
    assert s.size_modifier() <= 1.35
    s2 = _state(hunger=0.0, fear=1.0, curiosity=0.0)
    assert s2.size_modifier() >= 0.3


# --- exploration_budget ----------------------------------------------------


def test_exploration_budget():
    s = _state(curiosity=0.8, fear=0.25)
    assert s.exploration_budget() == pytest.approx(0.8 * 0.75, abs=1e-6)


def test_exploration_budget_zeroed_by_fear():
    s = _state(curiosity=1.0, fear=1.0)
    assert s.exploration_budget() == 0.0


# --- load / save roundtrip --------------------------------------------------


def test_load_creates_default_row_when_missing():
    db = FakeDB()
    s = HeuristicState.load("w1", db)
    assert s.wallet_id == "w1"
    assert s.hunger == 0.5 and s.fear == 0.5
    assert len(db._data["wp_wallet_state"]) == 1


def test_save_upserts_and_appends_history():
    db = FakeDB()
    s = HeuristicState.load("w2", db)
    s.on_trade_close(pnl=-50, hold_hours=2)
    s.save(db, event="on_trade_close", daily_pnl=-50, equity=24950)

    assert len(db._data["wp_wallet_state"]) == 1
    assert db._data["wp_wallet_state"][0]["loss_streak"] == 1

    hist = db._data["wp_wallet_state_history"]
    assert len(hist) == 1
    assert hist[0]["event"] == "on_trade_close"
    assert hist[0]["daily_pnl"] == -50
    assert hist[0]["equity"] == 24950


def test_load_roundtrip_returns_persisted_values():
    db = FakeDB()
    s = HeuristicState.load("w3", db)
    s.hunger = 0.9
    s.fear = 0.2
    s.loss_streak = 4
    s.save(db, event="test")

    s2 = HeuristicState.load("w3", db)
    assert s2.hunger == pytest.approx(0.9, abs=1e-6)
    assert s2.fear == pytest.approx(0.2, abs=1e-6)
    assert s2.loss_streak == 4
