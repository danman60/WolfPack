import polars as pl, numpy as np
df = pl.read_parquet("panel.parquet")
print("DELTA-NEUTRAL CARRY SIM: short perp + long spot, hourly funding, basis-aware")
print("assumes 1x notional each leg; return quoted on TOTAL capital (spot+margin=2x notional -> halve)\n")
print(f"{'coin':<7}{'gross ann%':>11}{'basis ann%':>11}{'net ann%':>10}{'on cap%':>9}{'maxDD%':>8}{'worst30d%':>10}{'neg wks%':>9}")
rows=[]
for c, g in df.group_by("coin"):
    c=c[0]; g=g.sort("ts")
    gh = g.group_by_dynamic("ts", every="1h").agg([
        pl.col("funding").mean(), pl.col("mark_px").last(), pl.col("oracle_px").last()])
    gh = gh.drop_nulls()
    f = gh["funding"].to_numpy(); mk = gh["mark_px"].to_numpy(); orc = gh["oracle_px"].to_numpy()
    ok = np.isfinite(f)&np.isfinite(mk)&np.isfinite(orc)&(mk>0)&(orc>0)
    f, mk, orc = f[ok], mk[ok], orc[ok]
    if len(f) < 24*180: continue
    basis = (mk-orc)/orc                      # perp premium
    # short perp + long spot: pnl_hour = funding + (basis_t - basis_{t+1})
    dbasis = -np.diff(basis, prepend=basis[0])
    pnl = f + dbasis                          # per hour, fraction of notional
    hrs = len(pnl)
    gross_ann = f.mean()*8760*100
    basis_ann = dbasis.mean()*8760*100
    net_ann  = pnl.mean()*8760*100
    eq = np.cumsum(pnl)                       # additive on notional
    dd = (np.maximum.accumulate(eq)-eq).max()*100
    w30 = min(eq[i+720]-eq[i] for i in range(0,max(1,len(eq)-720),24))*100 if len(eq)>720 else np.nan
    wk = np.add.reduceat(pnl, np.arange(0,len(pnl),168))
    negw = (wk<0).mean()*100
    rows.append((c, gross_ann, basis_ann, net_ann, net_ann/2, dd, w30, negw))
for r in sorted(rows, key=lambda x:-x[3]):
    print(f"{r[0]:<7}{r[1]:>11.2f}{r[2]:>11.2f}{r[3]:>10.2f}{r[4]:>9.2f}{r[5]:>8.2f}{r[6]:>10.2f}{r[7]:>9.1f}")

print("\nEQUAL-WEIGHT PORTFOLIO (all coins, delta-neutral carry)")
mats=[]
for c, g in df.group_by("coin"):
    c=c[0]; g=g.sort("ts")
    gh=g.group_by_dynamic("ts",every="1h").agg([pl.col("funding").mean(),pl.col("mark_px").last(),pl.col("oracle_px").last()]).drop_nulls()
    if gh.height<24*180: continue
    f=gh["funding"].to_numpy(); mk=gh["mark_px"].to_numpy(); orc=gh["oracle_px"].to_numpy()
    b=(mk-orc)/orc; p=f-np.diff(b,prepend=b[0])
    mats.append(pl.DataFrame({"ts":gh["ts"],c:p}))
port=mats[0]
for m in mats[1:]: port=port.join(m,on="ts",how="full",coalesce=True)
port=port.sort("ts")
vals=port.drop("ts").to_numpy()
pnl=np.nanmean(np.where(np.isfinite(vals),vals,np.nan),axis=1)
pnl=pnl[np.isfinite(pnl)]
eq=np.cumsum(pnl)
n=len(pnl); n_is=int(n*0.7)
print(f"  hours={n}  ann={pnl.mean()*8760*100:.2f}%  IS={pnl[:n_is].mean()*8760*100:.2f}%  OOS={pnl[n_is:].mean()*8760*100:.2f}%")
print(f"  sharpe={pnl.mean()/pnl.std()*np.sqrt(8760):.2f}  maxDD={(np.maximum.accumulate(eq)-eq).max()*100:.2f}%")
wk=np.add.reduceat(pnl,np.arange(0,n,168)); print(f"  weekly: {(wk>0).mean()*100:.1f}% positive, worst week {wk.min()*100:.2f}%")
print(f"  on total capital (2x notional): {pnl.mean()*8760*100/2:.2f}%/yr")
