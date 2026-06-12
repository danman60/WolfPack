"""Turtle breadth study — step 3: cross-sectional stats + portfolio simulation.

RESEARCH ONLY.

- Cross-sectional: fraction of universe with positive expectancy at p30/p40 (base costs).
- Common period: ONE fixed p for all symbols = cross-sectional best of {20,30,40,55}
  by (fraction positive, then median expectancy). No per-symbol cherry-picking.
- Portfolios (built from per-symbol BacktestEngine equity curves, 4h bars):
    honest    = ALL universe symbols (winners + losers — no ex-ante knowledge)
    selected  = only symbols with positive in-sample expectancy at common p
                (OVERFIT-FLAGGED: selection uses in-sample results)
  Equal-risk: weight_i ∝ 1 / annualized vol of symbol's underlying 4h returns,
  renormalized each bar over symbols whose data/warmup is active.
- Leverage sweep 1x..4x on the honest portfolio + block-bootstrap MC (5000 sims,
  1-week blocks) for the worst-tail max-DD per leverage.
"""

import json
import math
from pathlib import Path

import numpy as np

OUT_DIR = Path(__file__).parent
PERIODS = [20, 30, 40, 55]
BARS_PER_YEAR = 6 * 365  # 2190 4h bars
ANN = math.sqrt(BARS_PER_YEAR)
MC_SIMS = 5000
MC_BLOCK = 42  # 1 week of 4h bars
SEED = 42


