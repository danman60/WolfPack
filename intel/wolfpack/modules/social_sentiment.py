"""Social Sentiment — Fear & Greed Index + CoinGecko trending/social data.

Free APIs, no keys needed:
- alternative.me Fear & Greed Index
- CoinGecko trending coins + coin community data
"""

import logging
from typing import Any

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# CoinGecko ID mapping for common perp symbols
_COINGECKO_IDS: dict[str, str] = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "LINK": "chainlink",
    "DOGE": "dogecoin",
    "ARB": "arbitrum",
    "AVAX": "avalanche-2",
    "MATIC": "matic-network",
    "OP": "optimism",
    "APT": "aptos",
    "SUI": "sui",
    "NEAR": "near",
    "ATOM": "cosmos",
    "DOT": "polkadot",
    "ADA": "cardano",
    "XRP": "ripple",
    "FIL": "filecoin",
    "LTC": "litecoin",
    "UNI": "uniswap",
    "AAVE": "aave",
}

TIMEOUT = 5.0


class SocialSentimentOutput(BaseModel):
    fear_greed_index: int  # 0-100
    fear_greed_label: str  # "Extreme Fear" -> "Extreme Greed"
    trending_coins: list[str]  # top 7 trending on CoinGecko
    symbol_social_score: float  # 0-100
    is_symbol_trending: bool


class SocialSentimentAnalyzer:
    """Fetches social sentiment from free public APIs."""

    async def analyze(self, symbol: str = "BTC") -> SocialSentimentOutput:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            fng_data, trending_data, coin_data = await _fetch_all(client, symbol)

        # Fear & Greed
        fear_greed_index = 50
        fear_greed_label = "Neutral"
        if fng_data:
            try:
                entry = fng_data["data"][0]
                fear_greed_index = int(entry["value"])
                fear_greed_label = entry["value_classification"]
            except (KeyError, IndexError, ValueError):
                pass

        # Trending coins
        trending_coins: list[str] = []
        is_symbol_trending = False
        if trending_data:
            try:
                for item in trending_data.get("coins", [])[:7]:
                    coin = item.get("item", {})
                    sym = coin.get("symbol", "").upper()
                    trending_coins.append(sym)
                    if sym == symbol.upper():
                        is_symbol_trending = True
            except (KeyError, TypeError):
                pass

        # Symbol social score from CoinGecko community data
        symbol_social_score = 50.0
        if coin_data:
            try:
                community = coin_data.get("community_score", 0) or 0
                developer = coin_data.get("developer_score", 0) or 0
                public_interest = coin_data.get("public_interest_score", 0) or 0
                # Weighted average, normalized to 0-100
                raw = community * 0.4 + developer * 0.3 + public_interest * 0.3
                symbol_social_score = min(100.0, max(0.0, raw))
            except (KeyError, TypeError, ValueError):
                pass

        return SocialSentimentOutput(
            fear_greed_index=fear_greed_index,
            fear_greed_label=fear_greed_label,
            trending_coins=trending_coins,
            symbol_social_score=round(symbol_social_score, 1),
            is_symbol_trending=is_symbol_trending,
        )


async def _fetch_all(
    client: httpx.AsyncClient, symbol: str
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None]:
    """Fetch all three APIs concurrently with graceful fallback."""
    import asyncio

    async def _fng() -> dict[str, Any] | None:
        try:
            resp = await client.get("https://api.alternative.me/fng/")
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"[social] Fear & Greed fetch failed: {e}")
            return None

    async def _trending() -> dict[str, Any] | None:
        try:
            resp = await client.get("https://api.coingecko.com/api/v3/search/trending")
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"[social] CoinGecko trending fetch failed: {e}")
            return None

    async def _coin_data() -> dict[str, Any] | None:
        cg_id = _COINGECKO_IDS.get(symbol.upper())
        if not cg_id:
            return None
        try:
            resp = await client.get(
                f"https://api.coingecko.com/api/v3/coins/{cg_id}",
                params={"localization": "false", "tickers": "false", "market_data": "false", "community_data": "true", "developer_data": "true"},
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"[social] CoinGecko coin data fetch failed for {symbol}: {e}")
            return None

    results = await asyncio.gather(_fng(), _trending(), _coin_data(), return_exceptions=True)
    return (
        results[0] if not isinstance(results[0], Exception) else None,
        results[1] if not isinstance(results[1], Exception) else None,
        results[2] if not isinstance(results[2], Exception) else None,
    )
