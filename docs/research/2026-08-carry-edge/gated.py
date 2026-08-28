import polars as pl, numpy as np
lf=pl.scan_parquet("parts/*.parquet")
def load(c):
    g=lf.filter(pl.col("coin")==c).select(["ts","funding","mark_px","oracle_px"]).sort("ts").collect()
    gh=g.group_by_dynamic("ts",every="1h").agg([pl.col("funding").mean(),pl.col("mark_px").last(),pl.col("oracle_px").last()]).drop_nulls().sort("ts")
    f=gh["funding"].to_numpy(); mk=gh["mark_px"].to_numpy(); orc=gh["oracle_px"].to_numpy()
    ok=np.isfinite(f)&np.isfinite(mk)&np.isfinite(orc)&(mk>0)&(orc>0)
    return gh["ts"].to_numpy()[ok],f[ok],((mk-orc)/orc)[ok]
COINS=["BTC","ETH","SOL","DOGE","LINK","AVAX","XRP","LTC"]
S={c:load(c) for c in COINS}
SPREAD={"BTC":1.65e-4,"ETH":1.98e-4,"SOL":2.56e-4,"DOGE":3.4e-4,"LINK":3.32e-4,"AVAX":2.98e-4,"XRP":3.0e-4,"LTC":3.36e-4}
print("GATED CARRY: only hold when trailing 7d funding (annualized) > T. Cost charged on every on/off flip.")
print(f"{'gate':>7} | {'full 2.87y ann%':>15} {'maxDD%':>7} {'Calmar':>7} | {'2025+ ann%':>11} {'2026 ann%':>10} {'time on%':>9} {'flips/yr':>9}")
for T in [0.0,0.05,0.10,0.15,0.20]:
    per=[]
    for c in COINS:
        ts,f,b=S[c]
        tr=pl.Series(f).rolling_mean(168).to_numpy()*8760      # trailing 7d ann funding
        on=np.nan_to_num(tr,nan=-1)>T
        p=(f+np.clip(-np.diff(b,prepend=b[0]),-0.01,0.01))*on
        flips=np.abs(np.diff(on.astype(int),prepend=0))
        p=p-flips*SPREAD[c]                                     # pay spread on each entry/exit
        per.append(pl.DataFrame({"ts":ts,c:p}))
    m=per[0]
    for x in per[1:]: m=m.join(x,on="ts",how="full",coalesce=True)
    m=m.sort("ts"); V=m.drop("ts").to_numpy(); cnt=np.isfinite(V).sum(axis=1)
    pnl=np.where(cnt>0,np.nansum(np.where(np.isfinite(V),V,0),axis=1)/np.maximum(cnt,1),np.nan)
    k=np.isfinite(pnl)&(cnt>=4); pnl=pnl[k]; ts=m["ts"].to_numpy()[k]
    eq=np.cumsum(pnl); ann=pnl.mean()*8760*100
    mdd=(np.maximum.accumulate(eq)-eq).max()*100
    y=pl.Series(ts).dt.year().to_numpy()
    a25=pnl[y>=2025].mean()*8760*100; a26=pnl[y>=2026].mean()*8760*100
    onpct=np.mean([ (np.nan_to_num(pl.Series(S[c][1]).rolling_mean(168).to_numpy(),nan=-1)>T).mean() for c in COINS])*100
    fl=np.mean([np.abs(np.diff((np.nan_to_num(pl.Series(S[c][1]).rolling_mean(168).to_numpy(),nan=-1)>T).astype(int))).sum()/(len(S[c][1])/8760) for c in COINS])
    print(f"{T*100:>6.0f}% | {ann:>15.2f} {mdd:>7.2f} {ann/max(mdd,1e-9):>7.2f} | {a25:>11.2f} {a26:>10.2f} {onpct:>9.1f} {fl:>9.1f}")

print("\nPER-COIN RECENT REGIME (2025-01 onward, ungated) — who still pays?")
print(f"{'coin':<6}{'2025 ann%':>11}{'2026 ann%':>11}{'2026 maxDD%':>13}")
for c in COINS:
    ts,f,b=S[c]; p=f+np.clip(-np.diff(b,prepend=b[0]),-0.01,0.01)
    y=pl.Series(ts).dt.year().to_numpy()
    e=np.cumsum(p[y>=2026])
    dd=(np.maximum.accumulate(e)-e).max()*100 if len(e) else np.nan
    print(f"{c:<6}{p[y==2025].mean()*8760*100:>11.2f}{p[y>=2026].mean()*8760*100:>11.2f}{dd:>13.2f}")
