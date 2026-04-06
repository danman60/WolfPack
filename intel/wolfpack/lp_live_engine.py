"""Live LP Engine — executes real Uniswap V3 positions on Arbitrum.

Same interface as PaperLPEngine so LPAutoTrader works unchanged.
Uses web3.py for on-chain transaction signing.
"""

import logging
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from web3 import Web3
from eth_account import Account

from wolfpack.config import settings
from wolfpack.lp_paper_engine import PaperLPPosition, PaperLPPortfolio

logger = logging.getLogger(__name__)

# Uniswap V3 NonfungiblePositionManager (same address on all chains)
NPM_ADDRESS = "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"

# Minimal ABI for mint, decreaseLiquidity, collect, positions
NPM_ABI = [
    # mint
    {
        "inputs": [{"components": [
            {"name": "token0", "type": "address"},
            {"name": "token1", "type": "address"},
            {"name": "fee", "type": "uint24"},
            {"name": "tickLower", "type": "int24"},
            {"name": "tickUpper", "type": "int24"},
            {"name": "amount0Desired", "type": "uint256"},
            {"name": "amount1Desired", "type": "uint256"},
            {"name": "amount0Min", "type": "uint256"},
            {"name": "amount1Min", "type": "uint256"},
            {"name": "recipient", "type": "address"},
            {"name": "deadline", "type": "uint256"},
        ], "name": "params", "type": "tuple"}],
        "name": "mint",
        "outputs": [
            {"name": "tokenId", "type": "uint256"},
            {"name": "liquidity", "type": "uint128"},
            {"name": "amount0", "type": "uint256"},
            {"name": "amount1", "type": "uint256"},
        ],
        "stateMutability": "payable",
        "type": "function"
    },
    # decreaseLiquidity
    {
        "inputs": [{"components": [
            {"name": "tokenId", "type": "uint256"},
            {"name": "liquidity", "type": "uint128"},
            {"name": "amount0Min", "type": "uint256"},
            {"name": "amount1Min", "type": "uint256"},
            {"name": "deadline", "type": "uint256"},
        ], "name": "params", "type": "tuple"}],
        "name": "decreaseLiquidity",
        "outputs": [
            {"name": "amount0", "type": "uint256"},
            {"name": "amount1", "type": "uint256"},
        ],
        "stateMutability": "payable",
        "type": "function"
    },
    # collect
    {
        "inputs": [{"components": [
            {"name": "tokenId", "type": "uint256"},
            {"name": "recipient", "type": "address"},
            {"name": "amount0Max", "type": "uint128"},
            {"name": "amount1Max", "type": "uint128"},
        ], "name": "params", "type": "tuple"}],
        "name": "collect",
        "outputs": [
            {"name": "amount0", "type": "uint256"},
            {"name": "amount1", "type": "uint256"},
        ],
        "stateMutability": "payable",
        "type": "function"
    },
    # positions (read)
    {
        "inputs": [{"name": "tokenId", "type": "uint256"}],
        "name": "positions",
        "outputs": [
            {"name": "nonce", "type": "uint96"},
            {"name": "operator", "type": "address"},
            {"name": "token0", "type": "address"},
            {"name": "token1", "type": "address"},
            {"name": "fee", "type": "uint24"},
            {"name": "tickLower", "type": "int24"},
            {"name": "tickUpper", "type": "int24"},
            {"name": "liquidity", "type": "uint128"},
            {"name": "feeGrowthInside0LastX128", "type": "uint256"},
            {"name": "feeGrowthInside1LastX128", "type": "uint256"},
            {"name": "tokensOwed0", "type": "uint128"},
            {"name": "tokensOwed1", "type": "uint128"},
        ],
        "stateMutability": "view",
        "type": "function"
    },
]

