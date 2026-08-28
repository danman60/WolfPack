"""Finer-grained walk-forward: overlapping 15-day windows every 5 days."""
import pickle
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from strategy_existing_meanrev import backtest_meanrev  # noqa: E402

HERE = Path(__file__).resolve().parent

df = pd.read_csv(HERE / "data" / "DOGEUSDT_1h_90d.csv", parse_dates=["timestamps"]).sort_values("timestamps").reset_index(drop=True)
bars_win = 15 * 24
step_bars = 5 * 24

print(f"{'win#':<5} {'span':<35} {'n':<4} {'wr':<6} {'total':<9} {'hodl':<9} {'beats':<6}")
rows = []
total_n = 0; total_beat = 0; total_pos = 0
i = 0
for start in range(0, len(df) - bars_win + 1, step_bars):
    sub = df.iloc[start:start + bars_win].reset_index(drop=True)
    trades, s = backtest_meanrev(sub, "DOGE", short_only=True, use_sweep_filter=False)
    if s.get("n", 0) == 0:
        continue
    span = f"{sub['timestamps'].iloc[0].date()}→{sub['timestamps'].iloc[-1].date()}"
    beats = s["total_pct"] > s["hodl_pct"]
    print(f"{i:<5} {span:<35} {s['n']:<4} {s['win_rate']:<6} {s['total_pct']:<9} {s['hodl_pct']:<9} {'YES' if beats else 'no'}")
    rows.append({**s, "window_idx": i, "span": span, "beats_hodl": beats})
    total_n += 1
    if beats:
        total_beat += 1
    if s["total_pct"] > 0:
        total_pos += 1
    i += 1

print(f"\nTotal windows with n≥1: {total_n}")
print(f"Positive return:       {total_pos}/{total_n} ({total_pos/total_n*100:.1f}%)")
print(f"Beat HODL:             {total_beat}/{total_n} ({total_beat/total_n*100:.1f}%)")
res = pd.DataFrame(rows)
mean_total = res["total_pct"].mean()
mean_hodl = res["hodl_pct"].mean()
print(f"Mean window total_pct: {mean_total:.2f}%")
print(f"Mean window hodl_pct:  {mean_hodl:.2f}%")
print(f"Mean alpha vs HODL:    {mean_total - mean_hodl:+.2f}%")
res.to_csv(HERE / "results" / "doge_rolling_15d.csv", index=False)
