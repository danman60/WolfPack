import {ASSETS, CRYPTO_ASSETS, type Amounts, type Asset, type CryptoAsset, type MarketSnapshot, type Portfolio} from './contract';
import {approveShift, previewShift} from './engine';
import type {AllocationEstimate, AllocationWeights} from './allocation-contract';
const S = 100_000_000n;
const ceil = (n: bigint, d: bigint) => (n + d - 1n) / d;
const u = (n: string) => { if (!/^(0|[1-9]\d*)(\.\d{1,8})?$/.test(n)) throw new Error('Invalid fixed-precision amount.'); const [a,b=''] = n.split('.'); return BigInt(a)*S+BigInt(b.padEnd(8,'0')); };
const dec = (n: bigint) => `${n/S}.${(n%S).toString().padStart(8,'0')}`;
export function validateWeights(weights: AllocationWeights): void {
  if (!weights || Object.keys(weights).length !== 4 || ASSETS.some(a => !Number.isFinite(weights[a]) || weights[a]<0 || weights[a]>1) || Math.abs(ASSETS.reduce((s,a)=>s+weights[a],0)-1)>1e-8) throw new Error('Four allocation weights must be finite, nonnegative and sum to 100%.');
}
export function allocationMarks(market: MarketSnapshot): Record<Asset,number> { return {CAD:1,...Object.fromEntries(CRYPTO_ASSETS.map(a=>[a,(Number(market.books[a].bid)+Number(market.books[a].ask))/2]))} as Record<Asset,number>; }
export function allocationValue(balances: Amounts, prices: Record<Asset,number>): number { return ASSETS.reduce((sum,a)=>sum+Number(balances[a])*prices[a],0); }
export function currentWeights(portfolio: Portfolio, market: MarketSnapshot): AllocationWeights {
  const marks=allocationMarks(market),total=allocationValue(portfolio.balances,marks);
  if (!(total>0)) throw new Error('Portfolio value must be positive.');
  return Object.fromEntries(ASSETS.map(a=>[a,Number(portfolio.balances[a])*marks[a]/total])) as AllocationWeights;
}
/** Same pure calculation in browser and server. No network, persistence or funded execution. */
export function estimateAllocation(portfolio: Portfolio, market: MarketSnapshot, weights: AllocationWeights, returns: Record<CryptoAsset,number>, slippageBps: number, preserveUnits=false): AllocationEstimate {
  validateWeights(weights);
  if (!Number.isFinite(slippageBps)||slippageBps<0||slippageBps>1000||CRYPTO_ASSETS.some(a=>!Number.isFinite(returns[a])||returns[a]<-1)) throw new Error('Invalid forecast or slippage allowance.');
  const marks=allocationMarks(market), capital=allocationValue(portfolio.balances,marks);
  const terminal=(balances:Amounts)=>ASSETS.reduce((sum,a)=>sum+Number(balances[a])*marks[a]*(a==='CAD'?1:1+returns[a]),0);
  const hold=terminal(portfolio.balances);
  const result:AllocationEstimate={feasible:true,reason:null,weights:{...weights},startingValueCad:capital,expectedEndingValueCad:hold,expectedProfitCad:hold-capital,expectedHoldProfitCad:hold-capital,expectedAdvantageCad:0,feesCad:0,slippageCad:0,spreadDepthCad:0,turnoverCad:0,plannedBalances:{...portfolio.balances},legs:[],notes:[]};
  const ownedWeights=currentWeights(portfolio,market);
  if(preserveUnits){result.weights={...ownedWeights};result.notes=['HOLD preserves every current unit; no trades or trading costs.'];return result;}
  try {
    const prices=Object.fromEntries(ASSETS.map(a=>[a,a==='CAD'?S:(u(market.books[a].bid)+u(market.books[a].ask))/2n])) as Record<Asset,bigint>;
    const scaled=Object.fromEntries(ASSETS.map(a=>[a,BigInt(Math.round(weights[a]*Number(S)))])) as Record<Asset,bigint>;
    const largest=ASSETS.reduce((a,b)=>weights[a]>=weights[b]?a:b);scaled[largest]+=S-ASSETS.reduce((sum,a)=>sum+scaled[a],0n);
    const initial=ASSETS.reduce((sum,a)=>sum+u(portfolio.balances[a])*prices[a]/S,0n);
    if(initial<=0n)throw new Error('Portfolio value must be positive.');
    function cost(asset:CryptoAsset,qty:bigint,buy:boolean) {
      let remaining=qty,numerator=0n;
      for(const level of buy?market.books[asset].asks:market.books[asset].bids){const take=remaining<u(level.quantity)?remaining:u(level.quantity);numerator+=take*u(level.price);remaining-=take;if(!remaining)break;}
      if(remaining)throw new Error(`Insufficient ${asset} book depth to reach the target.`);
      const gross=buy?ceil(numerator,S):numerator/S;const fee=ceil(gross*BigInt(portfolio.feeBps),10000n);
      return {gross,fee,total:buy?gross+fee:gross-fee};
    }
    function proposal(value:bigint){
      let cash=u(portfolio.balances.CAD), loss=0n;
      const trades: {asset:CryptoAsset;qty:bigint;buy:boolean;budget:bigint}[]=[];
      for(const asset of CRYPTO_ASSETS){
        const book=market.books[asset],increment=u(book.increment),owned=u(portfolio.balances[asset]);
        const desired=(value*scaled[asset]/prices[asset])/increment*increment;
        const delta=desired-owned,buy=delta>0n,qty=(delta<0n?-delta:delta)/increment*increment;
        if(!qty||qty<u(book.minimum))continue;
        const c=cost(asset,qty,buy);cash+=buy?-c.total:c.total; loss+=buy?c.total-qty*prices[asset]/S:qty*prices[asset]/S-c.total;trades.push({asset,qty,buy,budget:c.total});
      }
      return {cash,trades,loss,feasible:cash>=value*scaled.CAD/S};
    }
    let high=initial,low=initial;
    const top=proposal(high);
    if(!top.feasible){
      low=initial-top.loss;
      if(low<0n)low=0n;
      let candidate=proposal(low);
      while(!candidate.feasible&&low>0n){low/=2n;candidate=proposal(low);}
      if(!candidate.feasible)throw new Error('Target cannot be self-financed.');
      while(low<high){const mid=(low+high+1n)/2n;if(proposal(mid).feasible)low=mid;else high=mid-1n;}
    }
    const chosen=proposal(low);if(!chosen.feasible)throw new Error('Target cannot be self-financed at venue precision.');let simulated=portfolio;
    const time=new Date(Math.max(Date.parse(market.fetchedAt),Date.parse(portfolio.events.at(-1)!.at)));
    if(time.getTime()>=Date.parse(market.expiresAt))throw new Error('The book predates your latest ledger entry. Refresh market prices.');
    for(const trade of chosen.trades.sort((a,b)=>Number(a.buy)-Number(b.buy))){
      const from:Asset=trade.buy?'CAD':trade.asset,to:Asset=trade.buy?trade.asset:'CAD';
      const quote=previewShift(simulated,market,from,to,dec(trade.buy?trade.budget:trade.qty),time);
      simulated=approveShift(simulated,quote,time);
      const gross=quote.legs.reduce((sum,l)=>sum+Number(l.grossCad),0);
      result.legs.push({id:quote.id,from,to,amount:quote.amount,received:quote.received,feeCad:Number(quote.feeCad),grossCad:gross,fills:quote.legs});
      result.feesCad+=Number(quote.feeCad);result.turnoverCad+=gross;
    }
    result.plannedBalances={...simulated.balances};
    const after=allocationValue(simulated.balances,marks);
    result.spreadDepthCad=Math.max(0,capital-after-result.feesCad);
    result.slippageCad=result.turnoverCad*slippageBps/10000;
    result.expectedEndingValueCad=terminal(simulated.balances)-result.slippageCad;
    result.expectedProfitCad=result.expectedEndingValueCad-capital;
    result.expectedAdvantageCad=result.expectedEndingValueCad-hold;
    result.notes=['Fees and current spread/depth are included in fills. Additional slippage allowance is deducted once from the forecast.','Venue minimums/increments can leave small residual holdings. Actual fills determine the final allocation.'];
    return result;
  }catch(error){return {...result,feasible:false,reason:error instanceof Error?error.message:'Allocation cannot be priced.',legs:[],plannedBalances:{...portfolio.balances}};}
}
/** Finite explicit portfolio search; actual units/HOLD remains a separate cost-free alternative. */
export function rankAllocations(portfolio:Portfolio,market:MarketSnapshot,returns:Record<CryptoAsset,number>,riskPercent:number,slippageBps:number):{weights:AllocationWeights;decision:'hold'|'shift';compared:number;unpriced:number} {
 if(!Number.isFinite(riskPercent)||riskPercent<0||riskPercent>100)throw new Error('Crypto budget must be from 0 to 100%.');
 let recommended=currentWeights(portfolio,market),best=estimateAllocation(portfolio,market,recommended,returns,slippageBps,true).expectedHoldProfitCad;
 const risk=riskPercent/100,options:AllocationWeights[]=[{CAD:1,BTC:0,ETH:0,LINK:0}];
 for(let btc=0;btc<=10;btc++)for(let eth=0;eth<=10-btc;eth++)options.push({CAD:1-risk,BTC:risk*btc/10,ETH:risk*eth/10,LINK:risk*(10-btc-eth)/10});
 let compared=0,unpriced=0,decision:'hold'|'shift'='hold';
 for(const weights of options){const estimate=estimateAllocation(portfolio,market,weights,returns,slippageBps);if(estimate.feasible)compared++;else unpriced++;if(estimate.feasible&&estimate.expectedProfitCad>best+0.01){best=estimate.expectedProfitCad;recommended=weights;decision='shift';}}
 return {weights:recommended,decision,compared,unpriced};
}
export function recommendAllocation(portfolio:Portfolio,market:MarketSnapshot,returns:Record<CryptoAsset,number>,riskPercent:number,slippageBps:number):AllocationWeights{return rankAllocations(portfolio,market,returns,riskPercent,slippageBps).weights;}

export function allocationFingerprintSource():string{return [estimateAllocation,rankAllocations,validateWeights,currentWeights,allocationValue,allocationMarks,u,dec,ceil].map(fn=>fn.toString()).join("\n");}

export function projectionExpired(dueAt:string,now=Date.now()):boolean{const due=Date.parse(dueAt);return !Number.isFinite(due)||now>=due;}