def main():
    results = json.loads((OUT_DIR / "breadth_results.json").read_text())
    syms = list(results["symbols"].keys())
    npz = np.load(OUT_DIR / "equity_curves.npz")

    # ---------- cross-sectional ----------
    xs = {}
    for p in PERIODS:
        exps = {s: results["symbols"][s]["cells"][f"p{p}_base"]["expectancy_bps_of_equity"]
                for s in syms}
        exps_stress = {s: results["symbols"][s]["cells"][f"p{p}_stress"]["expectancy_bps_of_equity"]
                       for s in syms}
        pos = [s for s, e in exps.items() if e > 0]
        pos_stress = [s for s, e in exps_stress.items() if e > 0]
        xs[f"p{p}"] = {
            "n_positive": len(pos), "n_total": len(syms),
            "frac_positive": round(len(pos) / len(syms), 3),
            "median_expectancy_bps": round(float(np.median(list(exps.values()))), 1),
            "n_positive_stress": len(pos_stress),
            "frac_positive_stress": round(len(pos_stress) / len(syms), 3),
            "positive_symbols": sorted(pos),
        }
        print(f"p{p}: {len(pos)}/{len(syms)} positive ({len(pos)/len(syms)*100:.0f}%) "
              f"median exp {np.median(list(exps.values())):+.1f}bps | stress: {len(pos_stress)}/{len(syms)}")

    # common p: best fraction positive, tiebreak median expectancy
    common_p = max(PERIODS, key=lambda p: (xs[f"p{p}"]["frac_positive"],
                                           xs[f"p{p}"]["median_expectancy_bps"]))
    print(f"common period: p{common_p}")

    # ---------- per-symbol bar returns (strategy equity curves) ----------
    # union timeline
    all_t = sorted(set(int(t) for s in syms for t in npz[f"{s}__t"]))
    t_index = {t: i for i, t in enumerate(all_t)}
    T = len(all_t)

    # strategy bar returns matrix [sym, T]; nan = inactive (pre-listing/warmup)
    R = np.full((len(syms), T), np.nan)
    vol = {}
    for k, s in enumerate(syms):
        ts = npz[f"{s}__t"]
        eq = npz[f"{s}__p{common_p}"]
        # underlying vol from candles (close returns)
        candles = json.loads((OUT_DIR / "candles" / f"{s}.json").read_text())
        closes = np.array([c[4] for c in candles])
        u_ret = np.diff(closes) / closes[:-1]
        vol[s] = float(np.std(u_ret)) * ANN  # annualized underlying vol
        idx = np.array([t_index[int(t)] for t in ts])
        valid = ~np.isnan(eq)
        first = np.argmax(valid)
        e = eq[first:]
        r = np.zeros(len(e))
        r[1:] = np.diff(e) / e[:-1]
        R[k, idx[first:]] = r

    w_raw = np.array([1.0 / vol[s] for s in syms])

    def portfolio_returns(members_mask):
        """Equal-risk weighted mean of member strategy bar returns, per-bar renorm."""
        active = (~np.isnan(R)) & members_mask[:, None]
        W = np.where(active, w_raw[:, None], 0.0)
        wsum = W.sum(axis=0)
        port = np.where(wsum > 0, np.nansum(np.where(active, R, 0.0) * W, axis=0)
                        / np.where(wsum > 0, wsum, 1.0), 0.0)
        return port

    def curve_stats(port_ret, lev=1.0):
        r = port_ret * lev
        eq = np.cumprod(1.0 + r)
        total = eq[-1] - 1.0
        years = T / BARS_PER_YEAR
        cagr = (eq[-1] ** (1 / years) - 1) if eq[-1] > 0 else -1.0
        mu, sd = float(np.mean(r)), float(np.std(r, ddof=1))
        sharpe = mu / sd * ANN if sd > 0 else 0.0
        peak = np.maximum.accumulate(eq)
        dd = (peak - eq) / peak
        max_dd = float(np.max(dd))
        # longest flat: longest run of bars below prior peak
        below = dd > 1e-9
        longest = cur = 0
        for b in below:
            cur = cur + 1 if b else 0
            longest = max(longest, cur)
        return {"total_return_pct": round(total * 100, 1),
                "cagr_pct": round(cagr * 100, 2),
                "sharpe_ann": round(sharpe, 2),
                "max_dd_pct": round(max_dd * 100, 2),
                "longest_flat_days": round(longest / 6, 0),
                "final_equity_mult": round(float(eq[-1]), 3)}, eq

    def mc_dd(port_ret, lev):
        rng = np.random.default_rng(SEED)
        r = port_ret * lev
        n = len(r)
        dds = np.empty(MC_SIMS)
        ruined = 0
        for i in range(MC_SIMS):
            seq = []
            while len(seq) < n:
                s0 = rng.integers(0, n - MC_BLOCK + 1)
                seq.extend(r[s0:s0 + MC_BLOCK])
            seq = np.array(seq[:n])
            eq = np.cumprod(1.0 + seq)
            peak = np.maximum.accumulate(eq)
            dds[i] = np.max((peak - eq) / peak)
            if np.min(eq) <= 0:
                ruined += 1
        return {"mc_median_dd_pct": round(float(np.median(dds)) * 100, 1),
                "mc_p95_dd_pct": round(float(np.percentile(dds, 95)) * 100, 1),
                "mc_prob_dd_gt_30pct": round(float(np.mean(dds > 0.30)) * 100, 1),
                "mc_ruin_pct": round(ruined / MC_SIMS * 100, 2)}

    exps = {s: results["symbols"][s]["cells"][f"p{common_p}_base"]["expectancy_bps_of_equity"]
            for s in syms}
    sel_mask = np.array([exps[s] > 0 for s in syms])
    all_mask = np.ones(len(syms), dtype=bool)

    out = {"common_p": common_p, "cross_sectional": xs,
           "weights_ann_vol": {s: round(vol[s], 3) for s in syms},
           "window": {"bars": T,
                      "start_utc": _d(all_t[0]), "end_utc": _d(all_t[-1]),
                      "years": round(T / BARS_PER_YEAR, 2)},
           "portfolios": {}}

    for name, mask in (("honest_all_universe", all_mask), ("selected_winners_only", sel_mask)):
        port = portfolio_returns(mask)
        stats, eq = curve_stats(port)
        out["portfolios"][name] = {"n_symbols": int(mask.sum()),
                                   "members": [s for s, m in zip(syms, mask) if m],
                                   "lev_1x": stats}
        print(f"\n{name} (n={mask.sum()}): ret {stats['total_return_pct']:+.1f}% "
              f"cagr {stats['cagr_pct']:+.2f}%/yr sharpe {stats['sharpe_ann']} "
              f"dd {stats['max_dd_pct']}% flat {stats['longest_flat_days']:.0f}d")
        if name == "honest_all_universe":
            lev_table = {}
            for lev in (1, 2, 3, 4):
                s, _ = curve_stats(port, lev)
                s.update(mc_dd(port, lev))
                lev_table[f"{lev}x"] = s
                print(f"  {lev}x: ret {s['total_return_pct']:+.1f}% cagr {s['cagr_pct']:+.2f}%/yr "
                      f"sharpe {s['sharpe_ann']} dd {s['max_dd_pct']}% "
                      f"MC p95dd {s['mc_p95_dd_pct']}% P(dd>30%) {s['mc_prob_dd_gt_30pct']}%")
            out["portfolios"][name]["leverage_sweep"] = lev_table
            # save honest portfolio equity curve
            np.savez_compressed(OUT_DIR / "portfolio_curve.npz",
                                t=np.array(all_t), ret_1x=port)

    (OUT_DIR / "portfolio_results.json").write_text(json.dumps(out, indent=1))
    print("\nwrote portfolio_results.json + portfolio_curve.npz")


def _d(ms):
    import time
    return time.strftime("%Y-%m-%d", time.gmtime(ms / 1000))


if __name__ == "__main__":
    main()
