import polars as pl, numpy as np
lf=pl.scan_parquet("parts/*.parquet")
def load(c):
    g=(lf.filter(pl.col("coin")==c).select(["ts","funding","mark_px","oracle_px"])
        .sort("ts").collect())
    gh=g.group_by_dynamic("ts",every="1h").agg([pl.col("funding").mean(),pl.col("mark_px").last(),pl.col("oracle_px").last()]).drop_nulls().sort("ts")
    f=gh["funding"].to_numpy(); mk=gh["mark_px"].to_numpy(); orc=gh["oracle_px"].to_numpy()
    ok=np.isfinite(f)&np.isfinite(mk)&np.isfinite(orc)&(mk>0)&(orc>0)
    return gh["ts"].to_numpy()[ok], f[ok], ((mk-orc)/orc)[ok]
print("="*84); print("DECISIVE REGIME TEST — 3.1 YEARS INCL. 2024-25 BEAR"); print("="*84)
res={}
for c in ["BTC","ETH","SOL","DOGE","LINK","AVAX","XRP","LTC"]:
    try: ts,f,b=load(c)
    except Exception as e: print(c,"ERR",e); continue
    if len(f)<8760: continue
    p=f+np.clip(-np.diff(b,prepend=b[0]),-0.01,0.01)
    res[c]=(ts,p)
    eq=np.cumsum(p); n=len(p); ann=p.mean()*8760*100
    mdd=(np.maximum.accumulate(eq)-eq).max()*100
    mo=np.add.reduceat(p,np.arange(0,n,730))
    n_is=int(n*0.7)
    q=pl.DataFrame({"ts":ts,"p":p}).with_columns(pl.col("ts").dt.truncate("1q").alias("q"))
    rows=[(d,v*8760*100) for d,v in q.group_by("q").agg(pl.col("p").mean()).sort("q").iter_rows()]
    print(f"\n{c}  {str(ts[0])[:10]} -> {str(ts[-1])[:10]}  ({n/8760:.2f}y)")
    print(f"  ann={ann:6.2f}%  maxDD={mdd:5.2f}%  Calmar={ann/max(mdd,1e-9):5.2f}  monthlySharpe={mo.mean()/mo.std()*np.sqrt(12):5.2f}  negMo={(mo<0).sum()}/{len(mo)}")
    print(f"  IS(first70%)={p[:n_is].mean()*8760*100:6.2f}%   OOS(last30%)={p[n_is:].mean()*8760*100:6.2f}%")
    print(f"  negative quarters: {sum(1 for _,v in rows if v<0)}/{len(rows)}")
    print("  "+" ".join(f"{d.year%100}Q{(d.month-1)//3+1}:{v:.0f}" for d,v in rows))

print("\n"+"="*84); print("8-MAJOR EQUAL-WEIGHT PORTFOLIO — FULL HISTORY"); print("="*84)
common=None
for c,(ts,p) in res.items():
    d=pl.DataFrame({"ts":ts,c:p}); common=d if common is None else common.join(d,on="ts",how="full",coalesce=True)
common=common.sort("ts"); V=common.drop("ts").to_numpy(); cnt=np.isfinite(V).sum(axis=1)
pnl=np.where(cnt>0,np.nansum(np.where(np.isfinite(V),V,0),axis=1)/np.maximum(cnt,1),np.nan)
keep=np.isfinite(pnl)&(cnt>=4); pnl=pnl[keep]; ts=common["ts"].to_numpy()[keep]
eq=np.cumsum(pnl); n=len(pnl); ann=pnl.mean()*8760*100
mdd=(np.maximum.accumulate(eq)-eq).max()*100
mo=np.add.reduceat(pnl,np.arange(0,n,730)); yr=np.add.reduceat(pnl,np.arange(0,n,8760))
print(f"  {str(ts[0])[:10]} -> {str(ts[-1])[:10]}  hours={n} ({n/8760:.2f}y)")
print(f"  ann={ann:.2f}%  maxDD={mdd:.2f}%  Calmar={ann/max(mdd,1e-9):.2f}  monthlySharpe={mo.mean()/mo.std()*np.sqrt(12):.2f}")
print(f"  negative months {(mo<0).sum()}/{len(mo)}   worst month {mo.min()*100:.2f}%   best {mo.max()*100:.2f}%")
print(f"  per-year: "+"  ".join(f"{v*100:.1f}%" for v in yr))
print(f"  ON TOTAL CAPITAL (2x notional): {ann/2:.2f}%/yr, maxDD {mdd/2:.2f}%")
q=pl.DataFrame({"ts":ts,"p":pnl}).with_columns(pl.col("ts").dt.truncate("1q").alias("q"))
rows=[(d,v*8760*100) for d,v in q.group_by("q").agg(pl.col("p").mean()).sort("q").iter_rows()]
print(f"  negative quarters {sum(1 for _,v in rows if v<0)}/{len(rows)}")
print("  "+" ".join(f"{d.year%100}Q{(d.month-1)//3+1}:{v:.0f}" for d,v in rows))
