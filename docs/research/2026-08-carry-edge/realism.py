import polars as pl, numpy as np
df=pl.scan_parquet("wide/*.parquet").collect().sort(["coin","ts"])
piv=lambda v: df.pivot(on="coin",index="ts",values=v).sort("ts")
pf,pm,po,pv,ps=piv("funding"),piv("mark_px"),piv("oracle_px"),piv("day_ntl_vlm"),piv("spread")
cols=[c for c in pf.columns if c!="ts"]; ts=pf["ts"].to_numpy()
F,M,O,V,SP=[x.drop("ts").to_numpy() for x in (pf,pm,po,pv,ps)]
B=(M-O)/np.where(O>0,O,np.nan)
DB=np.clip(np.vstack([np.zeros((1,len(cols))),-np.diff(B,axis=0)]),-0.01,0.01)
TR=np.vstack([np.full((168,len(cols)),np.nan),
              np.array([np.nanmean(np.where(np.isfinite(F[max(0,i-168):i]),F[max(0,i-168):i],np.nan),axis=0) for i in range(168,len(ts))])])
MAJORS={c for c in ["BTC","ETH","SOL","XRP","DOGE","LINK","AVAX","LTC","BNB","SUI","HYPE","PAXG","ZEC"] if c in cols}
midx={cols.index(c) for c in MAJORS}
def run(N,RB,borrow_ann,short_spot_majors_only,two_sided):
    hb=borrow_ann/8760
    pnl=np.full(len(ts),np.nan); prev={}
    for t in range(168,len(ts)):
        if (t-168)%RB==0 or not prev:
            ok=np.isfinite(TR[t])&(V[t]>10e6)&np.isfinite(SP[t])&(SP[t]<15e-4)
            sc=np.where(ok,np.abs(TR[t]) if two_sided else np.where(TR[t]>0,TR[t],-np.inf),-np.inf)
            sc=np.where(np.isfinite(sc),sc,-np.inf)
            if two_sided and short_spot_majors_only:   # negative-funding leg needs SHORT SPOT
                bad=np.array([ (TR[t,j]<0) and (j not in midx) for j in range(len(cols))])
                sc=np.where(bad,-np.inf,sc)
            idx=[int(j) for j in np.argsort(sc)[-N:] if sc[j]>0]
            new={j:(np.sign(TR[t,j]) if two_sided else 1.0) for j in idx}
            ch=set(new)^set(prev)
            c=sum(float(SP[t,j]) if np.isfinite(SP[t,j]) else 5e-4 for j in ch); prev=new
        else: c=0.0
        if not prev: pnl[t]=0.0; continue
        js=list(prev); sg=np.array([prev[j] for j in js])
        gross=sg*(F[t,js]+DB[t,js])
        carry_cost=np.where(sg<0, hb, 0.0)          # long perp => SHORT SPOT => pay borrow
        pnl[t]=float(np.nanmean(gross-carry_cost))-c/max(len(prev),1)
    p=pnl[np.isfinite(pnl)]; tt=ts[np.isfinite(pnl)]; y=pl.Series(tt).dt.year().to_numpy()
    r={}
    for lab,m in [("2025",y==2025),("2026",y>=2026)]:
        q=p[m]; e=np.cumsum(q); r[lab]=(q.mean()*8760*100,(np.maximum.accumulate(e)-e).max()*100 if len(e) else np.nan)
    return r
print("EXECUTION-REALISM SWEEP — borrow cost on the short-spot leg; restrict that leg to names with real spot")
print(f"{'config':<46}{'2025 ann%':>11}{'2026 ann%':>11}{'2026 DD%':>10}")
cfgs=[
 ("one-sided N=5 wk (ALWAYS executable)",       dict(N=5,RB=168,borrow_ann=0.0,short_spot_majors_only=False,two_sided=False)),
 ("one-sided N=8 wk",                            dict(N=8,RB=168,borrow_ann=0.0,short_spot_majors_only=False,two_sided=False)),
 ("two-sided N=5 wk, borrow 0%  (fantasy)",      dict(N=5,RB=168,borrow_ann=0.0,short_spot_majors_only=False,two_sided=True)),
 ("two-sided N=5 wk, borrow 10%",                dict(N=5,RB=168,borrow_ann=0.10,short_spot_majors_only=False,two_sided=True)),
 ("two-sided N=5 wk, borrow 25%",                dict(N=5,RB=168,borrow_ann=0.25,short_spot_majors_only=False,two_sided=True)),
 ("two-sided N=5 wk, borrow 25% + majors-only",  dict(N=5,RB=168,borrow_ann=0.25,short_spot_majors_only=True,two_sided=True)),
 ("two-sided N=8 wk, borrow 25% + majors-only",  dict(N=8,RB=168,borrow_ann=0.25,short_spot_majors_only=True,two_sided=True)),
]
for lab,kw in cfgs:
    r=run(**kw); print(f"{lab:<46}{r['2025'][0]:>11.2f}{r['2026'][0]:>11.2f}{r['2026'][1]:>10.2f}")
