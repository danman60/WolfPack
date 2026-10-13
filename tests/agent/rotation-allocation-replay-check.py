#!/usr/bin/env python3
"""Bounded real-data replay and independent event/forecast accounting, never a parameter search."""
import argparse,datetime as dt,hashlib,importlib.util,json,subprocess
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('common',Path(__file__).with_name('rotation-advice-numerics.py'));common=importlib.util.module_from_spec(spec);spec.loader.exec_module(common)
LOADER=common.NODE[:common.NODE.index('const api=load')]
def main():
 p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();rows=json.loads(a.data.read_text())['rows'][-719:];points=[{k:r[k] for k in ['date','prices']} for r in rows]
 code=LOADER+r'''
const api=load('app/src/lib/rotation/allocation-replay.ts'),input=JSON.parse(fs.readFileSync(0,'utf8'));const config={cadence:'weekly',feeBps:20,slippageBps:10,riskPercent:60,initialWeights:{CAD:.4,BTC:.2,ETH:.2,LINK:.2},capitalCad:10000};
const full=api.replayAllocationCycles({points:input},config),prefix=api.replayAllocationCycles({points:input.slice(0,650)},config),mutated=structuredClone(input);for(let i=650;i<mutated.length;i++)for(const a of ['BTC','ETH','LINK'])mutated[i].prices[a]*=1.5;
const mutation=api.replayAllocationCycles({points:mutated},config);console.log(JSON.stringify({full,prefix,mutation}));'''
 data=json.loads(subprocess.run(['node','-e',code],input=json.dumps(points),text=True,capture_output=True,cwd=ROOT,check=True).stdout)
 price={((dt.date.fromisoformat(r['date'])+dt.timedelta(days=1)).isoformat()+'T00:00:00.000Z'):{'CAD':1,**r['prices']} for r in points};assets=['CAD','BTC','ETH','LINK'];full=data['full'];events=full['finalPortfolio']['events']
 value=lambda units,marks:sum(float(units[x])*marks[x] for x in assets)
 for c in full['cycles']:
  assert c['trainingEnd']<c['signalAt']<c['fillAt']<c['dueAt']
  before=c['startingBalances'];start=value(before,price[c['signalAt']]);at=[e for e in events if e['at']<=c['dueAt']][-1]['balances'];actual=value(at,price[c['dueAt']])-start;hold=value(before,price[c['dueAt']])-start
  assert abs(c['actualProfitCad']-actual)<1e-7 and abs(c['actualAdvantageCad']-(actual-hold))<1e-7
  i=next(i for i,r in enumerate(points) if (dt.date.fromisoformat(r['date'])+dt.timedelta(days=1)).isoformat()==c['signalAt'][:10]);fit,_,_=common.independently_fit(points[:i+1],'weekly');expected=(fit['1']+fit['10'])/2
  assert np.allclose([c['forecastReturns'][x] for x in assets[1:]],expected,atol=1e-11)
 for prefix in [data['prefix'],data['mutation']]:
  cutoff=data['prefix']['curve'][-1]['at'];eligible=[c for c in full['cycles'] if c['dueAt']<=cutoff];compared=[c for c in prefix['cycles'] if c['dueAt']<=cutoff];assert eligible==compared,'Future changed past decision or frozen outcome'
  # Final prefix can omit an incomplete future cycle; compare wealth only through latest mature common cycle.
  end=eligible[-1]['dueAt'];assert [x for x in full['curve'] if x['at']<=end]==[x for x in prefix['curve'] if x['at']<=end]
 for row in full['curve']:
  prior=[e for e in events if e['at']<=row['at']];units=prior[-1]['balances'] if prior else full['cycles'][0]['startingBalances'];assert abs(value(units,price[row['at']])-row['valueCad'])<1e-7
 initial_units=full['cycles'][0]['startingBalances'];hold_curve=[value(initial_units,price[r['at']]) for r in full['curve']];strategy_curve=[r['valueCad'] for r in full['curve']];drawdown=lambda curve:float(np.max(1-np.array(curve)/np.maximum.accumulate(curve)));report={'configuration':{'cadence':'weekly','cryptoBudgetPercent':60,'feeBps':20,'adversePriceBps':10,'initialWeights':{'CAD':.4,'BTC':.2,'ETH':.2,'LINK':.2}},'firstCompletedClose':full['curve'][0]['at'],'lastCompletedClose':full['curve'][-1]['at'],'continuousHoldEndingCad':hold_curve[-1],'strategyMaximumDrawdown':drawdown(strategy_curve),'holdMaximumDrawdown':drawdown(hold_curve),'noInterestCashEndingCad':strategy_curve[0],'continuousAdvantageCad':strategy_curve[-1]-hold_curve[-1],'status':'PASS','cycles':len(full['cycles']),'days':len(full['curve']),'independentForecastFits':len(full['cycles']),'prefixAndFuturePerturbation':'PASS','eventWealthAndMatchedBaseline':'PASS','startingValueCad':full['curve'][0]['valueCad'],'endingValueCad':full['curve'][-1]['valueCad'],'feesCad':full['finalPortfolio']['feesCad'],'sourceSha256':hashlib.sha256(a.data.read_bytes()).hexdigest(),'scope':'One declared weekly60% risk scenario, genuine most-recent719 Coinbase/BoC closes. Modeled10bps adverse fills and20bps fee; no historical order-book depth or sentiment claim; not an optimization.'}
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');a.output.with_name('replay-artifact.json').write_text(json.dumps(full));print(json.dumps(report))
if __name__=='__main__':main()
