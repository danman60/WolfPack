#!/usr/bin/env python3
"""Moonshot Scalper — buzz x HL small-cap screener (RESEARCH / FORWARD-WATCH ONLY).

NO TRADING. NO DB WRITES. NO WALLET CONFIG. Writes ranked candidate "shots" to a
local JSONL signal log for forward observation. Run manually or on cron.

Pipeline
--------
1. Pull the live Hyperliquid perp universe (vol / OI / maxLeverage) and flag the
   small-cap tier (24h vol < $5M).
2. Pull buzz signals:
     - CoinGecko trending (PRIMARY — empirically the only free source that maps to
       HL-listed alts; see buzz-overlap-probe.md).
     - 4chan /biz/ catalog cashtag/ALLCAPS mentions (SECONDARY, low weight — mostly
       meme-stocks/majors, rarely hits HL small-caps; kept for completeness).
     - Reddit: BLOCKED from server IPs (403). Stub left in place; enable if run from
       a residential IP or with an authed API key.
3. Score buzz per ticker, intersect with the HL small-cap universe.
4. For each survivor, pull 5m candles from the intel API and run the existing
   `momentum_buckets` module as the chart trigger (regime_hint / momentum_score).
5. Estimate live spread from the HL L2 book; write ranked shots to signals.jsonl.

Run:
    python -m wolfpack.research.moonshot_screener
    # or
    python intel/wolfpack/research/moonshot_screener.py
"""
from __future__ import annotations

import collections
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

# Reuse the existing trading-grade modules (import only — do NOT modify them).
try:
    from wolfpack.exchanges.base import Candle
    from wolfpack.modules.momentum_buckets import MomentumBuckets
except ModuleNotFoundError:  # allow running as a bare script from repo root
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from wolfpack.exchanges.base import Candle
    from wolfpack.modules.momentum_buckets import MomentumBuckets

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
HL_INFO = "https://api.hyperliquid.xyz/info"
INTEL_BASE = "http://159.89.115.95:8000"  # intel service (candles endpoint)
CG_TRENDING = "https://api.coingecko.com/api/v3/search/trending"
BIZ_CATALOG = "https://a.4cdn.org/biz/catalog.json"

SMALL_CAP_VOL_MAX = 5_000_000   # <$5M/24h = HL small-cap tier
VOL_FLOOR = 250_000             # reject untradeable dust
SPREAD_GATE_BPS = 25.0          # reject illiquid books
UA = {"User-Agent": "Mozilla/5.0 (compatible; wolfpack-research/0.1)"}

OUT_DIR = Path(__file__).resolve().parents[3] / "docs" / "research" / "2026-06-moonshot-scalper"
SIGNALS_PATH = OUT_DIR / "signals.jsonl"

# ALLCAPS noise to strip from /biz/ token extraction.
_NOISE = {
    "THE", "AND", "FOR", "YOU", "ARE", "NOT", "BUT", "WITH", "THIS", "THAT", "ALL",
    "NEW", "NOW", "GET", "WHY", "HOW", "WHO", "CAN", "HAS", "HAD", "WAS", "ITS", "OUT",
    "ONE", "TWO", "USD", "USDT", "DEX", "CEX", "ATH", "FUD", "FOMO", "WAGMI", "NGMI",
    "HODL", "IMO", "DYOR", "LFG", "GM", "API", "CEO", "NFT", "DAO", "TBH", "ICO", "ROI",
    "TVL", "RSI", "EMA", "OG", "IT", "IS", "TO", "OF", "IN", "ON", "AT", "BE", "DO",
    "GO", "NO", "SO", "UP", "OR", "IF", "MY", "WE", "HE", "AN", "AS", "BY", "OK", "LOL",
    "WTF", "USA", "SEC", "FBI", "CIA", "ETF", "GDP", "FED", "IRS", "US", "EU", "UK",
    "DE", "DK", "RC", "TV", "OH", "AI", "SHIT", "MONEY", "MARKET", "WHAT", "STOCK",
    "GRAIL", "CUSIP", "THINK",
}


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------
def fetch_hl_universe(client: httpx.Client) -> dict:
    """Live HL perp universe -> {sym: {vol, oi_usd, maxlev, mark}} for ACTIVE perps."""
    r = client.post(HL_INFO, json={"type": "metaAndAssetCtxs"}, timeout=30)
    meta, ctxs = r.json()
    rows = {}
    for u, c in zip(meta["universe"], ctxs):
        if u.get("isDelisted"):
            continue
        mark = float(c.get("markPx", 0) or 0)
        rows[u["name"]] = {
            "vol": float(c.get("dayNtlVlm", 0) or 0),
            "oi_usd": float(c.get("openInterest", 0) or 0) * mark,
            "maxlev": u.get("maxLeverage", 0),
            "mark": mark,
        }
    return rows


