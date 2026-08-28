import polars as pl, numpy as np
df = pl.read_parquet("panel.parquet")
R = []   # (name, n, mean_bps, t, note)

def tstat(x):
    x = x[~np.isnan(x)]
    if len(x) < 30: return np.nan, np.nan, len(x)
    return float(x.mean()), float(x.mean()/(x.std(ddof=1)/np.sqrt(len(x)))), len(x)

print("="*78); print("MEASURED EXECUTION COST (this replaces the 10bps guess)"); print("="*78)
cost = {}
for c, g in df.group_by("coin"):
    c = c[0]; g = g.sort("ts")
    hs = ((g["impact_ask_px"] - g["impact_bid_px"]) / g["mid_px"]).drop_nans()
    hs = hs.filter((hs > 0) & (hs < 0.05))
    if len(hs) == 0: continue
    cost[c] = float(hs.median())          # full spread, fraction
    print(f"  {c:<6} spread {cost[c]*1e4:7.2f} bps   round-trip {cost[c]*1e4:7.2f} bps (cross once each way = 1x spread)")

print(); print("="*78); print("H1 — FUNDING CARRY (delta-neutral short perp)"); print("="*78)
print(f"{'coin':<6}{'ann.funding%':>14}{'IS%':>9}{'OOS%':>9}{'t':>8}{'%hrs>0':>9}")
h1 = []
for c, g in df.group_by("coin"):
    c = c[0]; g = g.sort("ts")
    # funding col is the HOURLY rate; sample hourly to avoid 60x duplication
    gh = g.group_by_dynamic("ts", every="1h").agg(pl.col("funding").mean())
    f = gh["funding"].to_numpy(); f = f[~np.isnan(f)]
    if len(f) < 24*90: continue
    n_is = int(len(f)*0.7)
    ann = f.mean()*8760*100
    ann_is = f[:n_is].mean()*8760*100; ann_oos = f[n_is:].mean()*8760*100
    m,t,n = tstat(f)
    pos = (f>0).mean()*100
    h1.append((c, ann, ann_is, ann_oos, t, pos))
    R.append((f"H1_carry_{c}", n, ann, t, ""))
for c,ann,a_is,a_oos,t,pos in sorted(h1, key=lambda x:-x[1]):
    print(f"{c:<6}{ann:>14.2f}{a_is:>9.2f}{a_oos:>9.2f}{t:>8.1f}{pos:>9.1f}")

print(); print("="*78); print("H2 — OI-DELTA x PRICE-DELTA QUADRANTS (h=60m fixed)"); print("="*78)
H = 60
quad_all = {k: [] for k in ["newlong","shortcover","newshort","longliq"]}
for c, g in df.group_by("coin"):
    c = c[0]; g = g.sort("ts")
    oi = g["open_interest"].to_numpy(); px = g["mid_px"].to_numpy()
    if len(px) < 100000: continue
    doi = np.concatenate([[np.nan]*H, oi[H:]/oi[:-H]-1])
    dpx = np.concatenate([[np.nan]*H, px[H:]/px[:-H]-1])
    fwd = np.concatenate([px[H:]/px[:-H]-1, [np.nan]*H])
    c_rt = cost.get(c, 0.001)
    lab = np.full(len(px), "", dtype=object)
    lab[(doi>0)&(dpx>0)] = "newlong"; lab[(doi<0)&(dpx>0)] = "shortcover"
    lab[(doi>0)&(dpx<0)] = "newshort"; lab[(doi<0)&(dpx<0)] = "longliq"
    for k in quad_all:
        m = (lab==k) & ~np.isnan(fwd)
        if m.sum() > 100: quad_all[k].append((c, fwd[m], c_rt))
print(f"{'quadrant':<12}{'n':>10}{'gross bps':>12}{'net bps':>10}{'t':>8}")
for k, rows in quad_all.items():
    allr = np.concatenate([r[1] for r in rows]); rt = np.mean([r[2] for r in rows])
    m,t,n = tstat(allr*1e4)
    net = m - rt*1e4
    print(f"{k:<12}{n:>10}{m:>12.2f}{net:>10.2f}{t:>8.2f}")
    R.append((f"H2_{k}", n, net, t, ""))

print(); print("="*78); print("H3 — PREMIUM Z-SCORE (h=60m fixed, z over 1440m)"); print("="*78)
print(f"{'bucket':<14}{'n':>10}{'gross bps':>12}{'net bps':>10}{'t':>8}")
buckets = {"z<-2":[], "z>2":[]}
for c, g in df.group_by("coin"):
    c = c[0]; g = g.sort("ts")
    pr = g["premium"].to_numpy(); px = g["mid_px"].to_numpy()
    if len(px) < 100000: continue
    s = pl.Series(pr)
    mu = s.rolling_mean(1440).to_numpy(); sd = s.rolling_std(1440).to_numpy()
    z = (pr-mu)/sd
    fwd = np.concatenate([px[H:]/px[:-H]-1, [np.nan]*H])
    c_rt = cost.get(c, 0.001)
    for k, m in [("z<-2", z<-2), ("z>2", z>2)]:
        mm = m & ~np.isnan(fwd) & ~np.isnan(z)
        if mm.sum() > 100: buckets[k].append((fwd[mm], c_rt))
for k, rows in buckets.items():
    allr = np.concatenate([r[0] for r in rows]); rt = np.mean([r[1] for r in rows])
    m,t,n = tstat(allr*1e4)
    sign = -1 if k=="z>2" else 1     # pre-registered: high premium -> short
    net = sign*m - rt*1e4
    print(f"{k:<14}{n:>10}{m:>12.2f}{net:>10.2f}{t:>8.2f}")
    R.append((f"H3_{k}", n, net, t, ""))

print(); print("="*78); print(f"MULTIPLE COMPARISONS — {len(R)} tests run, BH-FDR q=0.10"); print("="*78)
from math import erfc, sqrt
ps = []
for name,n,eff,t,_ in R:
    p = erfc(abs(t)/sqrt(2)) if not np.isnan(t) else 1.0
    ps.append((p, name, eff, t))
ps.sort()
m = len(ps); surv = []
for i,(p,name,eff,t) in enumerate(ps, 1):
    if p <= i/m*0.10: surv.append((name,p,eff,t))
print(f"survivors: {len(surv)}/{m}")
for name,p,eff,t in surv[:15]:
    print(f"  {name:<22} p={p:.2e}  net_effect={eff:>9.2f}  t={t:>7.1f}")
