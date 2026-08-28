import lz4.frame, polars as pl, glob, io, sys, os
SCH={"time":pl.Utf8,"coin":pl.Utf8,"funding":pl.Float64,"open_interest":pl.Float64,"prev_day_px":pl.Float64,
     "day_ntl_vlm":pl.Float64,"premium":pl.Float64,"oracle_px":pl.Float64,"mark_px":pl.Float64,
     "mid_px":pl.Float64,"impact_bid_px":pl.Float64,"impact_ask_px":pl.Float64}
files=sorted(glob.glob("raw/*.csv.lz4"))
files=[f for f in files if os.path.basename(f)[:4] in ("2025","2026")]   # recent regime only
print(f"{len(files)} days in 2025-2026")
os.makedirs("wide",exist_ok=True); [os.remove(p) for p in glob.glob("wide/*.parquet")]
buf=[]; part=0; tot=0
for i,f in enumerate(files,1):
    try:
        b=lz4.frame.open(f,'rb').read()
        if len(b)<1000: continue
        d=pl.read_csv(io.BytesIO(b),schema_overrides=SCH,ignore_errors=True)
        d=d.with_columns(pl.col("time").str.to_datetime("%Y-%m-%dT%H:%M:%SZ").alias("ts")).drop("time")
        # aggregate to HOURLY inside the loop -> 60x smaller, all 232 coins fit
        d=(d.sort("ts").group_by_dynamic("ts",every="1h",group_by="coin")
             .agg([pl.col("funding").mean(),pl.col("mark_px").last(),pl.col("oracle_px").last(),
                   pl.col("open_interest").last(),pl.col("day_ntl_vlm").last(),
                   ((pl.col("impact_ask_px")-pl.col("impact_bid_px"))/pl.col("mid_px")).median().alias("spread")]))
        buf.append(d)
    except Exception as e: print("SKIP",f,e,file=sys.stderr)
    if len(buf)>=90 or i==len(files):
        if buf:
            x=pl.concat(buf,how="vertical_relaxed"); x.write_parquet(f"wide/w{part:03d}.parquet")
            tot+=x.height; part+=1; buf=[]
        print(f"  {i}/{len(files)} rows={tot}",flush=True)
lf=pl.scan_parquet("wide/*.parquet")
s=lf.select([pl.col("ts").min().alias("lo"),pl.col("ts").max().alias("hi"),pl.col("coin").n_unique().alias("n")]).collect()
print("SPAN",s["lo"][0],"->",s["hi"][0],"COINS",s["n"][0],"ROWS",tot)