def fetch_coingecko_trending(client: httpx.Client) -> list[str]:
    try:
        d = client.get(CG_TRENDING, timeout=30, headers=UA).json()
        return [c["item"]["symbol"].upper() for c in d.get("coins", [])]
    except Exception as e:  # noqa: BLE001
        print(f"[warn] CoinGecko trending failed: {e}", file=sys.stderr)
        return []


def fetch_biz_mentions(client: httpx.Client) -> dict[str, int]:
    try:
        data = client.get(BIZ_CATALOG, timeout=30, headers=UA).json()
    except Exception as e:  # noqa: BLE001
        print(f"[warn] /biz/ catalog failed: {e}", file=sys.stderr)
        return {}
    texts = []
    for page in data:
        for t in page.get("threads", []):
            for k in ("sub", "com"):
                if t.get(k):
                    texts.append(t[k])
    blob = re.sub(r"<[^>]+>", " ", " ".join(texts))
    cnt: collections.Counter = collections.Counter()
    for c in re.findall(r"\$([A-Za-z]{2,6})\b", blob):
        cnt[c.upper()] += 2  # cashtags weighted
    for c in re.findall(r"\b([A-Z]{2,6})\b", blob):
        cnt[c] += 1
    return {k: v for k, v in cnt.items() if k not in _NOISE}


def fetch_reddit_mentions(client: httpx.Client) -> dict[str, int]:
    """BLOCKED from datacenter IPs (Reddit returns 403). Returns {} unless reachable."""
    subs = [("CryptoMoonShots", "top", "day"), ("CryptoCurrency", "hot", ""),
            ("SatoshiStreetBets", "top", "day"), ("altcoin", "hot", "")]
    cnt: collections.Counter = collections.Counter()
    ok = False
    for sub, sort, t in subs:
        url = f"https://www.reddit.com/r/{sub}/{sort}.json?limit=100" + (f"&t={t}" if t else "")
        try:
            r = client.get(url, headers=UA, timeout=20)
            if r.status_code != 200:
                continue
            ok = True
            for ch in r.json().get("data", {}).get("children", []):
                blob = (ch["data"].get("title", "") or "") + " " + (ch["data"].get("selftext", "") or "")
                for c in re.findall(r"\$([A-Za-z]{2,6})\b", blob):
                    cnt[c.upper()] += 2
                for c in re.findall(r"\b([A-Z]{2,6})\b", blob):
                    cnt[c] += 1
            time.sleep(1)
        except Exception:  # noqa: BLE001
            continue
    if not ok:
        print("[warn] Reddit unreachable (403/IP-block) — skipped.", file=sys.stderr)
    return {k: v for k, v in cnt.items() if k not in _NOISE}


# ---------------------------------------------------------------------------
# Buzz scoring + chart trigger
# ---------------------------------------------------------------------------
def build_buzz(cg_trending: list[str], biz: dict[str, int], reddit: dict[str, int]) -> dict[str, dict]:
    """buzz_score in [0,100]: CG trending dominates (it's the source that maps to HL)."""
    buzz: dict[str, dict] = {}
    for sym in cg_trending:
        b = buzz.setdefault(sym, {"score": 0.0, "sources": []})
        b["score"] += 60.0
        b["sources"].append("coingecko_trending")
    for sym, n in biz.items():
        b = buzz.setdefault(sym, {"score": 0.0, "sources": []})
        b["score"] += min(n * 2.0, 25.0)
        b["sources"].append(f"biz:{n}")
    for sym, n in reddit.items():
        b = buzz.setdefault(sym, {"score": 0.0, "sources": []})
        b["score"] += min(n * 2.0, 25.0)
        b["sources"].append(f"reddit:{n}")
    for b in buzz.values():
        b["score"] = round(min(b["score"], 100.0), 1)
    return buzz


