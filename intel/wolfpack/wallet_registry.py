"""Wallet registry — loads the 4 canonical wallets from wp_wallets.

Provides a cached lookup layer over the wp_wallets table so other modules
(paper_trading, auto_trader, live_trading, LP engines) can resolve a wallet
by name or id without hitting the database on every call.

The 4 canonical wallets:
    - paper_perp   (paper mode, perp trading)
    - prod_perp    (production mode, perp trading)
    - paper_lp     (paper mode, Uniswap V3 LP)
    - prod_lp      (production mode, Uniswap V3 LP)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# 5 minutes — aligned with intel service tick cadence
_CACHE_TTL_SECONDS: float = 300.0


# Hardcoded defaults used as a fallback when the database is unreachable.
# IDs are None here; callers that need stable IDs should query the DB when it
# is up. The defaults preserve the name/mode/type so business logic doesn't
# crash on startup just because Supabase is momentarily unavailable.
_DEFAULT_WALLETS: list[dict[str, Any]] = [
    {
        "id": None,
        "name": "paper_perp",
        "wallet_mode": "paper",
        "wallet_type": "perp",
        "starting_equity": 10000.0,
        "current_equity": 10000.0,
        "status": "active",
        "config": {},
    },
    {
        "id": None,
        "name": "prod_perp",
        "wallet_mode": "production",
        "wallet_type": "perp",
        "starting_equity": 1000.0,
        "current_equity": 1000.0,
        "status": "paused",
        "config": {},
    },
    {
        "id": None,
        "name": "paper_lp",
        "wallet_mode": "paper",
        "wallet_type": "lp",
        "starting_equity": 25000.0,
        "current_equity": 25000.0,
        "status": "active",
        "config": {},
    },
    {
        "id": None,
        "name": "prod_lp",
        "wallet_mode": "production",
        "wallet_type": "lp",
        "starting_equity": 0.0,
        "current_equity": 0.0,
        "status": "paused",
        "config": {},
    },
]


@dataclass
class WalletConfig:
    """In-memory representation of a row from wp_wallets."""

    id: str | None
    name: str
    wallet_mode: str  # "paper" | "production"
    wallet_type: str  # "perp" | "lp"
    starting_equity: float
    current_equity: float
    status: str  # "active" | "paused" | "cutover_pending"
    config: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "WalletConfig":
        cfg = row.get("config") or {}
        if not isinstance(cfg, dict):
            cfg = {}
        return cls(
            id=row.get("id"),
            name=row["name"],
            wallet_mode=row["wallet_mode"],
            wallet_type=row["wallet_type"],
            starting_equity=float(row.get("starting_equity") or 0.0),
            current_equity=float(row.get("current_equity") or 0.0),
            status=row.get("status") or "active",
            config=cfg,
        )


class WalletRegistry:
    """Cached lookup over wp_wallets with 5-minute TTL and DB fallback."""

    def __init__(self, ttl_seconds: float = _CACHE_TTL_SECONDS):
        self._ttl_seconds = ttl_seconds
        self._wallets_by_name: dict[str, WalletConfig] = {}
        self._wallets_by_id: dict[str, WalletConfig] = {}
        self._loaded_at: float = 0.0

    # ------------------------------------------------------------------
    # Loading / caching
    # ------------------------------------------------------------------

    def _cache_valid(self) -> bool:
        if not self._wallets_by_name:
            return False
        return (time.time() - self._loaded_at) < self._ttl_seconds

    def _ensure_loaded(self, force: bool = False) -> None:
        if not force and self._cache_valid():
            return
        rows = self._fetch_rows()
        if not rows:
            # DB unreachable or empty — fall back to hardcoded defaults
            rows = _DEFAULT_WALLETS
            logger.warning("WalletRegistry: falling back to hardcoded defaults")

        by_name: dict[str, WalletConfig] = {}
        by_id: dict[str, WalletConfig] = {}
        for row in rows:
            try:
                cfg = WalletConfig.from_row(row)
            except Exception as e:
                logger.warning(f"WalletRegistry: skipping malformed row {row}: {e}")
                continue
            by_name[cfg.name] = cfg
            if cfg.id:
                by_id[str(cfg.id)] = cfg
        self._wallets_by_name = by_name
        self._wallets_by_id = by_id
        self._loaded_at = time.time()

    def _fetch_rows(self) -> list[dict[str, Any]]:
        try:
            from wolfpack.db import get_db
            db = get_db()
            result = db.table("wp_wallets").select("*").execute()
            return list(result.data or [])
        except Exception as e:
            logger.warning(f"WalletRegistry: DB fetch failed: {e}")
            return []

    def refresh(self) -> None:
        """Force reload from the database on next access."""
        self._loaded_at = 0.0
        self._ensure_loaded(force=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_wallet(self, name: str) -> WalletConfig | None:
        """Return a wallet by canonical name (e.g. 'paper_perp')."""
        self._ensure_loaded()
        return self._wallets_by_name.get(name)

    def get_wallet_by_id(self, wallet_id: str) -> WalletConfig | None:
        """Return a wallet by UUID string."""
        self._ensure_loaded()
        return self._wallets_by_id.get(str(wallet_id))

    def get_active_wallets(self, wallet_type: str) -> list[WalletConfig]:
        """Return all active wallets of the given type ('perp' or 'lp')."""
        self._ensure_loaded()
        return [
            w
            for w in self._wallets_by_name.values()
            if w.wallet_type == wallet_type and w.status == "active"
        ]

    def all_wallets(self) -> list[WalletConfig]:
        """Return all wallets regardless of status."""
        self._ensure_loaded()
        return list(self._wallets_by_name.values())


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_registry: WalletRegistry | None = None


def get_registry() -> WalletRegistry:
    """Return the process-wide WalletRegistry singleton."""
    global _registry
    if _registry is None:
        _registry = WalletRegistry()
    return _registry
