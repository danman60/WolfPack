import polars as pl, numpy as np
df=pl.scan_parquet("wide/*.parquet").collect().sort(["coin","ts"])
print("Universe screen (2026 YTD): who pays, who is tradeable?")
scr=(df.filter(pl.col("ts")>=pl.datetime(2026,1,1))
       .group_by("coin").agg([
         (pl.col("funding").mean()*8760*100).alias("ann_fund"),
         pl.col("day_ntl_vlm").median().alias("vlm"),
         (pl.col("spread").median()*1e4).alias("sp_bps"),
         pl.col("open_interest").median().alias("oi"), pl.len().alias("hrs")])
       .filter((pl.col("hrs")>2000)&pl.col("ann_fund").is_finite()))
liq=scr.filter((pl.col("vlm")>10_000_000)&(pl.col("sp_bps")<15))
print(f"  {scr.height} coins w/ >2000h in 2026 | {liq.height} pass liquidity(>$10M vlm) + spread(<15bps)")
print("\n  TOP 12 BY 2026 FUNDING, LIQUIDITY-FILTERED:")
print(f"  {'coin':<10}{'ann fund%':>11}{'vlm $M':>9}{'spread bps':>12}")
for r in liq.sort("ann_fund",descending=True).head(12).iter_rows(named=True):
    print(f"  {r['coin']:<10}{r['ann_fund']:>11.2f}{r['vlm']/1e6:>9.1f}{r['sp_bps']:>12.2f}")

# ---- dynamic selection backtest ----
piv_f=df.pivot(on="coin",index="ts",values="funding").sort("ts")
piv_m=df.pivot(on="coin",index="ts",values="mark_px").sort("ts")
piv_o=df.pivot(on="coin",index="ts",values="oracle_px").sort("ts")
piv_v=df.pivot(on="coin",index="ts",values="day_ntl_vlm").sort("ts")
piv_s=df.pivot(on="coin",index="ts",values="spread").sort("ts")
cols=[c for c in piv_f.columns if c!="ts"]; ts=piv_f["ts"].to_numpy()
F=piv_f.drop("ts").to_numpy(); M=piv_m.drop("ts").to_numpy(); O=piv_o.drop("ts").to_numpy()
V=piv_v.drop("ts").to_numpy(); SP=piv_s.drop("ts").to_numpy()
B=(M-O)/np.where(O>0,O,np.nan)
DB=np.vstack([np.zeros((1,len(cols))), -np.diff(B,axis=0)]); DB=np.clip(DB,-0.01,0.01)
TR=np.vstack([np.full((168,len(cols)),np.nan),
              np.array([np.nanmean(F[max(0,i-168):i],axis=0) for i in range(168,len(ts))])])
print("\nDYNAMIC CARRY: hourly, hold top-N by trailing-7d funding among liquid names.")
print("Cost: measured spread charged on every name entering/leaving the book.\n")
print(f"{'N':>3} {'minVlm$M':>9} | {'2025 ann%':>10} {'2026 ann%':>10} {'2026 maxDD%':>12} {'2026 Calmar':>12} {'avg held':>9}")
for N,MINV in [(5,10e6),(10,10e6),(15,10e6),(10,25e6),(20,5e6)]:
    pnl=np.full(len(ts),np.nan); held=np.zeros(len(ts)); prev=set()
    for t in range(168,len(ts)):
        ok=np.isfinite(TR[t])&np.isfinite(F[t])&np.isfinite(DB[t])&(V[t]>MINV)&np.isfinite(SP[t])&(SP[t]<15e-4)&(TR[t]>0)
        idx=np.where(ok)[0]
        if len(idx)==0: pnl[t]=0.0; prev=set(); continue
        sel=idx[np.argsort(TR[t][idx])][-N:]
        r=float(np.mean(F[t,sel]+DB[t,sel]))
        cur=set(sel.tolist()); ch=(cur^prev)
        cost=sum(float(SP[t,j]) if np.isfinite(SP[t,j]) else 5e-4 for j in ch)/max(len(cur),1)
        pnl[t]=r-cost; held[t]=len(cur); prev=cur
    p=pnl[np.isfinite(pnl)]; tt=ts[np.isfinite(pnl)]
    y=pl.Series(tt).dt.year().to_numpy()
    p26=p[y>=2026]; e=np.cumsum(p26); dd=(np.maximum.accumulate(e)-e).max()*100 if len(e) else np.nan
    a26=p26.mean()*8760*100
    print(f"{N:>3} {MINV/1e6:>9.0f} | {p[y==2025].mean()*8760*100:>10.2f} {a26:>10.2f} {dd:>12.2f} {a26/max(dd,1e-9):>12.2f} {held[held>0].mean():>9.1f}")
