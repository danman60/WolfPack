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
def run(N,MINV,RB,HYST,two_sided):
    pnl=np.full(len(ts),np.nan); prev={}; turn=0
    for t in range(168,len(ts)):
        if (t-168)%RB==0 or not prev:
            ok=np.isfinite(TR[t])&(V[t]>MINV)&np.isfinite(SP[t])&(SP[t]<15e-4)
            score=np.abs(TR[t]) if two_sided else np.where(TR[t]>0,TR[t],-np.inf)
            score=np.where(ok&np.isfinite(score),score,-np.inf)
            idx=np.argsort(score)[-N:]; idx=[int(j) for j in idx if score[j]>0]
            new={}
            for j in idx:
                sgn=np.sign(TR[t,j]) if two_sided else 1.0
                new[j]=sgn
            if prev:   # hysteresis: keep incumbent unless challenger beats it by HYST
                keep={j:s for j,s in prev.items() if np.isfinite(score[j]) and score[j]>0}
                for j,s in new.items():
                    if j not in keep and len(keep)<N: keep[j]=s
                if len(keep)>N:
                    keep=dict(sorted(keep.items(),key=lambda kv:-score[kv[0]])[:N])
                cand={j:s for j,s in new.items() if j not in keep}
                for j,s in cand.items():
                    worst=min(keep,key=lambda k:score[k])
                    if score[j]>score[worst]*(1+HYST): del keep[worst]; keep[j]=s
                new=keep
            ch=set(new)^set(prev); turn+=len(ch)
            c=sum(float(SP[t,j]) if np.isfinite(SP[t,j]) else 5e-4 for j in ch)
            prev=new
        else: c=0.0
        if not prev: pnl[t]=0.0; continue
        js=list(prev); sg=np.array([prev[j] for j in js])
        r=float(np.nanmean(sg*(F[t,js]+DB[t,js])))
        pnl[t]=r-c/max(len(prev),1)
    p=pnl[np.isfinite(pnl)]; tt=ts[np.isfinite(pnl)]
    y=pl.Series(tt).dt.year().to_numpy()
    out={}
    for lab,mask in [("2025",y==2025),("2026",y>=2026),("all",np.ones(len(y),bool))]:
        q=p[mask]; e=np.cumsum(q)
        out[lab]=(q.mean()*8760*100,(np.maximum.accumulate(e)-e).max()*100 if len(e) else np.nan)
    return out,turn/((len(ts)-168)/8760)
print("TWO-SIDED DYNAMIC CARRY (short perp if funding>0, long perp if funding<0; spot hedge both ways)")
print(f"{'N':>3}{'rebal':>7}{'hyst':>6}{'2sided':>8} | {'2025 ann%':>10}{'2026 ann%':>10}{'2026 DD%':>9}{'2026 Cal':>9}{'turn/yr':>8}")
for N,RB,H,TS in [(5,168,0.20,True),(8,168,0.20,True),(8,168,0.20,False),(8,720,0.20,True),(5,720,0.30,True),(12,720,0.20,True)]:
    o,tn=run(N,10e6,RB,H,TS)
    lab={168:"weekly",720:"monthly"}[RB]
    print(f"{N:>3}{lab:>7}{H:>6.2f}{str(TS):>8} | {o['2025'][0]:>10.2f}{o['2026'][0]:>10.2f}{o['2026'][1]:>9.2f}{o['2026'][0]/max(o['2026'][1],1e-9):>9.2f}{tn:>8.1f}")
