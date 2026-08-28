import lz4.frame, polars as pl, glob, io, sys
TARGET=["BTC","ETH","SOL","AVAX","LINK","DOGE","ARB","OP","BNB","XRP","LTC","APT","SUI","HYPE","WLD","INJ","SEI","TIA","kPEPE"]
SCH={"time":pl.Utf8,"coin":pl.Utf8,"funding":pl.Float64,"open_interest":pl.Float64,"prev_day_px":pl.Float64,
     "day_ntl_vlm":pl.Float64,"premium":pl.Float64,"oracle_px":pl.Float64,"mark_px":pl.Float64,
     "mid_px":pl.Float64,"impact_bid_px":pl.Float64,"impact_ask_px":pl.Float64}
files=sorted(glob.glob("raw/*.csv.lz4")); buf=[]; part=0; tot=0
for i,f in enumerate(files,1):
    try:
        b=lz4.frame.open(f,'rb').read()
        if len(b)<1000: continue
        d=pl.read_csv(io.BytesIO(b),schema_overrides=SCH,ignore_errors=True).filter(pl.col("coin").is_in(TARGET))
        if d.height: buf.append(d)
    except Exception as e: print("SKIP",f,e,file=sys.stderr)
    if len(buf)>=60 or i==len(files):
        if buf:
            x=pl.concat(buf,how="vertical_relaxed")
            x=x.with_columns(pl.col("time").str.to_datetime("%Y-%m-%dT%H:%M:%SZ").alias("ts")).drop("time")
            x.write_parquet(f"parts/p{part:04d}.parquet"); tot+=x.height; part+=1; buf=[]
        print(f"  {i}/{len(files)} parts={part} rows={tot}",flush=True)
print("TOTAL ROWS",tot)
lf=pl.scan_parquet("parts/*.parquet")
s=lf.select([pl.col("ts").min().alias("lo"),pl.col("ts").max().alias("hi")]).collect()
print("SPAN",s["lo"][0],"->",s["hi"][0])
