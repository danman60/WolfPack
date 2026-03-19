"""Kraken exchange adapter using the Kraken CLI binary as backend."""

import asyncio
import json
import logging
import os
import time

from wolfpack.exchanges.base import (
    ExchangeAdapter,
    ExchangeId,
    Candle,
    FundingRate,
    MarketInfo,
    Orderbook,
    OrderbookLevel,
)

logger = logging.getLogger(__name__)

KRAKEN_CLI = os.path.expanduser("~/.cargo/bin/kraken")

# Interval mapping: WolfPack interval string -> Kraken CLI minutes
_INTERVAL_MAP = {
    "1m": 1,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "4h": 240,
    "1d": 1440,
}

# Symbol mapping: common name -> Kraken spot pair for OHLC
_SPOT_PAIR_MAP = {
    "BTC": "XBTUSD",
    "ETH": "ETHUSD",
    "SOL": "SOLUSD",
    "DOGE": "DOGEUSD",
    "XRP": "XRPUSD",
    "ADA": "ADAUSD",
    "AVAX": "AVAXUSD",
    "DOT": "DOTUSD",
    "LINK": "LINKUSD",
    "MATIC": "MATICUSD",
    "UNI": "UNIUSD",
    "ATOM": "ATOMUSD",
    "LTC": "LTCUSD",
    "ARB": "ARBUSD",
    "OP": "OPUSD",
    "APT": "APTUSD",
    "NEAR": "NEARUSD",
    "FIL": "FILUSD",
    "TIA": "TIAUSD",
    "SUI": "SUIUSD",
    "SEI": "SEIUSD",
    "INJ": "INJUSD",
    "FET": "FETUSD",
    "RENDER": "RENDERUSD",
    "PEPE": "PEPEUSD",
    "WIF": "WIFUSD",
    "BONK": "BONKUSD",
    "JUP": "JUPUSD",
    "AAVE": "AAVEUSD",
    "MKR": "MKRUSD",
}

# Futures perp prefix mapping
_FUTURES_PAIR_MAP = {k: f"PF_{v}" for k, v in _SPOT_PAIR_MAP.items()}
# Kraken futures uses XBT for BTC
_FUTURES_PAIR_MAP["BTC"] = "PF_XBTUSD"

# Simple TTL cache
_cache: dict[str, tuple[float, object]] = {}
_CACHE_TTLS = {
    "markets": 300,
    "candles": 60,
    "funding": 60,
    "orderbook": 10,
}


def _cache_get(key: str) -> object | None:
    if key in _cache:
        ts, data = _cache[key]
        ttl = _CACHE_TTLS.get(key.split(":")[0], 60)
        if time.time() - ts < ttl:
            return data
    return None


def _cache_set(key: str, data: object) -> None:
    _cache[key] = (time.time(), data)


def _now_ms() -> int:
    return int(time.time() * 1000)


