"""
Walk-forward validation of DOGE short mean-reversion at 3.0 ATR.

The full-90d result was +12.33% on 30 trades. We need to know if this is robust
across sub-periods (early 30d, mid 30d, late 30d) — i.e., does the edge persist
or did one period contribute all of it?

Also: stretch test on full DOGE history from finetune/ pickles to see year-by-year
performance of this specific strategy (NOT for "does it work all time" — for "what
regimes does it work in").
"""
from __future__ import annotations

import math
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from strategy_existing_meanrev import backtest_meanrev  # noqa: E402

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
FT = HERE / "finetune"
RESULTS = HERE / "results"


def main() -> int:
    # 1. 90d split into 3 × 30d windows
    csv = DATA / "DOGEUSDT_1h_90d.csv"
    df = pd.read_csv(csv, parse_dates=["timestamps"]).sort_values("timestamps").reset_index(drop=True)
    bars = 30 * 24
    print("=== DOGE 90d split into 3 × 30d windows (short_no_sweep, prod preset) ===\n")
    print(f"{'window':<8} {'span':<35} {'n':<4} {'wr':<6} {'avg_net':<10} {'total':<10} {'hodl':<10} {'sharpe':<8}")
    for i in range(3):
        sub = df.iloc[i * bars:(i + 1) * bars].reset_index(drop=True)
        trades, s = backtest_meanrev(sub, "DOGE", short_only=True, use_sweep_filter=False)
        span = f"{sub['timestamps'].iloc[0].date()}→{sub['timestamps'].iloc[-1].date()}"
        if s.get("n", 0) == 0:
            print(f"{i:<8} {span:<35} 0")
            continue
        print(f"{i:<8} {span:<35} {s['n']:<4} {s['win_rate']:<6} {s['avg_net_pct']:<10} {s['total_pct']:<10} {s['hodl_pct']:<10} {s['sharpe']:<8}")

    # 2. Full DOGE history year-by-year (yes, multi-year — but only to know regime sensitivity)
    print("\n\n=== DOGE FULL HISTORY year-by-year (same strategy, same params) ===\n")
    chunks = []
    for name in ["train_data.pkl", "val_data.pkl", "eval_data.pkl"]:
        p = FT / name
        if p.exists():
            with open(p, "rb") as f:
                d = pickle.load(f)
            if "DOGEUSDT" in d:
                chunks.append(d["DOGEUSDT"])
    full_df = pd.concat(chunks).sort_index() if chunks else pd.DataFrame()
    if full_df.empty:
        print("(no full-history DOGE pickle — skipping)")
        return 0
    full_df = full_df[~full_df.index.duplicated(keep="last")]
    full_df = full_df.rename(columns={"vol": "volume", "amt": "amount"})
    full_df = full_df.reset_index().rename(columns={"datetime": "timestamps"})
    full_df["year"] = pd.to_datetime(full_df["timestamps"]).dt.year

    print(f"{'year':<6} {'n':<5} {'wr':<6} {'avg_net':<10} {'total':<10} {'hodl':<10} {'sharpe':<8}")
    for year in sorted(full_df["year"].unique()):
        sub = full_df[full_df["year"] == year].reset_index(drop=True)
        if len(sub) < 100:
            continue
        trades, s = backtest_meanrev(sub, "DOGE", short_only=True, use_sweep_filter=False)
        if s.get("n", 0) == 0:
            continue
        print(f"{year:<6} {s['n']:<5} {s['win_rate']:<6} {s['avg_net_pct']:<10} {s['total_pct']:<10} {s['hodl_pct']:<10} {s['sharpe']:<8}")

    # 3. Rolling 30d windows over full history (more granular regime sensitivity)
    full_df["timestamps"] = pd.to_datetime(full_df["timestamps"])
    bars = 30 * 24
    rolling_results = []
    for start in range(0, len(full_df) - bars, bars // 2):  # overlapping 30d windows every 15d
        sub = full_df.iloc[start:start + bars].reset_index(drop=True)
        trades, s = backtest_meanrev(sub, "DOGE", short_only=True, use_sweep_filter=False)
        if s.get("n", 0) >= 3:
            s["window_start"] = sub["timestamps"].iloc[0]
            s["window_end"] = sub["timestamps"].iloc[-1]
            rolling_results.append(s)
    rdf = pd.DataFrame(rolling_results)
    if not rdf.empty:
        print(f"\n=== Rolling 30d windows (n≥3 trades) — total {len(rdf)} windows ===")
        positive = (rdf["total_pct"] > 0).sum()
        beat_hodl = (rdf["total_pct"] > rdf["hodl_pct"]).sum()
        print(f"  windows with positive strategy return: {positive}/{len(rdf)} ({positive/len(rdf)*100:.1f}%)")
        print(f"  windows where strategy beat HODL:      {beat_hodl}/{len(rdf)} ({beat_hodl/len(rdf)*100:.1f}%)")
        print(f"  mean total_pct across windows:         {rdf['total_pct'].mean():.2f}%")
        print(f"  median total_pct:                      {rdf['total_pct'].median():.2f}%")
        print(f"  mean win_rate:                         {rdf['win_rate'].mean():.2f}%")
        # Save full
        rdf.to_csv(RESULTS / "doge_rolling_30d_full_history.csv", index=False)
        print(f"\nSaved → {RESULTS / 'doge_rolling_30d_full_history.csv'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
