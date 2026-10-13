import {ASSETS,CRYPTO_ASSETS,type Cadence,type HistoryDataset,type MarketSnapshot,type Portfolio} from './contract';
import {approveShift,createPortfolio,previewShift} from './engine';
import {fitForecast,forecastHorizon} from './forecast-advice';
import {allocationValue,estimateAllocation,rankAllocations,validateWeights} from './allocation-engine';
import type {AllocationWeights} from './allocation-contract';
const DAY=86400000;
export type AllocationReplayCycle={signalAt:string;fillAt:string;dueAt:string;weights:AllocationWeights;preserveUnits:boolean;trainingEnd:string;forecastReturns:Record<(typeof CRYPTO_ASSETS)[number],number>;startingBalances:Portfolio['balances'];plannedBalances:Portfolio['balances'];predictedProfitCad:number;predictedAdvantageCad:number;actualProfitCad:number;actualAdvantageCad:number;hypotheticalProfitCad:number;profitErrorCad:number;feesCad:number};
/** Continuous past-only replay of the same fit -> choose -> freeze -> execute -> check-in cycle.
 * Historical depth is unknown: explicit symmetric adverse-price model, never claimed historical Ndax fills.
 */
export function replayAllocationCycles(dataset:HistoryDataset,config:{cadence:Cadence;feeBps:number;slippageBps:number;riskPercent:number;initialWeights:AllocationWeights;capitalCad:number}):{cycles:AllocationReplayCycle[];curve:{at:string;valueCad:number}[];finalPortfolio:Portfolio;notes:string[]}{
 validateWeights(config.initialWeights);if(!Number.isFinite(config.capitalCad)||config.capitalCad<=0||config.capitalCad>1e9)throw new Error('Replay capital must be positive and at most CAD1billion.');
 const rows=dataset.points,times=rows.map(row=>Date.parse(row.date+'T00:00:00Z')+DAY);const index=new Map(times.map((time,i)=>[time,i]));
 const market=(i:number,adverse:number):MarketSnapshot=>{
  const at=new Date(times[i]+1).toISOString();
  return{id:crypto.randomUUID(),source:'Historical reference closes with modeled adverse fills; depth not observed',fetchedAt:at,expiresAt:new Date(times[i]+30001).toISOString(),books:Object.fromEntries(CRYPTO_ASSETS.map(asset=>{
   const price=rows[i].prices[asset],half=Math.max(1e-8,price*adverse/10000);
   return[asset,{asset,bid:(price-half).toFixed(8),ask:(price+half).toFixed(8),bids:[{price:(price-half).toFixed(8),quantity:'1000000000'}],asks:[{price:(price+half).toFixed(8),quantity:'1000000000'}],minimum:'0.00000001',increment:'0.00000001'}];})) as MarketSnapshot['books']};
 };
 let start=-1;
 for(let i=460;i<rows.length;i++){try{fitForecast({...dataset,points:rows.slice(0,i+1)},config.cadence,new Date(times[i]));start=i;break;}catch{/* shared warmup advances before any outcomes are viewed */}}
 if(start<0)throw new Error('Insufficient mature history for chronological replay.');
 const initialMarket=market(start,config.slippageBps);
 const opening=Object.fromEntries(ASSETS.map(a=>[a,(config.capitalCad*config.initialWeights[a]/(a==='CAD'?1:rows[start].prices[a])).toFixed(8)])) as Portfolio['balances'];
 let portfolio=createPortfolio({name:'Retrospective continuous allocation replay',opening,cadence:config.cadence,feeBps:config.feeBps},initialMarket,new Date(initialMarket.fetchedAt));
 const frozen:Omit<AllocationReplayCycle,'actualProfitCad'|'actualAdvantageCad'|'hypotheticalProfitCad'|'profitErrorCad'>[]=[];
 const curve:{at:string;valueCad:number}[]=[];let nextReview=times[start];
 for(let i=start;i<rows.length;i++){
  if(times[i]>=nextReview){
   const dueTime=Date.parse(forecastHorizon(new Date(times[i]).toISOString(),config.cadence))+DAY,fill=i+1;
   if(fill<rows.length&&index.has(dueTime)){
    const prefix={...dataset,points:rows.slice(0,i+1)},fit=fitForecast(prefix,config.cadence,new Date(times[i]));
    const decisionMarket=market(i,config.slippageBps),choice=rankAllocations(portfolio,decisionMarket,fit.forecastReturns,config.riskPercent,0),weights=choice.weights,preserveUnits=choice.decision==='hold';
    const estimate=estimateAllocation(portfolio,decisionMarket,weights,fit.forecastReturns,0,preserveUnits);
    if(!estimate.feasible)throw new Error(estimate.reason||'Historical target cannot be modeled.');
    const startingBalances={...portfolio.balances},fillMarket=market(fill,config.slippageBps),execution=estimateAllocation(portfolio,fillMarket,weights,fit.forecastReturns,0,preserveUnits);
    if(!execution.feasible)throw new Error(execution.reason||'Historical fill cannot be modeled.');
    for(const leg of execution.legs){const preview=previewShift(portfolio,fillMarket,leg.from,leg.to,leg.amount,new Date(fillMarket.fetchedAt));portfolio=approveShift(portfolio,preview,new Date(fillMarket.fetchedAt));}
    frozen.push({signalAt:fit.signalAt,fillAt:fillMarket.fetchedAt,dueAt:new Date(dueTime).toISOString(),weights,preserveUnits,trainingEnd:fit.latestTrainingEnd,forecastReturns:fit.forecastReturns,startingBalances,plannedBalances:estimate.plannedBalances,predictedProfitCad:estimate.expectedProfitCad,predictedAdvantageCad:estimate.expectedAdvantageCad,feesCad:execution.feesCad});
   }
   nextReview=Date.parse(forecastHorizon(new Date(times[i]).toISOString(),config.cadence));
  }
  // Events may contain the already computed next-close fill; only value units available by this close.
  const balances=[...portfolio.events].reverse().find(event=>Date.parse(event.at)<=times[i])?.balances??opening;
  curve.push({at:new Date(times[i]).toISOString(),valueCad:allocationValue(balances,{CAD:1,...rows[i].prices})});
 }
 const cycles=frozen.map(cycle=>{
  const due=Date.parse(cycle.dueAt),at=index.get(due)!,signal=index.get(Date.parse(cycle.signalAt))!;
  const marks={CAD:1,...rows[at].prices},initial=allocationValue(cycle.startingBalances,{CAD:1,...rows[signal].prices});
  const actual=[...portfolio.events].reverse().find(event=>Date.parse(event.at)<=due)?.balances??opening;
  const actualProfit=allocationValue(actual,marks)-initial,hold=allocationValue(cycle.startingBalances,marks)-initial;
  return{...cycle,actualProfitCad:actualProfit,actualAdvantageCad:actualProfit-hold,hypotheticalProfitCad:allocationValue(cycle.plannedBalances,marks)-initial,profitErrorCad:actualProfit-cycle.predictedProfitCad};
 });
 return{cycles,curve,finalPortfolio:portfolio,notes:['All model fitting/scaling uses only completed prefix prices and strictly matured labels.','Frozen forecasts precede next-close modeled execution; wealth and units continue between reviews.','Historical sentiment is excluded because no point-in-time news archive was supplied.','Reference-close adverse fills assume sufficient depth; they are not observed executable exchange books. No retrospective score gates current advice.']};
}

export function allocationReplayFingerprintSource():string{return replayAllocationCycles.toString();}