# ERC20 minimal ABI
ERC20_ABI = [
    {
        "inputs": [
            {"name": "spender", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "stateMutability": "view",
        "type": "function"
    },
]

# Uniswap V3 Pool minimal ABI (slot0 for current tick/price)
POOL_ABI = [
    {
        "inputs": [],
        "name": "slot0",
        "outputs": [
            {"name": "sqrtPriceX96", "type": "uint160"},
            {"name": "tick", "type": "int24"},
            {"name": "observationIndex", "type": "uint16"},
            {"name": "observationCardinality", "type": "uint16"},
            {"name": "observationCardinalityNext", "type": "uint16"},
            {"name": "feeProtocol", "type": "uint8"},
            {"name": "unlocked", "type": "bool"},
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "token0",
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "token1",
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    },
]

# Chain-specific RPC defaults
_CHAIN_RPC = {
    "arbitrum": "https://arb1.arbitrum.io/rpc",
    "ethereum": "https://ethereum-rpc.publicnode.com",
}

# Transaction deadline padding (seconds)
TX_DEADLINE_SECONDS = 300
# Max slippage for LP operations (2%)
MAX_SLIPPAGE_BPS = 200


@dataclass
class LiveLPPosition(PaperLPPosition):
    """Extends PaperLPPosition with on-chain data."""
    token_id: int = 0           # NFT token ID from mint
    token0_address: str = ""
    token1_address: str = ""
    on_chain_liquidity: int = 0  # raw liquidity from contract


class LiveLPEngine:
    """Manages real Uniswap V3 LP positions on-chain.

    Implements the same interface as PaperLPEngine so LPAutoTrader
    works without changes.
    """

    def __init__(self, persist: bool = True):
        self.persist = persist
        rpc_url = settings.lp_rpc_url or _CHAIN_RPC.get(settings.lp_chain, _CHAIN_RPC["arbitrum"])
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))

        if not settings.lp_wallet_private_key:
            raise ValueError("lp_wallet_private_key is required for live LP trading")

        self.account = Account.from_key(settings.lp_wallet_private_key)
        self.npm = self.w3.eth.contract(
            address=Web3.to_checksum_address(NPM_ADDRESS),
            abi=NPM_ABI,
        )

        # Portfolio mirrors PaperLPPortfolio interface
        self.portfolio = PaperLPPortfolio(
            starting_equity=0,  # will be computed from on-chain balances
            equity=0,
            free_collateral=0,
        )

        # Map pool_address -> LiveLPPosition for active positions
        self._token_id_map: dict[str, int] = {}  # pool_address -> token_id

        logger.info(f"LiveLPEngine initialized on {settings.lp_chain} — wallet {self.account.address[:10]}...")

    def open_position(
        self,
        pool_address: str,
        token0_symbol: str,
        token1_symbol: str,
        fee_tier: int,
        tick_lower: int,
        tick_upper: int,
        size_pct: float,
        current_tick: int,
        current_price_ratio: float,
    ) -> Optional[LiveLPPosition]:
        """Open a real LP position: approve tokens + mint NFT."""
        # Check for existing position in this pool
        existing = [p for p in self.portfolio.positions if p.pool_address == pool_address and p.status == "active"]
        if existing:
            logger.warning(f"Already have LP position in pool {pool_address}")
            return None

        if not (tick_lower <= current_tick <= tick_upper):
            logger.warning(f"Current tick {current_tick} outside range [{tick_lower}, {tick_upper}]")
            return None

        try:
            pool_contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(pool_address),
                abi=POOL_ABI,
            )
            token0_addr = pool_contract.functions.token0().call()
            token1_addr = pool_contract.functions.token1().call()

            token0_contract = self.w3.eth.contract(address=Web3.to_checksum_address(token0_addr), abi=ERC20_ABI)
            token1_contract = self.w3.eth.contract(address=Web3.to_checksum_address(token1_addr), abi=ERC20_ABI)

            token0_decimals = token0_contract.functions.decimals().call()
            token1_decimals = token1_contract.functions.decimals().call()

            # Determine amounts from wallet balances and size_pct
            bal0 = token0_contract.functions.balanceOf(self.account.address).call()
            bal1 = token1_contract.functions.balanceOf(self.account.address).call()

            size_frac = min(size_pct, 30) / 100.0
            amount0_desired = int(bal0 * size_frac)
            amount1_desired = int(bal1 * size_frac)

            if amount0_desired == 0 and amount1_desired == 0:
                logger.warning("No token balances to provide liquidity")
                return None

            # Approve NPM to spend tokens
            npm_addr = Web3.to_checksum_address(NPM_ADDRESS)
            self._approve_if_needed(token0_contract, npm_addr, amount0_desired)
            self._approve_if_needed(token1_contract, npm_addr, amount1_desired)

            # Slippage: allow MAX_SLIPPAGE_BPS deviation
            amount0_min = amount0_desired * (10000 - MAX_SLIPPAGE_BPS) // 10000
            amount1_min = amount1_desired * (10000 - MAX_SLIPPAGE_BPS) // 10000

            deadline = int(time.time()) + TX_DEADLINE_SECONDS

            mint_params = (
                Web3.to_checksum_address(token0_addr),
                Web3.to_checksum_address(token1_addr),
                fee_tier,
                tick_lower,
                tick_upper,
                amount0_desired,
                amount1_desired,
                amount0_min,
                amount1_min,
                self.account.address,
                deadline,
            )

            tx = self.npm.functions.mint(mint_params).build_transaction({
                "from": self.account.address,
                "nonce": self.w3.eth.get_transaction_count(self.account.address),
                "gas": 0,  # will be estimated
                "maxFeePerGas": self.w3.eth.gas_price * 2,
                "maxPriorityFeePerGas": self.w3.eth.max_priority_fee,
            })

            # Estimate gas
            tx["gas"] = int(self.w3.eth.estimate_gas(tx) * 1.2)

            signed = self.account.sign_transaction(tx)
            tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            if receipt["status"] != 1:
                logger.error(f"Mint transaction reverted: {tx_hash.hex()}")
                return None

            # Parse token_id from Transfer event (first log is the NFT mint)
            # The mint function returns (tokenId, liquidity, amount0, amount1)
            # We can decode from the transaction receipt logs
            token_id = self._parse_token_id_from_receipt(receipt)
            if token_id is None:
                logger.error("Could not parse token_id from mint receipt")
                return None

            # Estimate USD value from amounts used
            # For now, use a rough estimate — the update_position cycle will refine this
            liquidity_usd_estimate = (
                amount0_desired / (10 ** token0_decimals) * current_price_ratio
                + amount1_desired / (10 ** token1_decimals)
            )

            timestamp = datetime.now(timezone.utc)
            position = LiveLPPosition(
                position_id=f"live-lp-{pool_address[:8]}-{token_id}",
                pool_address=pool_address,
                token0_symbol=token0_symbol,
                token1_symbol=token1_symbol,
                fee_tier=fee_tier,
                tick_lower=tick_lower,
                tick_upper=tick_upper,
                liquidity_usd=liquidity_usd_estimate,
                entry_price_ratio=current_price_ratio,
                current_price_ratio=current_price_ratio,
                current_tick=current_tick,
                opened_at=timestamp,
                token_id=token_id,
                token0_address=token0_addr,
                token1_address=token1_addr,
            )

            self.portfolio.positions.append(position)
            self._token_id_map[pool_address] = token_id
            self._recalculate()

            logger.info(
                f"Opened LIVE LP {token0_symbol}/{token1_symbol} {fee_tier/10000:.2f}% "
                f"@ ticks [{tick_lower}, {tick_upper}], tokenId={token_id}, tx={tx_hash.hex()[:16]}..."
            )
            return position

        except Exception as e:
            logger.error(f"Failed to open live LP position: {e}")
            return None

    def close_position(self, pool_address: str) -> float:
        """Close LP position: decreaseLiquidity + collect. Returns net P&L (fees - IL)."""
        pos = None
        idx = -1
        for i, p in enumerate(self.portfolio.positions):
            if p.pool_address == pool_address and p.status in ("active", "out_of_range"):
                pos = p
                idx = i
                break

        if pos is None:
            return 0.0

        token_id = getattr(pos, "token_id", 0) or self._token_id_map.get(pool_address, 0)
        if token_id == 0:
            logger.error(f"No token_id for position in pool {pool_address}")
            return 0.0

        try:
            # Read on-chain position to get current liquidity
            on_chain = self.npm.functions.positions(token_id).call()
            liquidity = on_chain[7]  # liquidity field

            if liquidity == 0:
                logger.warning(f"Position {token_id} already has 0 liquidity")
            else:
                # decreaseLiquidity — remove all liquidity
                deadline = int(time.time()) + TX_DEADLINE_SECONDS
                decrease_params = (
                    token_id,
                    liquidity,
                    0,  # amount0Min — accept any (slippage during close is acceptable)
                    0,  # amount1Min
                    deadline,
                )

                tx = self.npm.functions.decreaseLiquidity(decrease_params).build_transaction({
                    "from": self.account.address,
                    "nonce": self.w3.eth.get_transaction_count(self.account.address),
                    "gas": 0,
                    "maxFeePerGas": self.w3.eth.gas_price * 2,
                    "maxPriorityFeePerGas": self.w3.eth.max_priority_fee,
                })
                tx["gas"] = int(self.w3.eth.estimate_gas(tx) * 1.2)

                signed = self.account.sign_transaction(tx)
                tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
                receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

                if receipt["status"] != 1:
                    logger.error(f"decreaseLiquidity reverted: {tx_hash.hex()}")
                    return 0.0

            # collect — sweep all tokens + fees
            max_uint128 = 2**128 - 1
            collect_params = (
                token_id,
                self.account.address,
                max_uint128,
                max_uint128,
            )

            tx = self.npm.functions.collect(collect_params).build_transaction({
                "from": self.account.address,
                "nonce": self.w3.eth.get_transaction_count(self.account.address),
                "gas": 0,
                "maxFeePerGas": self.w3.eth.gas_price * 2,
                "maxPriorityFeePerGas": self.w3.eth.max_priority_fee,
            })
            tx["gas"] = int(self.w3.eth.estimate_gas(tx) * 1.2)

            signed = self.account.sign_transaction(tx)
            tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            if receipt["status"] != 1:
                logger.error(f"collect reverted: {tx_hash.hex()}")
                return 0.0

            # Compute net P&L from tracked fees/IL
            net_pnl = pos.fees_earned_usd - pos.il_usd
            self.portfolio.realized_pnl += net_pnl
            self.portfolio.total_fees_earned += pos.fees_earned_usd
            self.portfolio.total_il += pos.il_usd
            self.portfolio.closed_positions += 1

            pos.status = "closed"
            self.portfolio.positions.pop(idx)
            self._token_id_map.pop(pool_address, None)

            if self.persist:
                self._store_closed_position(pos, net_pnl)

            self._recalculate()

            logger.info(
                f"Closed LIVE LP {pos.token0_symbol}/{pos.token1_symbol}: "
                f"fees ${pos.fees_earned_usd:.2f}, IL ${pos.il_usd:.2f}, net ${net_pnl:.2f}, tx={tx_hash.hex()[:16]}..."
            )
            return net_pnl

        except Exception as e:
            logger.error(f"Failed to close live LP position: {e}")
            return 0.0

    def update_position(
        self,
        pool_address: str,
        current_tick: int,
        current_price_ratio: float,
        pool_volume_24h: float,
        pool_tvl: float,
    ) -> None:
        """Update position state from on-chain data + market data.

        Reads the NPM positions() for fees owed, updates tick/price/IL.
        Fee accrual for live positions comes from on-chain tokensOwed rather
        than simulation, but we still track the paper-style metrics for
        portfolio consistency.
        """
        for pos in self.portfolio.positions:
            if pos.pool_address != pool_address or pos.status != "active":
                continue

            pos.current_tick = current_tick
            pos.current_price_ratio = current_price_ratio

            # Check range
            in_range = pos.tick_lower <= current_tick <= pos.tick_upper
            if in_range:
                if pos.status == "out_of_range":
                    pos.status = "active"
                pos.out_of_range_ticks = 0
            else:
                pos.out_of_range_ticks += 1
                if pos.out_of_range_ticks >= 3:
                    pos.status = "out_of_range"

            # Read on-chain fees owed (best-effort)
            token_id = getattr(pos, "token_id", 0) or self._token_id_map.get(pool_address, 0)
            if token_id > 0:
                try:
                    on_chain = self.npm.functions.positions(token_id).call()
                    tokens_owed0 = on_chain[10]
                    tokens_owed1 = on_chain[11]

                    # Rough USD estimate of uncollected fees
                    t0_addr = getattr(pos, "token0_address", "")
                    t1_addr = getattr(pos, "token1_address", "")
                    t0_dec = self._get_decimals(t0_addr) if t0_addr else 18
                    t1_dec = self._get_decimals(t1_addr) if t1_addr else 6

                    # Use price ratio to convert token0 to USD terms
                    fee0_usd = (tokens_owed0 / (10 ** t0_dec)) * (current_price_ratio if current_price_ratio > 0 else 1.0)
                    fee1_usd = tokens_owed1 / (10 ** t1_dec)
                    pos.fees_earned_usd = fee0_usd + fee1_usd
                except Exception as e:
                    logger.debug(f"Could not read on-chain fees for tokenId {token_id}: {e}")
                    # Fall back to simulation-based fee accrual
                    if in_range and pool_tvl > 0:
                        daily_fees = pool_volume_24h * (pos.fee_tier / 1_000_000)
                        position_share = pos.liquidity_usd / pool_tvl
                        fee_per_tick = daily_fees * position_share / 288
                        pos.fees_earned_usd += fee_per_tick
            else:
                # No token_id — use simulation fallback
                if in_range and pool_tvl > 0:
                    daily_fees = pool_volume_24h * (pos.fee_tier / 1_000_000)
                    position_share = pos.liquidity_usd / pool_tvl
                    fee_per_tick = daily_fees * position_share / 288
                    pos.fees_earned_usd += fee_per_tick

            # Compute IL (same formula as paper engine)
            pos.il_pct = self._compute_il(pos.entry_price_ratio, current_price_ratio)
            pos.il_usd = pos.liquidity_usd * abs(pos.il_pct) / 100

        self._recalculate()

    @staticmethod
    def _compute_il(entry_ratio: float, current_ratio: float) -> float:
        """Impermanent loss formula: 2*sqrt(r)/(1+r) - 1 where r = current/entry."""
        if entry_ratio <= 0:
            return 0.0
        r = current_ratio / entry_ratio
        if r <= 0:
            return 0.0
        il = 2 * math.sqrt(r) / (1 + r) - 1
        return round(il * 100, 4)

    def _recalculate(self) -> None:
        """Recalculate portfolio equity from positions."""
        total_value = sum(
            p.liquidity_usd + p.fees_earned_usd - p.il_usd
            for p in self.portfolio.positions
            if p.status != "closed"
        )
        self.portfolio.free_collateral = 0  # live mode: free collateral is wallet balance
        self.portfolio.equity = total_value

    def _approve_if_needed(self, token_contract, spender: str, amount: int) -> None:
        """Approve spender if current allowance is insufficient."""
        try:
            # Check current allowance via raw call (allowance not in our minimal ABI)
            allowance_sig = Web3.keccak(text="allowance(address,address)")[:4]
            owner_padded = self.account.address[2:].lower().zfill(64)
            spender_padded = spender[2:].lower().zfill(64)
            data = "0x" + allowance_sig.hex() + owner_padded + spender_padded

            result = self.w3.eth.call({
                "to": token_contract.address,
                "data": data,
            })
            current_allowance = int(result.hex(), 16)

            if current_allowance >= amount:
                return

            # Approve max uint256
            max_approval = 2**256 - 1
            tx = token_contract.functions.approve(
                Web3.to_checksum_address(spender), max_approval
            ).build_transaction({
                "from": self.account.address,
                "nonce": self.w3.eth.get_transaction_count(self.account.address),
                "gas": 0,
                "maxFeePerGas": self.w3.eth.gas_price * 2,
                "maxPriorityFeePerGas": self.w3.eth.max_priority_fee,
            })
            tx["gas"] = int(self.w3.eth.estimate_gas(tx) * 1.2)

            signed = self.account.sign_transaction(tx)
            tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
            self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
            logger.info(f"Approved {token_contract.address[:10]} for NPM")
        except Exception as e:
            logger.warning(f"Approval check/tx failed: {e}")

    def _parse_token_id_from_receipt(self, receipt) -> Optional[int]:
        """Parse the minted NFT token_id from the Transfer event in receipt logs."""
        # ERC721 Transfer(address,address,uint256) topic
        transfer_topic = Web3.keccak(text="Transfer(address,address,uint256)")
        for log in receipt.get("logs", []):
            if len(log["topics"]) >= 4 and log["topics"][0] == transfer_topic:
                # topics[3] is the tokenId for ERC721 Transfer
                token_id = int(log["topics"][3].hex(), 16)
                return token_id

        # Fallback: try IncreaseLiquidity event
        increase_topic = Web3.keccak(text="IncreaseLiquidity(uint256,uint128,uint256,uint256)")
        for log in receipt.get("logs", []):
            if log["topics"] and log["topics"][0] == increase_topic:
                token_id = int(log["topics"][1].hex(), 16)
                return token_id

        return None

    def _get_decimals(self, token_address: str) -> int:
        """Get token decimals (cached)."""
        if not hasattr(self, "_decimals_cache"):
            self._decimals_cache: dict[str, int] = {}
        if token_address in self._decimals_cache:
            return self._decimals_cache[token_address]
        try:
            contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(token_address),
                abi=ERC20_ABI,
            )
            decimals = contract.functions.decimals().call()
            self._decimals_cache[token_address] = decimals
            return decimals
        except Exception:
            return 18  # default

    def _store_closed_position(self, pos, net_pnl: float) -> None:
        """Store closed LP position to wp_lp_events."""
        if not self.persist:
            return
        try:
            from wolfpack.db import get_db
            db = get_db()
            db.table("wp_lp_events").insert({
                "event_type": "closed",
                "details": {
                    "position_id": pos.position_id,
                    "pool": pos.pool_address,
                    "pair": f"{pos.token0_symbol}/{pos.token1_symbol}",
                    "fees_earned": round(pos.fees_earned_usd, 2),
                    "il_usd": round(pos.il_usd, 2),
                    "net_pnl": round(net_pnl, 2),
                    "hold_minutes": (datetime.now(timezone.utc) - pos.opened_at).total_seconds() / 60,
                    "token_id": getattr(pos, "token_id", 0),
                    "mode": "live",
                },
            }).execute()
        except Exception as e:
            logger.warning(f"Failed to store LP close event: {e}")

    def take_snapshot(self) -> dict:
        """Generate a portfolio snapshot dict for Supabase storage."""
        positions_data = [
            {
                "position_id": p.position_id,
                "pool": p.pool_address,
                "pair": f"{p.token0_symbol}/{p.token1_symbol}",
                "liquidity_usd": round(p.liquidity_usd, 2),
                "fees": round(p.fees_earned_usd, 2),
                "il_pct": p.il_pct,
                "il_usd": round(p.il_usd, 2),
                "status": p.status,
                "ticks": [p.tick_lower, p.tick_upper],
                "current_tick": p.current_tick,
                "entry_price_ratio": round(p.entry_price_ratio, 6),
                "current_price_ratio": round(p.current_price_ratio, 6),
                "token_id": getattr(p, "token_id", 0),
                "mode": "live",
            }
            for p in self.portfolio.positions
        ]

        return {
            "total_value_usd": round(self.portfolio.equity, 2),
            "total_fees_usd": round(self.portfolio.total_fees_earned, 2),
            "total_il_usd": round(self.portfolio.total_il, 2),
            "positions": positions_data,
        }

    def store_snapshot(self) -> dict:
        """Persist portfolio state to wp_lp_snapshots."""
        if not self.persist:
            return {}
        try:
            from wolfpack.db import get_db
            db = get_db()
            snapshot = self.take_snapshot()
            result = db.table("wp_lp_snapshots").insert(snapshot).execute()
            return result.data[0] if result.data else snapshot
        except Exception as e:
            logger.warning(f"Failed to store LP snapshot: {e}")
            return {}

    def restore_from_snapshot(self) -> None:
        """Restore LP portfolio from latest Supabase snapshot.

        For live mode this is best-effort — on-chain state is the source of truth,
        but we restore tracked metrics (fees, IL, position metadata) from the snapshot.
        """
        if not self.persist:
            return
        try:
            from wolfpack.db import get_db
            db = get_db()
            result = (
                db.table("wp_lp_snapshots")
                .select("*")
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if result.data:
                snap = result.data[0]
                p = self.portfolio
                p.equity = snap.get("total_value_usd", 0)
                p.total_fees_earned = snap.get("total_fees_usd", 0.0)
                p.total_il = snap.get("total_il_usd", 0.0)
                p.positions.clear()
                for pos_data in snap.get("positions", []):
                    pair = pos_data.get("pair", "")
                    ticks = pos_data.get("ticks", [0, 0])
                    pos = LiveLPPosition(
                        position_id=pos_data.get("position_id", ""),
                        pool_address=pos_data.get("pool", ""),
                        token0_symbol=pair.split("/")[0] if "/" in pair else "",
                        token1_symbol=pair.split("/")[1] if "/" in pair else "",
                        fee_tier=3000,
                        tick_lower=ticks[0],
                        tick_upper=ticks[1],
                        liquidity_usd=pos_data.get("liquidity_usd", 0.0),
                        entry_price_ratio=pos_data.get("entry_price_ratio", 1.0),
                        current_price_ratio=pos_data.get("current_price_ratio", 1.0),
                        fees_earned_usd=pos_data.get("fees", 0.0),
                        il_pct=pos_data.get("il_pct", 0.0),
                        il_usd=pos_data.get("il_usd", 0.0),
                        status=pos_data.get("status", "active"),
                        current_tick=pos_data.get("current_tick", 0),
                        token_id=pos_data.get("token_id", 0),
                    )
                    p.positions.append(pos)
                    if pos.token_id > 0:
                        self._token_id_map[pos.pool_address] = pos.token_id

                locked = sum(pos.liquidity_usd for pos in p.positions if pos.status != "closed")
                p.free_collateral = max(0, p.equity - locked)
                self._recalculate()
                logger.info(f"Restored live LP portfolio from snapshot: ${p.equity:.2f} equity, {len(p.positions)} positions")
        except Exception as e:
            logger.warning(f"Failed to restore LP portfolio: {e}")
