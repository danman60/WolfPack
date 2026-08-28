import polars as pl, numpy as np
df=pl.scan_parquet("wide/*.parquet").collect().sort(["coin","ts"])
TRADE=["BTC","ETH","SOL","HYPE","PAXG","XRP","DOGE","LINK","SUI","ZEC","FARTCOIN","PUMP","LIT","kPEPE"]
print("UNCLIPPED hourly basis-move tail, per tradeable name (this is the REAL leverage constraint)")
print(f"{'coin':<10}{'n hrs':>8}{'worst 1h%':>11}{'p0.1%':>9}{'p1%':>8}{'std bps':>9}{'safe L @ -10% stop':>20}")
safe=[]
for c in TRADE:
    g=df.filter(pl.col("coin")==c).sort("ts")
    if g.height<2000: continue
    mk=g["mark_px"].to_numpy(); orc=g["oracle_px"].to_numpy()
    ok=np.isfinite(mk)&np.isfinite(orc)&(orc>0)&(mk>0)
    b=((mk-orc)/orc)[ok]
    db=-np.diff(b)                      # adverse move for a short-perp/long-spot book
    db=db[np.isfinite(db)]
    if len(db)<1000: continue
    worst=db.min()*100; p01=np.percentile(db,0.1)*100; p1=np.percentile(db,1)*100
    L=10/abs(worst) if worst<0 else np.inf
    safe.append((c,L))
    print(f"{c:<10}{len(db):>8}{worst:>11.3f}{p01:>9.3f}{p1:>8.3f}{db.std()*1e4:>9.2f}{min(L,50):>20.1f}")
print("\n  'safe L' = leverage at which the WORST observed single hour costs 10% of capital.")
mn=min(s[1] for s in safe); nm=[s[0] for s in safe if s[1]==mn][0]
print(f"  binding name: {nm} at L={mn:.1f}")
maj=[s for s in safe if s[0] in ("BTC","ETH","SOL","HYPE","PAXG")]
print(f"  MAJORS-ONLY book (BTC/ETH/SOL/HYPE/PAXG) binding L = {min(s[1] for s in maj):.1f}  <- these all have HL spot")
