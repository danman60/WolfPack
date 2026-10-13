import type {DailyPoint,Portfolio} from './contract';
import type {AllocationBatch,AllocationOutcome,AllocationProjection} from './allocation-contract';
import {allocationValue} from './allocation-engine';
export function computeAllocationOutcome(projection:AllocationProjection,portfolio:Portfolio,point:DailyPoint,batch:AllocationBatch|null,observedAt=new Date()):AllocationOutcome {
 const expectedDate=new Date(Date.parse(projection.dueAt)-86400000).toISOString().slice(0,10);
 if(point.date!==expectedDate||observedAt.getTime()<Date.parse(projection.dueAt))throw new Error('Exact matured check-in close required.');
 const marks={CAD:1,...point.prices},due=Date.parse(projection.dueAt);let actual={...projection.startingBalances},cash=0;let previous={...projection.startingBalances};
 for(const event of portfolio.events.slice(projection.startingPortfolio.events.length)){
  if(Date.parse(event.at)>due)break;
  if(event.kind==='deposit'||event.kind==='withdrawal')cash+=Number(event.balances.CAD)-Number(previous.CAD);
  actual={...event.balances};previous=event.balances;
 }
 const start=projection.estimate.startingValueCad,hold=allocationValue(projection.startingBalances,marks)+cash-start-cash;
 const actualProfit=allocationValue(actual,marks)-start-cash;
 const hypothetical=allocationValue(projection.estimate.plannedBalances,marks)-projection.estimate.slippageCad-start;
 const fills=batch?.orders.filter(o=>o.status==='filled'&&o.filledAt&&Date.parse(o.filledAt)<=due).length??0;
 const appliedHold=projection.preserveUnits===true&&batch?.status==='completed'&&batch.orders.length===0&&Date.parse(batch.createdAt)<=due;
 const execution=appliedHold?'fully-executed':fills===0?'not-executed':batch?.status==='completed'&&batch.orders.every(o=>o.status==='filled'&&o.filledAt&&Date.parse(o.filledAt)<=due)?'fully-executed':'partly-executed';
 const outcome:AllocationOutcome={id:crypto.randomUUID(),projectionId:projection.id,observedAt:observedAt.toISOString(),dueAt:projection.dueAt,priceAt:projection.dueAt,execution,
 predictedProfitCad:projection.estimate.expectedProfitCad,predictedAdvantageCad:projection.estimate.expectedAdvantageCad,actualProfitCad:actualProfit,holdProfitCad:hold,actualAdvantageCad:actualProfit-hold,profitErrorCad:actualProfit-projection.estimate.expectedProfitCad,advantageErrorCad:actualProfit-hold-projection.estimate.expectedAdvantageCad,hypotheticalProfitCad:hypothetical,hypotheticalAdvantageCad:hypothetical-hold,netCashFlowsCad:cash,prices:point.prices,actualBalances:actual,notes:['Actual units use ledger events no later than the frozen completed check-in close.','CAD deposits/withdrawals are matched in both paths and subtracted from profit. Later trades are excluded.','Hypothetical target outcome is separate from actual execution and retains the original slippage allowance.','Valuation uses the frozen Kraken completed daily reference close; executable fills used Ndax books. These are different sources.']};
 return outcome;
}