class KrakenExchange(ExchangeAdapter):
    @property
    def id(self) -> ExchangeId:
        return "kraken"

    @property
    def name(self) -> str:
        return "Kraken"

    async def _run_cli(self, *args: str, timeout: float = 15) -> dict | list:
        """Run the Kraken CLI and return parsed JSON output."""
        cmd = [KRAKEN_CLI] + list(args) + ["-o", "json"]
        logger.debug(f"[kraken-cli] Running: {' '.join(cmd)}")
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            if proc.returncode != 0:
                err_msg = stderr.decode().strip() if stderr else "unknown error"
                logger.error(f"[kraken-cli] Exit {proc.returncode}: {err_msg}")
                raise RuntimeError(f"Kraken CLI error: {err_msg}")
            return json.loads(stdout.decode())
        except asyncio.TimeoutError:
            logger.error(f"[kraken-cli] Timeout after {timeout}s: {' '.join(cmd)}")
            raise RuntimeError(f"Kraken CLI timeout: {' '.join(args)}")

    async def get_markets(self) -> list[MarketInfo]:
        cache_key = "markets"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached  # type: ignore

        data = await self._run_cli("futures", "tickers")
        tickers = data.get("tickers", data) if isinstance(data, dict) else data
        if isinstance(tickers, dict):
            tickers = list(tickers.values()) if not isinstance(list(tickers.values())[0] if tickers else None, dict) else list(tickers.values())

        markets: list[MarketInfo] = []
        for t in (tickers if isinstance(tickers, list) else []):
            symbol_raw = t.get("symbol", t.get("pair", ""))
            # Only include perpetual futures (PF_ prefix)
            if not str(symbol_raw).startswith("PF_"):
                continue

            # Map back to common symbol name
            common_name = str(symbol_raw).replace("PF_", "").replace("USD", "").replace("XBT", "BTC")

            markets.append(
                MarketInfo(
                    symbol=common_name,
                    base_asset=common_name,
                    last_price=float(t.get("last", t.get("markPrice", 0))),
                    volume_24h=float(t.get("vol24h", t.get("volumeQuote", 0))),
                    open_interest=float(t.get("openInterest", 0)),
                    funding_rate=float(t.get("fundingRate", t.get("funding_rate", 0))),
                    max_leverage=50,
                )
            )

        _cache_set(cache_key, markets)
        return markets

    async def get_candles(
        self, symbol: str, interval: str = "1h", limit: int = 100, start_time: int | None = None
    ) -> list[Candle]:
        cache_key = f"candles:{symbol}:{interval}:{limit}:{start_time}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached  # type: ignore

        pair = _SPOT_PAIR_MAP.get(symbol.upper(), f"{symbol.upper()}USD")
        mins = _INTERVAL_MAP.get(interval, 60)

        args = ["ohlc", pair, "--interval", str(mins)]
        if start_time is not None:
            args += ["--since", str(start_time // 1000)]

        data = await self._run_cli(*args)

        # Kraken OHLC returns {pair_key: [[ts, o, h, l, c, vwap, vol, count], ...]}
        candle_arrays: list = []
        if isinstance(data, dict):
            # Find the candle data — skip the "last" key
            for key, val in data.items():
                if key != "last" and isinstance(val, list):
                    candle_arrays = val
                    break
        elif isinstance(data, list):
            candle_arrays = data

        candles: list[Candle] = []
        for c in candle_arrays[-limit:]:
            if isinstance(c, list) and len(c) >= 6:
                candles.append(
                    Candle(
                        timestamp=int(float(c[0])) * 1000,  # Kraken returns seconds
                        open=float(c[1]),
                        high=float(c[2]),
                        low=float(c[3]),
                        close=float(c[4]),
                        volume=float(c[6]) if len(c) > 6 else 0,
                    )
                )

        _cache_set(cache_key, candles)
        return candles

    async def get_funding_rates(self) -> list[FundingRate]:
        cache_key = "funding"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached  # type: ignore

        data = await self._run_cli("futures", "tickers")
        tickers = data.get("tickers", data) if isinstance(data, dict) else data

        rates: list[FundingRate] = []
        for t in (tickers if isinstance(tickers, list) else []):
            symbol_raw = t.get("symbol", t.get("pair", ""))
            if not str(symbol_raw).startswith("PF_"):
                continue
            common_name = str(symbol_raw).replace("PF_", "").replace("USD", "").replace("XBT", "BTC")
            rates.append(
                FundingRate(
                    symbol=common_name,
                    rate=float(t.get("fundingRate", t.get("funding_rate", 0))),
                    next_funding_time=_now_ms() + 3600_000,
                )
            )

        _cache_set(cache_key, rates)
        return rates

    async def get_orderbook(self, symbol: str, depth: int = 20) -> Orderbook:
        cache_key = f"orderbook:{symbol}:{depth}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached  # type: ignore

        futures_pair = _FUTURES_PAIR_MAP.get(symbol.upper(), f"PF_{symbol.upper()}USD")
        data = await self._run_cli("futures", "orderbook", futures_pair)

        # Parse orderbook response
        ob_data = data.get("orderBook", data) if isinstance(data, dict) else data
        bids_raw = ob_data.get("bids", []) if isinstance(ob_data, dict) else []
        asks_raw = ob_data.get("asks", []) if isinstance(ob_data, dict) else []

        bids = [
            OrderbookLevel(
                price=float(b.get("price", b[0]) if isinstance(b, dict) else b[0]),
                size=float(b.get("qty", b.get("size", b[1])) if isinstance(b, dict) else b[1]),
            )
            for b in bids_raw[:depth]
        ]
        asks = [
            OrderbookLevel(
                price=float(a.get("price", a[0]) if isinstance(a, dict) else a[0]),
                size=float(a.get("qty", a.get("size", a[1])) if isinstance(a, dict) else a[1]),
            )
            for a in asks_raw[:depth]
        ]

        result = Orderbook(symbol=symbol, bids=bids, asks=asks, timestamp=_now_ms())
        _cache_set(cache_key, result)
        return result
