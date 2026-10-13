#!/usr/bin/env python3
"""Independent sign-region solution for arbitrary-weight self-financing allocations."""
import argparse
import importlib.util
import itertools
import json
from pathlib import Path
import subprocess
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('common',Path(__file__).with_name('rotation-advice-numerics.py'))
common=importlib.util.module_from_spec(spec);spec.loader.exec_module(common)
LOADER=common.NODE[:common.NODE.index('const api=load')]


def solve_equity(initial, weights, fee, spread):
    # Eight possible buy/sell sign regions; solve each linear conservation identity directly.
    capital=sum(initial);c_buy=(1+spread)*(1+fee)-1;c_sell=1-(1-spread)*(1-fee)
    answers=[]
    for buy in itertools.product((False,True),repeat=3):
        a=sum((c_buy if b else -c_sell)*w for b,w in zip(buy,weights[1:]))
        b=sum((-c_buy if side else c_sell)*x for side,x in zip(buy,initial[1:]))
        equity=(capital-b)/(1+a)
        if all((w*equity>=x-1e-8) if side else (w*equity<=x+1e-8) for side,w,x in zip(buy,weights[1:],initial[1:])):answers.append(equity)
    assert answers and max(answers)-min(answers)<1e-7
    return answers[0]


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    weights=[[1,0,0,0],[0,1,0,0],[.25,.25,.25,.25],[.2,.15,.45,.2],[.1,.4,.25,.25],[0,.33333333,.33333333,.33333334],[.4,.2,.3,.1]]
    code=LOADER+r'''
const api=load('app/src/lib/rotation/allocation-engine.ts'),engine=load('app/src/lib/rotation/engine.ts'),assert=require('node:assert/strict');
const input=JSON.parse(fs.readFileSync(0,'utf8')),now=new Date(),assets=['CAD','BTC','ETH','LINK'];
const market={id:crypto.randomUUID(),source:'Explicit synthetic accounting book',fetchedAt:now.toISOString(),expiresAt:new Date(+now+30000).toISOString(),books:{}};
for(const [asset,price] of Object.entries({BTC:100,ETH:10,LINK:1}))market.books[asset]={asset,bid:(price*.999).toFixed(8),ask:(price*1.001).toFixed(8),bids:[{price:(price*.999).toFixed(8),quantity:'1000000'}],asks:[{price:(price*1.001).toFixed(8),quantity:'1000000'}],minimum:'0.00000001',increment:'0.00000001'};
const portfolio=engine.createPortfolio({name:'Independent weights fixture',opening:{CAD:'4000',BTC:'20',ETH:'300',LINK:'1000'},cadence:'weekly',feeBps:20},market,now);
const frozen=JSON.stringify(portfolio),returns={BTC:.03,ETH:-.02,LINK:.06};
const results=input.weights.map(w=>api.estimateAllocation(portfolio,market,Object.fromEntries(assets.map((a,i)=>[a,w[i]])),returns,10));
assert.equal(JSON.stringify(portfolio),frozen);assert.equal(results[6].legs.length,0);assert.deepEqual(results[6].plannedBalances,portfolio.balances);assert.equal(results[6].feesCad,0);assert.equal(results[6].expectedAdvantageCad,0);
const repeat=api.estimateAllocation(portfolio,market,Object.fromEntries(assets.map((a,i)=>[a,input.weights[3][i]])),returns,10);
for(const key of ['plannedBalances','expectedProfitCad','expectedAdvantageCad','feesCad','slippageCad','spreadDepthCad'])assert.deepEqual(repeat[key],results[3][key]);
assert.throws(()=>api.estimateAllocation(portfolio,market,{CAD:1,BTC:1,ETH:0,LINK:0},returns,10));
const shallow=structuredClone(market);for(const b of Object.values(shallow.books)){b.bids[0].quantity='0.00001';b.asks[0].quantity='0.00001';}
assert.equal(api.estimateAllocation(portfolio,shallow,{CAD:1,BTC:0,ETH:0,LINK:0},returns,10).feasible,false);
console.log(JSON.stringify({results,returns}));
'''
    data=json.loads(subprocess.run(['node','-e',code],input=json.dumps({'weights':weights}),text=True,capture_output=True,cwd=ROOT,check=True).stdout)
    initial=np.array([4000,2000,3000,1000]);marks=np.array([1,100,10,1]);ret=np.array([0,.03,-.02,.06]);assets=['CAD','BTC','ETH','LINK'];maxerr=0
    for w,result in zip(weights,data['results']):
        assert result['feasible'],result['reason']
        expected=solve_equity(initial,w,.002,.001)
        balances=np.array([float(result['plannedBalances'][a]) for a in assets]);marked=balances*marks;equity=marked.sum()
        err=abs(equity-expected);maxerr=max(maxerr,err);assert err<.0001,(w,equity,expected)
        assert np.max(np.abs(marked-np.array(w)*expected))<.0001
        fees=sum(float(fill['feeCad']) for leg in result['legs'] for fill in leg['fills'])
        turnover=sum(float(fill['grossCad']) for leg in result['legs'] for fill in leg['fills'])
        assert abs(fees-result['feesCad'])<1e-7 and abs(turnover-result['turnoverCad'])<1e-7
        assert abs(10000-equity-fees-result['spreadDepthCad'])<1e-7
        terminal=float(marked@(1+ret))-turnover*.001
        hold=float(initial@(1+ret))
        assert abs(result['expectedEndingValueCad']-terminal)<1e-7
        assert abs(result['expectedProfitCad']-(terminal-10000))<1e-7
        assert abs(result['expectedAdvantageCad']-(terminal-hold))<1e-7
        # Independent sequential trade accounting using each actual fill.
        units=np.array([4000,20,300,1000],dtype=float)
        for leg in result['legs']:
            for fill in leg['fills']:
                i=assets.index(fill['asset']);quantity=float(fill['quantity']);gross=float(fill['grossCad']);fee=float(fill['feeCad'])
                sign=1 if fill['side']=='buy' else -1
                units[i]+=sign*quantity;units[0]-=sign*gross+fee
        assert np.max(np.abs(units-balances))<1e-7
    report={'status':'PASS','arbitrary_weight_cases':len(weights),'maximum_equity_error_vs_independent_linear_solution':maxerr,'checks':['all eight trade-sign regions solved independently','actual fill cash and units reconciled','matched unchanged-unit baseline','fees/spread/slippage counted once','deterministic repeated browser/server pure calculation','source portfolio unchanged','invalid weights rejected','insufficient depth infeasible'],'scope':'Synthetic accounting controls only; no profitable forecasting claim.'}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))


if __name__=='__main__':main()
