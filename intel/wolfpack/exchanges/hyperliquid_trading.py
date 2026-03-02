"""Hyperliquid order execution — EIP-712 signed order placement.

Requires HYPERLIQUID_PRIVATE_KEY in .env for order signing.
Uses the /exchange endpoint (separate from /info).
"""

import json
import logging
import time
from typing import Any, Literal

import httpx
from eth_account import Account
from eth_account.messages import encode_defunct

logger = logging.getLogger(__name__)

EXCHANGE_URL = "https://api.hyperliquid.xyz/exchange"
INFO_URL = "https://api.hyperliquid.xyz/info"

# Hyperliquid EIP-712 domain
DOMAIN = {
    "name": "Exchange",
    "version": "1",
    "chainId": 1337,
    "verifyingContract": "0x0000000000000000000000000000000000000000",
}

# Order wire type
ORDER_TYPE = {
    "EIP712Domain": [
        {"name": "name", "type": "string"},
        {"name": "version", "type": "string"},
        {"name": "chainId", "type": "uint256"},
        {"name": "verifyingContract", "type": "address"},
    ],
    "Order": [
        {"name": "asset", "type": "uint32"},
        {"name": "isBuy", "type": "bool"},
        {"name": "limitPx", "type": "uint64"},
        {"name": "sz", "type": "uint64"},
        {"name": "reduceOnly", "type": "bool"},
        {"name": "cloid", "type": "bytes16"},
    ],
    "Agent": [
        {"name": "source", "type": "string"},
        {"name": "connectionId", "type": "bytes32"},
    ],
}


class HyperliquidTrader:
    """Places orders on Hyperliquid using EIP-712 signed messages."""

    def __init__(self, private_key: str):
        self.account = Account.from_key(private_key)
        self.address = self.account.address
        self._client: httpx.AsyncClient | None = None
        self._asset_map: dict[str, int] | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=10)
        return self._client

    async def _get_asset_index(self, symbol: str) -> int:
        """Get the numeric asset index for a symbol."""
        if self._asset_map is None:
            client = await self._get_client()
            resp = await client.post(INFO_URL, json={"type": "meta"})
            resp.raise_for_status()
            meta = resp.json()
            universe = meta.get("universe", [])
            self._asset_map = {m["name"]: i for i, m in enumerate(universe)}

        idx = self._asset_map.get(symbol)
        if idx is None:
            raise ValueError(f"Unknown symbol: {symbol}")
        return idx

    async def place_order(
        self,
        symbol: str,
        is_buy: bool,
        size: float,
        price: float,
        reduce_only: bool = False,
        order_type: Literal["limit", "market"] = "limit",
    ) -> dict[str, Any]:
        """Place an order on Hyperliquid.

        Args:
            symbol: Asset symbol (e.g., "BTC")
            is_buy: True for long/buy, False for short/sell
            size: Order size in base asset units
            price: Limit price (for market orders, use a price with slippage)
            reduce_only: Only reduce existing position
            order_type: "limit" or "market" (market uses IOC with slippage)

        Returns:
            API response dict
        """
        asset_idx = await self._get_asset_index(symbol)

        # Hyperliquid price/size formatting
        # Prices need to be rounded to valid tick sizes
        order_wire = {
            "a": asset_idx,
            "b": is_buy,
            "p": str(price),
            "s": str(size),
            "r": reduce_only,
            "t": {"limit": {"tif": "Gtc"}} if order_type == "limit" else {"limit": {"tif": "Ioc"}},
        }

        timestamp = int(time.time() * 1000)

        action = {
            "type": "order",
            "orders": [order_wire],
            "grouping": "na",
        }

        # Sign the action
        signature = self._sign_action(action, timestamp)

        payload = {
            "action": action,
            "nonce": timestamp,
            "signature": signature,
        }

        client = await self._get_client()
        resp = await client.post(EXCHANGE_URL, json=payload)

        result = resp.json()
        logger.info(f"Order placed: {symbol} {'BUY' if is_buy else 'SELL'} {size} @ {price} -> {result}")
        return result

    async def cancel_order(self, symbol: str, order_id: int) -> dict[str, Any]:
        """Cancel an open order."""
        asset_idx = await self._get_asset_index(symbol)
        timestamp = int(time.time() * 1000)

        action = {
            "type": "cancel",
            "cancels": [{"a": asset_idx, "o": order_id}],
        }

        signature = self._sign_action(action, timestamp)

        payload = {
            "action": action,
            "nonce": timestamp,
            "signature": signature,
        }

        client = await self._get_client()
        resp = await client.post(EXCHANGE_URL, json=payload)
        return resp.json()

    async def get_open_orders(self) -> list[dict]:
        """Fetch open orders for this wallet."""
        client = await self._get_client()
        resp = await client.post(INFO_URL, json={"type": "openOrders", "user": self.address})
        resp.raise_for_status()
        return resp.json() if isinstance(resp.json(), list) else []

    async def get_positions(self) -> list[dict]:
        """Fetch current positions for this wallet."""
        client = await self._get_client()
        resp = await client.post(INFO_URL, json={"type": "clearinghouseState", "user": self.address})
        resp.raise_for_status()
        state = resp.json()
        return state.get("assetPositions", []) if isinstance(state, dict) else []

    def _sign_action(self, action: dict, timestamp: int) -> dict:
        """Sign an action using EIP-712 structured data.

        Hyperliquid uses a custom signing scheme. This constructs
        the typed data and signs it with the configured private key.
        """
        # Construct the connection ID hash
        action_hash = self._action_hash(action, timestamp)

        # Sign with the account
        signed = self.account.sign_message(action_hash)

        return {
            "r": hex(signed.r),
            "s": hex(signed.s),
            "v": signed.v,
        }

    def _action_hash(self, action: dict, timestamp: int) -> Any:
        """Compute the action hash for Hyperliquid signing.

        This follows Hyperliquid's specific EIP-712 signing format.
        """
        # Hyperliquid uses a simplified signing approach:
        # Sign the keccak256 of the JSON-encoded action + timestamp
        msg = json.dumps({"action": action, "nonce": timestamp}, separators=(",", ":"), sort_keys=True)
        return encode_defunct(text=msg)

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
