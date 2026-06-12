"""Turtle breadth study — step 1: universe selection + 4h candle fetch.

RESEARCH ONLY. New files only, all under docs/research/2026-06-turtle-breadth/.

Universe rule (deterministic, documented):
  liquid tier = (24h notional volume > $10M) UNION (open-interest notional > $20M)
  on live (non-delisted) Hyperliquid perps, snapshot at run time.
  Rationale: single-day volume is noisy (snapshot day was quiet — DOGE/AVAX/LINK
  printed <$10M vol but carry $20-30M OI); OI is the stable liquidity measure.

Survivorship caveat: delisted perps are invisible to this query. For liquid
large-caps the bias is far smaller than small-caps, but it exists.

Candles: Hyperliquid /info candleSnapshot, 4h, ~5000-candle cap (= ~27 months).
Cached to candles/<SYM>.json as rows [t, o, h, l, c, v].
"""

import json
import time
from pathlib import Path

import httpx

HL_API = "https://api.hyperliquid.xyz/info"
INTERVAL = "4h"
BAR_MS = 4 * 3600 * 1000
N_BARS = 5000
VOL_FLOOR = 10e6
OI_FLOOR = 20e6
MIN_BARS = 1500  # ~8 months; below this a symbol is too young to test

OUT_DIR = Path(__file__).parent
CANDLE_DIR = OUT_DIR / "candles"
CANDLE_DIR.mkdir(exist_ok=True)


def get_universe(client: httpx.Client) -> list[dict]:
    r = client.post(HL_API, json={"type": "metaAndAssetCtxs"}, timeout=30)
    r.raise_for_status()
    meta, ctxs = r.json()
    rows = []
    for u, c in zip(meta["universe"], ctxs):
        if u.get("isDelisted"):
            continue
        vol = float(c.get("dayNtlVlm", 0))
        oi = float(c.get("openInterest", 0)) * float(c.get("markPx", 0) or 0)
        if vol > VOL_FLOOR or oi > OI_FLOOR:
            rows.append({"symbol": u["name"], "vol_24h_usd": round(vol),
                         "oi_usd": round(oi),
                         "via": "vol" if vol > VOL_FLOOR else "oi"})
    rows.sort(key=lambda r: -r["vol_24h_usd"])
    return rows


def fetch_candles(client: httpx.Client, sym: str) -> list[list]:
    end = int(time.time() * 1000)
    start = end - N_BARS * BAR_MS
    r = client.post(HL_API, json={"type": "candleSnapshot",
                                  "req": {"coin": sym, "interval": INTERVAL,
                                          "startTime": start, "endTime": end}},
                    timeout=60)
    r.raise_for_status()
    raw = r.json()
    return [[int(c["t"]), float(c["o"]), float(c["h"]), float(c["l"]),
             float(c["c"]), float(c["v"])] for c in raw]


def main():
    with httpx.Client() as client:
        universe = get_universe(client)
        print(f"liquid tier: {len(universe)} symbols")
        ok, skipped, failed = [], [], []
        for row in universe:
            sym = row["symbol"]
            try:
                candles = fetch_candles(client, sym)
            except Exception as e:
                print(f"  {sym}: FETCH FAILED {e}")
                failed.append({"symbol": sym, "error": str(e)})
                continue
            row["n_candles"] = len(candles)
            if candles:
                row["start"] = time.strftime("%Y-%m-%d", time.gmtime(candles[0][0] / 1000))
                row["end"] = time.strftime("%Y-%m-%d", time.gmtime(candles[-1][0] / 1000))
            if len(candles) < MIN_BARS:
                print(f"  {sym}: only {len(candles)} bars (<{MIN_BARS}) — too young, skipped")
                skipped.append(row)
                continue
            (CANDLE_DIR / f"{sym}.json").write_text(json.dumps(candles))
            print(f"  {sym}: {len(candles)} bars {row.get('start')} -> {row.get('end')} "
                  f"vol=${row['vol_24h_usd']/1e6:.1f}M oi=${row['oi_usd']/1e6:.1f}M")
            ok.append(row)
            time.sleep(0.3)  # be polite

    out = {"fetched_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "rule": f"vol24h>${VOL_FLOOR/1e6:.0f}M OR oi>${OI_FLOOR/1e6:.0f}M, min {MIN_BARS} 4h bars",
           "universe": ok, "skipped_too_young": skipped, "fetch_failed": failed}
    (OUT_DIR / "universe.json").write_text(json.dumps(out, indent=2))
    print(f"\n{len(ok)} symbols usable, {len(skipped)} too young, {len(failed)} failed")
    print("wrote universe.json")


if __name__ == "__main__":
    main()
