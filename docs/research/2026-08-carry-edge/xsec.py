import polars as pl, numpy as np
lf=pl.scan_parquet("parts/*.parquet")
COINS=["BTC","ETH","SOL","DOGE","LINK","AVAX","XRP","LTC","ARB","OP","APT","INJ","SUI","SEI","WLD","kPEPE"]
SPREAD={"BTC":1.65,"ETH":1.98,"SOL":2.56,"DOGE":3.4,"LINK":3.32,"AVAX":2.98,"XRP":3.0,"LTC":3.36,
        "ARB":3.5,"OP":3.66,"APT":3.5,"INJ":3.5,"SUI":3.5,"SEI":4.56,"WLD":4.0,"kPEPE":4.5}
D={}
for c in COINS:
    g=lf.filter(pl.col("coin")==c).select(["ts","funding","mark_px","oracle_px"]).sort("ts").collect()
    if g.height<20000: continue
    gh=g.group_by_dynamic("ts",every="1h").agg([pl.col("funding").mean(),pl.col("mark_px").last(),pl.col("oracle_px").last()]).drop_nulls().sort("ts")
    f=gh["funding"].to_numpy(); mk=gh["mark_px"].to_numpy(); orc=gh["oracle_px"].to_numpy()
    ok=np.isfinite(f)&np.isfinite(mk)&np.isfinite(orc)&(mk>0)&(orc>0)
    D[c]=pl.DataFrame({"ts":gh["ts"].to_numpy()[ok],"f_"+c:f[ok],"px_"+c:orc[ok]})
m=None
for c,d in D.items(): m=d if m is None else m.join(d,on="ts",how="full",coalesce=True)
m=m.sort("ts"); ts=m["ts"].to_numpy()
CS=[c for c in D]
F=np.column_stack([m["f_"+c].to_numpy() for c in CS])
P=np.column_stack([m["px_"+c].to_numpy() for c in CS])
R=np.vstack([np.full((1,len(CS)),np.nan), P[1:]/P[:-1]-1])     # hourly spot return
TR=np.column_stack([pl.Series(F[:,i]).rolling_mean(168).to_numpy() for i in range(len(CS))])
print("CROSS-SECTIONAL FUNDING CARRY — short top-K funding perps, long bottom-K perps.")
print("Market-neutral via perp legs only: NO spot leg, NO second venue, 1x capital.\n")
print(f"{'K':>3} | {'full ann%':>10} {'maxDD%':>7} {'Calmar':>7} {'moSharpe':>9} | {'2025 ann%':>10} {'2026 ann%':>10}")
for K in [2,3,4,5]:
    pnl=np.full(len(ts),np.nan)
    for t in range(1,len(ts)):
        v=TR[t-1]; ok=np.isfinite(v)&np.isfinite(R[t])&np.isfinite(F[t])
        if ok.sum()<2*K+2: continue
        idx=np.where(ok)[0]; order=idx[np.argsort(v[idx])]
        lo,hi=order[:K],order[-K:]
        # short high-funding perp: +funding, -price return | long low-funding perp: -funding, +price return
        pnl[t]=(F[t,hi].mean()-R[t,hi].mean())+(R[t,lo].mean()-F[t,lo].mean())
    p=pnl[np.isfinite(pnl)]; tt=ts[np.isfinite(pnl)]
    # rebalance cost: assume daily reconstitution, 2K legs, avg spread
    avg_sp=np.mean(list(SPREAD.values()))*1e-4
    p=p-(2*K*avg_sp*0.5)/24/ (2*K) *0   # legs already averaged; charge daily turnover below
    p=p-(avg_sp*2)/24                    # ~2 spreads/day of turnover amortized hourly
    eq=np.cumsum(p); ann=p.mean()*8760*100
    mdd=(np.maximum.accumulate(eq)-eq).max()*100
    mo=np.add.reduceat(p,np.arange(0,len(p),730))
    y=pl.Series(tt).dt.year().to_numpy()
    print(f"{K:>3} | {ann:>10.2f} {mdd:>7.2f} {ann/max(mdd,1e-9):>7.2f} {mo.mean()/mo.std()*np.sqrt(12):>9.2f} | {p[y==2025].mean()*8760*100:>10.2f} {p[y>=2026].mean()*8760*100:>10.2f}")
