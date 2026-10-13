import {createHash} from 'node:crypto';
import {GET as getHistory} from '@/app/api/rotation/history/route';
import {ASSETS,CRYPTO_ASSETS,type Amounts,type Asset,type HistoryDataset,type MarketSnapshot,type Portfolio} from './contract';
import {approveShift,previewShift} from './engine';
import {ApiError,dbRequest,freshMarket,getPortfolio,requirePortfolio,type RotationUser} from './server';
import {fitForecast,forecastFingerprintSource,forecastHorizon} from './forecast-advice';
import {strategyHash,strategyId,latestForecastAdvice} from './strategy-server';
import {allocationFingerprintSource,allocationMarks,allocationValue,currentWeights,estimateAllocation,projectionExpired,rankAllocations,validateWeights} from './allocation-engine';
import {computeAllocationOutcome} from './allocation-outcome';
import {allocationReplayFingerprintSource} from './allocation-replay';
import {executionConnection} from './execution-adapter';
import {ALLOCATION_VERSION,type AllocationBatch,type AllocationForecast,type AllocationOutcome,type AllocationProjection,type AllocationWeights,type AllocationWorkspace} from './allocation-contract';
const DAY=86400000;
type Trial<T>={id:string;data:T};
const hash=(value:unknown)=>createHash('sha256').update(JSON.stringify(value)).digest('hex');
async function history():Promise<HistoryDataset>{const response=await getHistory();const data=await response.json();if(!response.ok)throw new ApiError(data.error||'Public completed history unavailable.',503);return data;}
function validSlip(value:unknown):number{if(typeof value!=='number'||!Number.isFinite(value)||value<0||value>1000)throw new ApiError('Slippage allowance must be from 0 to 1000 basis points.');return value;}
function forecast(dataset:HistoryDataset,portfolio:Portfolio):AllocationForecast{
 const fit=fitForecast(dataset,portfolio.cadence);
 return {returns:fit.forecastReturns,members:fit.members,signalAt:fit.signalAt,latestTrainingEnd:fit.latestTrainingEnd,trainingOrigins:fit.trainingOrigins,modelHash:hash(forecastFingerprintSource()),confidence:'low',notes:['Causal mean of ridge penalties 1 and 10; uncertainty is not a calibrated probability.','Price forecasts use completed prices and matured outcomes. Current sentiment adds context, not an invented validated return uplift.','Execution and forecast entry prices differ; expected profits are estimates, not guarantees.']};
}
export async function loadProjection(user:RotationUser,id:unknown):Promise<AllocationProjection>{
 const rows=await dbRequest<Trial<{projection:AllocationProjection}>[]>(`wpr_trials?owner_id=eq.${user.id}&id=eq.${strategyId(id)}&data->>namespace=eq.allocation-projection&select=id,data`,{},user.accessToken);
 if(rows.length!==1)throw new ApiError('Projection not found in this account.',404);
 return rows[0].data.projection;
}
export async function loadBatch(user:RotationUser,id:unknown):Promise<AllocationBatch>{
 const rows=await dbRequest<{data:AllocationBatch}[]>(`wpr_batches?owner_id=eq.${user.id}&id=eq.${strategyId(id)}&select=data`,{},user.accessToken);
 if(rows.length!==1)throw new ApiError('Batch not found in this account.',404);return rows[0].data;
}
async function batchFor(user:RotationUser,projectionId:string):Promise<AllocationBatch|null>{
 const rows=await dbRequest<{data:AllocationBatch}[]>(`wpr_batches?owner_id=eq.${user.id}&projection_id=eq.${projectionId}&select=data`,{},user.accessToken);return rows[0]?.data??null;
}
async function allocationSettings(user:RotationUser):Promise<{riskPercent:number;slippageBps:number}|null>{
 const rows=await dbRequest<Trial<{config:{riskPercent:number;slippageBps:number}}>[]>(`wpr_trials?owner_id=eq.${user.id}&data->>namespace=eq.allocation-settings&select=id,data&order=created_at.desc,id.desc&limit=1`,{},user.accessToken);
 if(rows[0])return rows[0].data.config;
 const previous=await latestForecastAdvice(user);return previous?previous.data.config:null;
}
export async function saveAllocationSettings(user:RotationUser,body:Record<string,unknown>):Promise<AllocationWorkspace>{
 const risk=body.riskPercent,slip=validSlip(body.slippageBps);
 if(typeof risk!=='number'||!Number.isFinite(risk)||risk<0||risk>100)throw new ApiError('Crypto budget must be from 0 to 100%.');
 await dbRequest('wpr_trials',{method:'POST',body:JSON.stringify({id:crypto.randomUUID(),owner_id:user.id,kind:'protocol',data:{namespace:'allocation-settings',config:{riskPercent:risk,slippageBps:slip}}})});return allocationWorkspace(user);
}
export async function allocationWorkspace(user:RotationUser):Promise<AllocationWorkspace>{
 const portfolio=await getPortfolio(user);if(!portfolio)throw new ApiError('Create your portfolio first.',404);
 const [market,dataset,saved,projectionRows,outcomeRows,batchRows]=await Promise.all([freshMarket(),history(),allocationSettings(user),
 dbRequest<Trial<{projection:AllocationProjection}>[]>(`wpr_trials?owner_id=eq.${user.id}&data->>namespace=eq.allocation-projection&select=id,data&order=created_at.desc&limit=12`,{},user.accessToken),
 dbRequest<Trial<{outcome:AllocationOutcome}>[]>(`wpr_trials?owner_id=eq.${user.id}&data->>namespace=eq.allocation-outcome&select=id,data&order=created_at.desc&limit=24`,{},user.accessToken),
 dbRequest<{data:AllocationBatch}[]>(`wpr_batches?owner_id=eq.${user.id}&select=data&order=created_at.desc&limit=12`,{},user.accessToken)]);
 let fit:AllocationForecast|null=null,error:string|null=null;try{fit=forecast(dataset,portfolio);}catch(e){error=e instanceof Error?e.message:'Forecast unavailable.';}
 let recommendationDecision:AllocationWorkspace['recommendationDecision']='unavailable';
 let recommended=currentWeights(portfolio,market),reason='Current holdings retained until an estimate and allocation preference are available.';
 if(fit&&saved){
  const ranked=rankAllocations(portfolio,market,fit.returns,saved.riskPercent,saved.slippageBps);recommended=ranked.weights;recommendationDecision=ranked.compared?ranked.decision:'unavailable';
  reason='Highest estimated after-cost value among a deterministic diversified allocation grid at your saved crypto budget, all CAD, and keeping your units. Six-pair technical/news context is shown separately; it does not manufacture a return uplift.';
  if(ranked.unpriced)reason+=` ${ranked.unpriced} alternatives could not be priced with available venue depth/minimums; this comparison is limited to ${ranked.compared} feasible alternatives, not a claim that unavailable routes are inferior.`;
  if(!ranked.compared)error='Allocation comparison is unavailable: no target alternatives can be priced. Current units are shown, not a market HOLD recommendation.';
 }
 const {getCurrentAnalysis}=await import('./analysis-server');const context=await getCurrentAnalysis();
 const up=context.pairs.filter(p=>p.technical.trend==='uptrend').length,down=context.pairs.filter(p=>p.technical.trend==='downtrend').length;
 const covered=CRYPTO_ASSETS.filter(a=>context.sentiment.assets[a].status==='available');
 reason+=` Current evidence: ${up} of six pairs trend up, ${down} trend down; asset news coverage ${covered.length}/3. ${covered.map(a=>a+': '+context.sentiment.assets[a].label).join('; ')}. This context qualifies the low-confidence recommendation; numerical allocation remains based on causal price estimates and costs.`;
 return {forecast:fit,forecastError:error,market,recommendedWeights:recommended,recommendationDecision,recommendationReason:reason,riskPercent:saved?.riskPercent??null,slippageBps:saved?.slippageBps??null,projections:projectionRows.map(r=>r.data.projection),outcomes:outcomeRows.map(r=>r.data.outcome),batches:batchRows.map(r=>r.data),connection:executionConnection()};
}
export async function saveProjection(user:RotationUser,body:Record<string,unknown>):Promise<AllocationProjection>{
 const id=strategyId(body.id),portfolio=await requirePortfolio(user,body.expectedRevision);
 if(body.preserveUnits!==undefined&&typeof body.preserveUnits!=='boolean')throw new ApiError('preserveUnits must be a boolean.');
 const preserveUnits=body.preserveUnits===true;const slippageBps=validSlip(body.slippageBps);
 const existing=await dbRequest<Trial<{projection:AllocationProjection}>[]>(`wpr_trials?owner_id=eq.${user.id}&id=eq.${id}&data->>namespace=eq.allocation-projection&select=id,data`,{},user.accessToken);if(existing[0])return existing[0].data.projection;
 const [dataset,market]=await Promise.all([history(),freshMarket()]);const weights=preserveUnits?currentWeights(portfolio,market):body.weights as AllocationWeights;validateWeights(weights);const fit=forecast(dataset,portfolio),estimate=estimateAllocation(portfolio,market,weights,fit.returns,slippageBps,preserveUnits);
 if(!estimate.feasible)throw new ApiError(estimate.reason||'Allocation cannot be quoted.',409);
 const {getCurrentAnalysis}=await import('./analysis-server');const analysis=await getCurrentAnalysis();
 const projection:AllocationProjection={id,createdAt:new Date().toISOString(),version:ALLOCATION_VERSION,portfolioId:portfolio.id,startingRevision:portfolio.revision,preserveUnits,asOf:market.fetchedAt,
 dueAt:new Date(Date.parse(forecastHorizon(fit.signalAt,portfolio.cadence))+DAY).toISOString(),weights:{...weights},slippageBps,feeBps:portfolio.feeBps,startingBalances:{...portfolio.balances},startingPortfolio:portfolio,market,dataset,forecast:fit,estimate,sourceHash:strategyHash({dataset,market}),evaluatorHash:hash([forecastFingerprintSource(),allocationFingerprintSource(),allocationReplayFingerprintSource(),previewShift.toString(),approveShift.toString()]),buildCommit:process.env.VERCEL_GIT_COMMIT_SHA??null,analysisId:analysis.id,analysis,rationale:preserveUnits?'Owner requested HOLD: preserve exact starting units regardless of subsequent price drift. Zero orders, fees and slippage.':'Owner-selected allocation evaluated with causal price forecasts and current execution costs. Frozen six-pair technical/sentiment evidence is contextual; historical sentiment was not fabricated.'};
 await requirePortfolio(user,portfolio.revision);
 await dbRequest('wpr_trials',{method:'POST',body:JSON.stringify({id,owner_id:user.id,kind:'development',data:{namespace:'allocation-projection',projection}})});return projection;
}
export async function checkInProjection(user:RotationUser,id:unknown):Promise<AllocationOutcome>{
 const projection=await loadProjection(user,id);
 const existing=await dbRequest<Trial<{outcome:AllocationOutcome}>[]>(`wpr_trials?owner_id=eq.${user.id}&data->>namespace=eq.allocation-outcome&data->>projectionId=eq.${projection.id}&select=id,data`,{},user.accessToken);if(existing[0])return existing[0].data.outcome;
 if(Date.now()<Date.parse(projection.dueAt))throw new ApiError('This frozen projection has not reached its check-in date.',409);
 const [dataset,portfolio,batch]=await Promise.all([history(),getPortfolio(user),batchFor(user,projection.id)]);if(!portfolio||portfolio.id!==projection.portfolioId)throw new ApiError('Original portfolio is unavailable.',409);
 const sourceDate=new Date(Date.parse(projection.dueAt)-DAY).toISOString().slice(0,10),point=dataset.points.find(p=>p.date===sourceDate);
 if(!point)throw new ApiError('The exact completed check-in price is unavailable; current prices will not replace it.',503);
 const outcome=computeAllocationOutcome(projection,portfolio,point,batch);
 await dbRequest('wpr_trials',{method:'POST',body:JSON.stringify({id:outcome.id,owner_id:user.id,kind:'development',data:{namespace:'allocation-outcome',projectionId:projection.id,outcome}})});return outcome;
}
async function writeBatch(user:RotationUser,batch:AllocationBatch,expected:number|null,portfolioRevision:number,next:Portfolio|null=null):Promise<AllocationBatch>{return dbRequest<AllocationBatch>('rpc/wpr_write_batch',{method:'POST',body:JSON.stringify({p_owner:user.id,p_batch:batch,p_expected:expected,p_portfolio_expected:portfolioRevision,p_next:next})});}
export async function applyAllocation(user:RotationUser,body:Record<string,unknown>):Promise<{batch:AllocationBatch;portfolio:Portfolio}>{
 const projection=await loadProjection(user,body.projectionId),previous=await batchFor(user,projection.id);if(previous){const portfolio=await getPortfolio(user);if(!portfolio)throw new ApiError('Portfolio unavailable.',404);return{batch:previous,portfolio};}
 if(projectionExpired(projection.dueAt))throw new ApiError('This projection reached its check-in date. Save a fresh projection before Apply.',409);
 const portfolio=await requirePortfolio(user,body.expectedRevision);if(portfolio.id!==projection.portfolioId||portfolio.revision!==projection.startingRevision)throw new ApiError('Portfolio or holdings changed. Save a new projection before Apply.',409);
 const market=await freshMarket(),estimate=estimateAllocation(portfolio,market,projection.weights,projection.forecast.returns,projection.slippageBps,projection.preserveUnits===true);
 if(!estimate.feasible)throw new ApiError(estimate.reason||'Allocation cannot be executed.',409);
 const frozenCost=projection.estimate.feesCad+projection.estimate.spreadDepthCad+projection.estimate.slippageCad;
 const max=body.maxCostCad;if(typeof max!=='number'||!Number.isFinite(max)||max<0||max>frozenCost+0.011)throw new ApiError('Approved maximum must not exceed the saved projection cost allowance.');
 const cost=estimate.feesCad+estimate.spreadDepthCad;if(cost>max+0.00000001)throw new ApiError('Current execution costs exceed the approved projection allowance. Save a refreshed projection.',409);
 const id=strategyId(body.idempotencyKey),now=new Date().toISOString();
 const batch:AllocationBatch={id,projectionId:projection.id,portfolioId:portfolio.id,revision:0,mode:'paper',status:estimate.legs.length?'running':'completed',createdAt:now,updatedAt:now,expectedPortfolioRevision:portfolio.revision,orders:estimate.legs.map((leg,index)=>({id:crypto.randomUUID(),clientOrderId:`${id}:${index}`,index,status:'queued',from:leg.from,to:leg.to,amount:leg.amount})),pauseReason:null,maxCostCad:max,costsCad:0,targetWeights:projection.weights};
 return{batch:await writeBatch(user,batch,null,portfolio.revision),portfolio};
}
export async function advanceAllocation(user:RotationUser,body:Record<string,unknown>):Promise<{batch:AllocationBatch;portfolio:Portfolio}>{
 const batch=await loadBatch(user,body.batchId);if(batch.revision!==body.expectedBatchRevision)throw new ApiError('Batch changed; reload its current state.',409);
 const portfolio=await getPortfolio(user);if(!portfolio)throw new ApiError('Portfolio unavailable.',404);
 if(batch.status==='completed'||batch.status==='cancelled')return{batch,portfolio};
 const next={...batch,revision:batch.revision+1,updatedAt:new Date().toISOString(),orders:batch.orders.map(o=>({...o}))};
 if(body.kind==='cancel'){next.status='cancelled';next.pauseReason='Owner stopped remaining trades. Confirmed fills remain in the ledger.';return{batch:await writeBatch(user,next,batch.revision,portfolio.revision),portfolio};}
 if(body.kind==='pause'){next.status='paused';next.pauseReason='Paused by owner.';return{batch:await writeBatch(user,next,batch.revision,portfolio.revision),portfolio};}
 if(body.kind==='resume'){
  if(batch.orders.some(o=>o.status==='unknown'||o.status==='partial'))throw new ApiError('Reconcile uncertain or partial fills before resuming.',409);
  if(portfolio.revision!==batch.expectedPortfolioRevision)throw new ApiError('Holdings changed outside this batch. Reconcile before resuming.',409);
  next.status='running';next.pauseReason=null;return{batch:await writeBatch(user,next,batch.revision,portfolio.revision),portfolio};
 }
 if(batch.status!=='running')return{batch,portfolio};
 if(portfolio.revision!==batch.expectedPortfolioRevision){next.status='paused';next.pauseReason='Portfolio changed outside the approved sequence; remaining orders were not submitted.';return{batch:await writeBatch(user,next,batch.revision,portfolio.revision),portfolio};}
 const order=next.orders.find(o=>o.status==='queued'||o.status==='intent');
 if(!order){next.status='completed';return{batch:await writeBatch(user,next,batch.revision,portfolio.revision),portfolio};}
 if(order.status==='queued'){order.status='intent';return{batch:await writeBatch(user,next,batch.revision,portfolio.revision),portfolio};}
 let proposedPortfolio:Portfolio|null=null;
 try{
  const projection=await loadProjection(user,batch.projectionId);
  if(projectionExpired(projection.dueAt))throw new Error('This projection reached its check-in date. Stop remaining trades and save a fresh projection.');
  const market=await freshMarket();
  let amount=order.amount;
  if(order.from==='CAD'){
   const remaining=estimateAllocation(portfolio,market,projection.weights,projection.forecast.returns,projection.slippageBps,projection.preserveUnits===true);
   if(!remaining.feasible)throw new Error(remaining.reason||'Remaining target cannot be priced.');
   const replanned=remaining.legs.find(l=>l.from==='CAD'&&l.to===order.to);
   if(!replanned)throw new Error('Remaining purchase is below venue minimum or target changed; review allocation.');
   amount=replanned.amount;
  }
  const quote=previewShift(portfolio,market,order.from,order.to,amount),proposed=approveShift(portfolio,quote);
  const reference=allocationMarks(projection.market);
  const actualCost=Math.max(0,allocationValue(portfolio.balances,reference)-allocationValue(proposed.balances,reference));
  if(batch.costsCad+actualCost>batch.maxCostCad+0.00000001)throw new Error('This fill would exceed the approved total cost allowance at the frozen reference prices.');
  proposed.events[proposed.events.length-1].id=order.id;
  order.status='filled';order.amount=quote.amount;order.filledAt=proposed.events.at(-1)!.at;order.fills=quote.legs;order.feeCad=Number(quote.feeCad);
  next.costsCad=batch.costsCad+actualCost;next.expectedPortfolioRevision=proposed.revision;if(next.orders.every(o=>o.status==='filled'))next.status='completed';
  proposedPortfolio=proposed;
 }catch(error){next.status='paused';next.pauseReason=error instanceof Error?error.message:'Execution paused.';order.error=next.pauseReason;return{batch:await writeBatch(user,next,batch.revision,portfolio.revision),portfolio};}
 // A transport/commit failure is NOT a failed fill. Read persisted state before retrying;
 // never save a mutated filled order without its atomic ledger commit.
 return{batch:await writeBatch(user,next,batch.revision,portfolio.revision,proposedPortfolio),portfolio:proposedPortfolio!};
}
