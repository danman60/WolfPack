#!/usr/bin/env python3
"""Independent fixed-date cash-flow/check-in controls, no HTTP or database substitution."""
import argparse,importlib.util,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];s=importlib.util.spec_from_file_location('common',Path(__file__).with_name('rotation-advice-numerics.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 code=m.NODE[:m.NODE.index('const api=load')]+r'''
const {computeAllocationOutcome:outcome}=load('app/src/lib/rotation/allocation-outcome.ts'),assert=require('node:assert/strict');
const {projectionExpired}=load('app/src/lib/rotation/allocation-engine.ts');const boundary=Date.parse('2026-01-08T00:00:00.000Z');assert.equal(projectionExpired('2026-01-08T00:00:00.000Z',boundary-1),false);assert.equal(projectionExpired('2026-01-08T00:00:00.000Z',boundary),true);assert.equal(projectionExpired('2026-01-08T00:00:00.000Z',boundary+1),true);assert.equal(projectionExpired('invalid',boundary),true);
const units=(CAD,BTC)=>({CAD:String(CAD),BTC:String(BTC),ETH:'0',LINK:'0'}),start=units(1000,10),due='2026-01-08T00:00:00.000Z';
const projection={id:'numerical-control',dueAt:due,startingBalances:start,startingPortfolio:{events:[{kind:'opening',at:'2026-01-01T00:00:00.000Z',balances:start}]},estimate:{startingValueCad:2000,expectedProfitCad:150,expectedAdvantageCad:50,plannedBalances:units(1000,9),slippageCad:2}};
const portfolio={events:[...projection.startingPortfolio.events,{kind:'deposit',at:'2026-01-02T00:00:00.000Z',balances:units(1200,10)},{kind:'shift',at:'2026-01-03T00:00:00.000Z',balances:units(1419.56,8)},{kind:'withdrawal',at:'2026-01-04T00:00:00.000Z',balances:units(1319.56,8)},{kind:'shift',at:'2026-01-08T00:00:00.001Z',balances:units(2000,0)}]},point={date:'2026-01-07',prices:{BTC:120,ETH:20,LINK:2}};
const batch={status:'completed',orders:[{status:'filled',filledAt:'2026-01-03T00:00:00.000Z'},{status:'filled',filledAt:'2026-01-08T00:00:00.001Z'}]},frozen=JSON.stringify(projection),result=outcome(projection,portfolio,point,batch,new Date(due));
assert.equal(JSON.stringify(projection),frozen);assert.throws(()=>outcome(projection,portfolio,{...point,date:'2026-01-08'},batch,new Date(due)));assert.throws(()=>outcome(projection,portfolio,point,batch,new Date('2026-01-07')));
const noTrade=outcome(projection,{events:[...projection.startingPortfolio.events,{kind:'deposit',at:'2026-01-02T00:00:00Z',balances:units(1200,10)}]},point,null,new Date(due));
const full=outcome(projection,portfolio,point,{status:'completed',orders:[batch.orders[0]]},new Date(due));
console.log(JSON.stringify({result,noTrade,full}));'''
 x=json.loads(subprocess.run(['node','-e',code],cwd=ROOT,text=True,capture_output=True,check=True).stdout);r=x['result']
 for key,expected in {'actualProfitCad':179.56,'holdProfitCad':200,'actualAdvantageCad':-20.44,'netCashFlowsCad':100,'profitErrorCad':29.56,'advantageErrorCad':-70.44,'hypotheticalProfitCad':78,'hypotheticalAdvantageCad':-122}.items():assert abs(r[key]-expected)<1e-8,(key,r[key],expected)
 assert r['execution']=='partly-executed' and x['full']['execution']=='fully-executed';assert x['noTrade']['execution']=='not-executed' and x['noTrade']['actualAdvantageCad']==0 and x['noTrade']['actualProfitCad']==200
 report={'status':'PASS','checks':['deposit and withdrawal excluded from profit in both paths','one millisecond after due trade excluded','unchanged units produce zero advantage despite deposit','partial/full/not executed classified separately','hypothetical target distinct from actual wealth','original frozen forecast unchanged','wrong day and not-due outcomes rejected','Apply expiry rejects due instant, later and invalid dates; permits due minus1ms'],'scope':'Explicit synthetic arithmetic controls, not historical market returns.'};a.output.write_text(json.dumps(report,indent=2));print(json.dumps(report))
if __name__=='__main__':main()
