#!/usr/bin/env python3
"""Independent fixed-precision reconciliation of the example against real captured books."""
import argparse,importlib.util,json,subprocess
from decimal import Decimal,ROUND_DOWN
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('common',Path(__file__).with_name('rotation-advice-numerics.py'));common=importlib.util.module_from_spec(spec);spec.loader.exec_module(common)
LOADER=common.NODE[:common.NODE.index('const api=load')]
p=argparse.ArgumentParser();p.add_argument('--market',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args();raw=json.loads(a.market.read_text());market=raw.get('market',raw)
code=LOADER+"const input=JSON.parse(fs.readFileSync(0,'utf8'));const api=load('app/src/lib/rotation/demo-example.ts');console.log(JSON.stringify(api.createExamplePortfolio(input,new Date(input.fetchedAt))));"
portfolio=json.loads(subprocess.run(['node','-e',code],input=json.dumps(market),text=True,capture_output=True,cwd=ROOT,check=True).stdout)
scale=Decimal(100000000);tick=Decimal('.00000001');cash=Decimal(10000);values={}
for asset,budget in [('BTC',4000),('ETH',2000),('LINK',2000)]:
 book=market['books'][asset];mark=((Decimal(book['bid'])+Decimal(book['ask']))/2).quantize(tick,rounding=ROUND_DOWN);inc=Decimal(book['increment']);quantity=(Decimal(budget)/mark/inc).to_integral_value(rounding=ROUND_DOWN)*inc;actual=Decimal(portfolio['balances'][asset]);assert actual==quantity and actual>0;value=(actual*mark).quantize(tick,rounding=ROUND_DOWN);cash-=value;values[asset]=str(value)
assert Decimal(portfolio['balances']['CAD'])==cash and cash>0;assert cash+sum(map(Decimal,values.values()))==10000;assert portfolio['initialValueCad']=='10000';assert portfolio['cadence']=='weekly' and portfolio['feeBps']==20
report={'status':'PASS','sourceMarketId':market['id'],'initialValueCad':portfolio['initialValueCad'],'opening':portfolio['balances'],'markedCryptoCad':values,'cashResidualCad':str(cash),'checks':['Genuine captured public book prices','Independent Decimal budget/increment calculation matches all units','8-decimal marked values plus residual cash equal exactly CAD10000','Four positive holdings','Weekly review and20bps fee defaults'],'scope':'Opening accounting only. Illustrative allocation; not profitability evidence.'};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2));print(json.dumps(report))
