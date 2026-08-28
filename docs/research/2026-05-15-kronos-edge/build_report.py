"""
Builds the final ranked-edge-findings markdown report from the 5 results CSVs.

Output: RESULTS.md (sibling to this script).

Ranks each idea by its best-symbol Sharpe (or best-bucket abs_fwd_ret for non-strategy
ideas), labels what beat HODL after costs, and produces a recommendation block.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
RESULTS_DIR = HERE / "results"
OUT_PATH = HERE / "RESULTS.md"


def fmt_table(df: pd.DataFrame) -> str:
    return df.to_markdown(index=False, floatfmt=".3f")


def section_idea1() -> str:
    p = RESULTS_DIR / "idea1_direct_strategy.csv"
    if not p.exists():
        return "## Idea #1 — Direct strategy\n_Not run._\n"
    df = pd.read_csv(p)
    best_per_symbol = df.sort_values(["symbol", "tf", "sharpe"], ascending=[True, True, False]).groupby(["symbol", "tf"]).head(1).reset_index(drop=True)
    return ("## Idea #1 — Direct Kronos-as-strategy\n\n"
            "Sign of predicted 24h cumulative return → long/short/flat. Non-overlap. Realistic fees + slippage (0.085% round-trip).\n\n"
            "### Full sweep\n\n"
            f"{fmt_table(df)}\n\n"
            "### Best threshold per (symbol, tf)\n\n"
            f"{fmt_table(best_per_symbol)}\n")


def section_idea2() -> str:
    p = RESULTS_DIR / "idea2_divergence.csv"
    if not p.exists():
        return "## Idea #2 — Divergence\n_Not run._\n"
    df = pd.read_csv(p)
    return ("## Idea #2 — Predict-vs-realize divergence signal\n\n"
            "Hypothesis: early-window residual (real - pred) over the first 4 candles predicts the remaining window's direction (momentum vs mean reversion).\n\n"
            f"{fmt_table(df)}\n\n"
            "Interpretation: if `follow_residual_pct` > `revert_residual_pct` in the high-|residual| buckets, residuals carry momentum information (trade with the surprise). Opposite = mean reversion against the surprise.\n")


def section_idea3() -> str:
    p = RESULTS_DIR / "idea3_prob_of_touch.csv"
    if not p.exists():
        return "## Idea #3 — Probability-of-touch\n_Not run._\n"
    df = pd.read_csv(p)
    return ("## Idea #3 — Probability-of-touch\n\n"
            "Kronos run with sample_count=50 on a strided subset; predicted high/low compared to realized 24h high/low. Used to set realistic stop / TP distances.\n\n"
            f"{fmt_table(df)}\n\n"
            "Interpretation: `precision_up` = of windows where Kronos said price would touch +X%, what fraction actually did. >50% on smaller thresholds = useful for stop placement. Sharply low = Kronos overestimates range.\n")


def section_idea4() -> str:
    p = RESULTS_DIR / "idea4_tokenizer_perplexity.csv"
    if not p.exists():
        return "## Idea #4 — Tokenizer perplexity anomaly\n_Not run._\n"
    df = pd.read_csv(p)
    return ("## Idea #4 — Tokenizer perplexity anomaly\n\n"
            "Per-candle reconstruction error from the Kronos tokenizer (no transformer). Bucketed by surprisal quintile. Forward 24h return / abs-return / realized vol per bucket.\n\n"
            f"{fmt_table(df)}\n\n"
            "Interpretation: if the high-surprisal bucket shows materially higher `mean_fwd_vol` or `abs_fwd_ret_pct`, surprisal is a usable regime-shift detector. If `fwd_long_winrate` is far from 50% in extreme buckets, there's a directional signal too.\n")


def section_idea7() -> str:
    p = RESULTS_DIR / "idea7_bollinger_baseline.csv"
    if not p.exists():
        return "## Idea #7 — Bollinger MR baselines\n_Not run._\n"
    df = pd.read_csv(p)
    best = df.groupby(["symbol", "variant"]).head(1).reset_index(drop=True)
    return ("## Idea #7 — Bollinger / z-score mean-reversion baselines\n\n"
            "Classical MR, vol-normalized sizing, and Kronos-gated MR (only fire when Kronos agrees with the MR direction). Tests whether the MR family can produce edge — and whether Kronos as a filter salvages it.\n\n"
            "### Best config per (symbol, variant)\n\n"
            f"{fmt_table(best)}\n\n"
            "### Full sweep\n\n"
            f"{fmt_table(df)}\n")


def section_idea5() -> str:
    p = RESULTS_DIR / "idea5_mtf_coherence.csv"
    if not p.exists():
        return "## Idea #5 — Multi-timeframe coherence\n_Not run._\n"
    df = pd.read_csv(p)
    return ("## Idea #5 — Multi-timeframe coherence (1h × 4h)\n\n"
            "Trade only when 1h and 4h Kronos forecasts agree on direction. Compare to the disagree bucket.\n\n"
            f"{fmt_table(df)}\n\n"
            "Interpretation: if `sharpe` and `win_rate` for `agree` materially exceed `disagree`, MTF gating adds edge. If they're similar, the 4h forecast adds no information vs the 1h alone.\n")


def section_ranking() -> str:
    rank_rows = []

    p1 = RESULTS_DIR / "idea1_direct_strategy.csv"
    if p1.exists():
        df = pd.read_csv(p1)
        best = df.sort_values("sharpe", ascending=False).head(1).iloc[0]
        beat_hodl = bool(best["total_ret_pct"] > best["hodl_total_pct"])
        rank_rows.append({
            "idea": "#1 Direct strategy",
            "best_metric": f"Sharpe={best['sharpe']:.2f} on {best['symbol']} {best['tf']} thr={best['threshold']}",
            "headline_number_pct": float(best["total_ret_pct"]),
            "hodl_pct": float(best["hodl_total_pct"]),
            "beat_hodl": beat_hodl,
        })

    p5 = RESULTS_DIR / "idea5_mtf_coherence.csv"
    if p5.exists():
        df = pd.read_csv(p5)
        agree = df[df["bucket"] == "agree"]
        if len(agree):
            best = agree.sort_values("sharpe", ascending=False).head(1).iloc[0]
            rank_rows.append({
                "idea": "#5 MTF coherence (agree-only)",
                "best_metric": f"Sharpe={best['sharpe']:.2f} on {best['symbol']}",
                "headline_number_pct": float(best["total_ret_pct"]),
                "hodl_pct": None,
                "beat_hodl": None,
            })

    out = "## Ranked findings\n\n"
    if rank_rows:
        out += fmt_table(pd.DataFrame(rank_rows)) + "\n\n"
    else:
        out += "_(no analyses ran)_\n\n"
    return out


def main() -> int:
    now = datetime.now().strftime("%Y-%m-%d %H:%M EDT")
    sections = [
        f"# Kronos edge findings — research report\n\n_Generated {now}._\n",
        section_ranking(),
        section_idea1(),
        section_idea7(),
        section_idea5(),
        section_idea2(),
        section_idea4(),
        section_idea3(),
        "## Conclusion (manual after review)\n\n_TBD._\n",
    ]
    OUT_PATH.write_text("\n".join(sections))
    print(f"Wrote {OUT_PATH}")
    print(f"\n--- Preview ---")
    print(OUT_PATH.read_text()[:3000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