def fetch_candles(client: httpx.Client, symbol: str, interval: str = "5m", limit: int = 100) -> list[Candle]:
    try:
        d = client.get(f"{INTEL_BASE}/market/candles",
                       params={"symbol": symbol, "interval": interval, "limit": limit},
                       timeout=25).json()
        return [Candle(**c) for c in d.get("candles", [])]
    except Exception as e:  # noqa: BLE001
        print(f"[warn] candles {symbol} failed: {e}", file=sys.stderr)
        return []


def fetch_spread_bps(client: httpx.Client, symbol: str) -> float | None:
    """Top-of-book spread in bps from the HL L2 snapshot."""
    try:
        r = client.post(HL_INFO, json={"type": "l2Book", "coin": symbol}, timeout=20)
        levels = r.json().get("levels", [])
        if len(levels) < 2 or not levels[0] or not levels[1]:
            return None
        bid = float(levels[0][0]["px"]); ask = float(levels[1][0]["px"])
        mid = (bid + ask) / 2
        return round((ask - bid) / mid * 10_000, 2) if mid > 0 else None
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def run() -> list[dict]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    mb = MomentumBuckets()
    shots: list[dict] = []
    ts = datetime.now(timezone.utc).isoformat()

    with httpx.Client() as client:
        hl = fetch_hl_universe(client)
        small_cap = {s: r for s, r in hl.items() if r["vol"] < SMALL_CAP_VOL_MAX and r["vol"] >= VOL_FLOOR}
        print(f"HL active={len(hl)}  small-cap(<${SMALL_CAP_VOL_MAX/1e6:.0f}M, >=${VOL_FLOOR/1e3:.0f}k)={len(small_cap)}")

        cg = fetch_coingecko_trending(client)
        biz = fetch_biz_mentions(client)
        reddit = fetch_reddit_mentions(client)
        buzz = build_buzz(cg, biz, reddit)
        print(f"buzz tickers: cg={len(cg)} biz={len(biz)} reddit={len(reddit)} union={len(buzz)}")

        # Candidates = buzzed AND in HL small-cap universe.
        candidates = [s for s in buzz if s in small_cap]
        print(f"buzz x HL-small-cap overlap: {len(candidates)} -> {candidates}")

        for sym in candidates:
            r = small_cap[sym]
            candles = fetch_candles(client, sym, "5m", 100)
            if len(candles) < 20:
                print(f"  [skip] {sym}: only {len(candles)} candles")
                continue
            m = mb.analyze(candles, asset=sym)
            spread = fetch_spread_bps(client, sym)
            entry = candles[-1].close
            shot = {
                "ts": ts,
                "ticker": sym,
                "buzz_score": buzz[sym]["score"],
                "sources": buzz[sym]["sources"],
                "hl_vol_24h": round(r["vol"]),
                "hl_oi_usd": round(r["oi_usd"]),
                "hl_maxlev": r["maxlev"],
                "chart_state": {
                    "regime_hint": m.regime_hint,
                    "momentum_score": m.momentum_score,
                    "conviction": m.conviction,
                    "primary_trend": m.primary_trend.value,
                },
                "est_spread_bps": spread,
                "spread_gate_pass": (spread is not None and spread <= SPREAD_GATE_BPS),
                # Hypothetical asymmetric small-bet plan (NO trade placed):
                "hypo_entry": entry,
                "hypo_stop": round(entry * 0.96, 8),       # -4%
                "hypo_target": round(entry * 1.08, 8),     # +8% (scale 50%, trail rest)
                # Is this a "fresh breakout" shot per the scope ruleset?
                "is_shot": (
                    m.regime_hint == "breakout"
                    and m.momentum_score >= 0.4
                    and m.conviction >= 0.5
                    and spread is not None and spread <= SPREAD_GATE_BPS
                ),
            }
            shots.append(shot)
            print(f"  {sym:8} buzz={shot['buzz_score']:5} regime={m.regime_hint:13} "
                  f"mom={m.momentum_score:+.2f} conv={m.conviction:.2f} spread={spread}bps "
                  f"shot={shot['is_shot']}")

    # Append every evaluated candidate to the forward-watch log (observation, not trades).
    with SIGNALS_PATH.open("a") as f:
        for s in shots:
            f.write(json.dumps(s) + "\n")
    n_shots = sum(1 for s in shots if s["is_shot"])
    print(f"\nWrote {len(shots)} candidate rows ({n_shots} pass full 'shot' gate) -> {SIGNALS_PATH}")
    return shots


if __name__ == "__main__":
    run()
