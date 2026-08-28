import polars as pl, numpy as np
df=pl.scan_parquet("wide/*.parquet").collect().sort(["coin","ts"])
piv=lambda v: df.pivot(on="coin",index="ts",values=v).sort("ts")
pf,pm,po,pv,ps=piv("funding"),piv("mark_px"),piv("oracle_px"),piv("day_ntl_vlm"),piv("spread")
cols=[c for c in pf.columns if c!="ts"]; ts=pf["ts"].to_numpy()
F,M,O,V,SP=[x.drop("ts").to_numpy() for x in (pf,pm,po,pv,ps)]
B=(M-O)/np.where(O>0,O,np.nan)
DBraw=np.vstack([np.zeros((1,len(cols))),-np.diff(B,axis=0)])   # UNCLIPPED - real tail
TR=np.vstack([np.full((168,len(cols)),np.nan),
    np.array([np.nanmean(np.where(np.isfinite(F[max(0,i-168):i]),F[max(0,i-168):i],np.nan),axis=0) for i in range(168,len(ts))])])
# tail-safety screen: exclude names whose worst observed hourly basis move < -3% (kills LIT, PUMP)
worst={}
for j,c in enumerate(cols):
    d=DBraw[:,j]; d=d[np.isfinite(d)]
    worst[j]=d.min() if len(d)>1000 else -1.0
BAN={j for j,w in worst.items() if w<-0.03}
print(f"tail screen bans {len(BAN)} of {len(cols)} names (worst hourly basis < -3%)")
print("  banned incl:", [cols[j] for j in list(BAN)[:8] if cols[j] in ("LIT","PUMP","FARTCOIN","TIA","SEI")])
def run(N=5,RB=168,ban=True):
    pnl=np.full(len(ts),np.nan); prev={}
    for t in range(168,len(ts)):
        if (t-168)%RB==0 or not prev:
            ok=np.isfinite(TR[t])&(V[t]>10e6)&np.isfinite(SP[t])&(SP[t]<15e-4)&(TR[t]>0)
            if ban:
                for j in BAN: ok[j]=False
            sc=np.where(ok,TR[t],-np.inf); sc=np.where(np.isfinite(sc),sc,-np.inf)
            idx=[int(j) for j in np.argsort(sc)[-N:] if sc[j]>0]
            ch=set(idx)^set(prev); c=sum(float(SP[t,j]) if np.isfinite(SP[t,j]) else 5e-4 for j in ch)
            prev={j:1.0 for j in idx}
        else: c=0.0
        if not prev: pnl[t]=0.0; continue
        js=list(prev)
        pnl[t]=float(np.nanmean(F[t,js]+np.clip(DBraw[t,js],-0.05,0.05)))-c/max(len(prev),1)
    m=np.isfinite(pnl); return pnl[m],ts[m]
p,tt=run(); y=pl.Series(tt).dt.year().to_numpy()
print("\n=== DEPLOYABLE SPEC: tail-screened one-sided dynamic carry, top-5, weekly rebalance ===")
print(f"{'leverage':>9}{'2026 ret%':>11}{'2025 ret%':>11}{'2026 maxDD%':>13}{'worst hr%':>11}{'worst day%':>12}")
for L in [1,2,3]:
    for lab,msk in [("",None)]: pass
    q26=p[y>=2026]*L; q25=p[y==2025]*L; e=np.cumsum(q26)
    dd=(np.maximum.accumulate(e)-e).max()*100
    wd=np.add.reduceat(p*L,np.arange(0,len(p),24)).min()*100
    print(f"{L:>9}{q26.mean()*8760*100:>11.2f}{q25.mean()*8760*100:>11.2f}{dd:>13.2f}{(p*L).min()*100:>11.2f}{wd:>12.2f}")
print("\nfull-period (2025-01 -> 2026-06) at L=3:")
q=p*3; e=np.cumsum(q); print(f"  ann={q.mean()*8760*100:.2f}%  maxDD={(np.maximum.accumulate(e)-e).max()*100:.2f}%  Calmar={q.mean()*8760*100/((np.maximum.accumulate(e)-e).max()*100):.1f}")
mo=np.add.reduceat(q,np.arange(0,len(q),730)); print(f"  monthly Sharpe={mo.mean()/mo.std()*np.sqrt(12):.2f}  neg months={(mo<0).sum()}/{len(mo)}  worst month={mo.min()*100:.2f}%")
