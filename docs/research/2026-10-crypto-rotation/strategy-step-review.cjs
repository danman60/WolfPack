// Six CPU sizing scenarios using real source modules and genuine fresh public books.
// No authentication, network calls, database writes or recommendation eligibility bypass.
// These explicit QA allocation targets do not claim the backtest produced a SHIFT.
// Archived snapshots expire intentionally; fetch a new public snapshot for another run.
const fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),assert=require('node:assert/strict');
const [app,marketFile,outputFile]=process.argv.slice(2);
if(!app||!marketFile||!outputFile)throw new Error('Explicit APP_ROOT MARKET_JSON OUTPUT_JSON required. Read-only CPU check; market must be a fresh genuine public snapshot.');
const ts=require(app+'/node_modules/typescript');
const originalResolve=Module._resolveFilename;
Module._resolveFilename=function(id,parent,...args){return originalResolve.call(this,id.startsWith('@/')?app+'/src/'+id.slice(2):id,parent,...args)};
require.extensions['.ts']=(module,file)=>module._compile(ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText,file);
const {createPortfolio,previewShift,approveShift}=require(app+'/src/lib/rotation/engine.ts');
const {sizeStrategyStep}=require(app+'/src/lib/rotation/strategy-server.ts');
const market=JSON.parse(fs.readFileSync(marketFile,'utf8'));
const output=[];
for(const [label,opening,target,risk] of [
 ['cash-buy',{CAD:'10000',BTC:'0',ETH:'0',LINK:'0'},'BTC',0.6],
 ['target-sell',{CAD:'0',BTC:'0.1',ETH:'0',LINK:'0'},'BTC',0.6],
 ['mixed-cross',{CAD:'5000',BTC:'0.02',ETH:'1',LINK:'25'},'ETH',0.6],
 ['cash-exit',{CAD:'5000',BTC:'0.02',ETH:'1',LINK:'25'},'CAD',0],
 ['venue-dust',{CAD:'10',BTC:'0.00000001',ETH:'0',LINK:'0'},'CAD',0],
 ['depth-rejection',{CAD:'1000000000',BTC:'0',ETH:'0',LINK:'0'},'BTC',1],
]){
 let p=createPortfolio({name:'Independent offline QA',opening,cadence:'weekly',feeBps:20},market);
 const baseline=JSON.stringify(p.baseline);let steps=0,fees=0;const decisions=[];
 let state={id:crypto.randomUUID(),target,targetWeights:{CAD:1-risk,BTC:target==='BTC'?risk:0,ETH:target==='ETH'?risk:0,LINK:target==='LINK'?risk:0},reviewDate:'2026-10-13',stepsCompleted:0,completesAfterNext:false,dust:[]};
 for(let i=0;i<4;i++){
  const d=sizeStrategyStep(p,market,state);decisions.push(d);
  if(d.decision!=='shift')break;
  const q=previewShift(p,market,d.nextShift.from,d.nextShift.to,d.nextShift.amount);p=approveShift(p,q);for(const leg of q.legs){const fixed=x=>BigInt(x.split('.')[0])*100000000n+BigInt((x.split('.')[1]||'').padEnd(8,'0'));assert.equal(fixed(leg.feeCad),(fixed(leg.grossCad)*20n+9999n)/10000n);}steps++;fees+=Number(q.feeCad);
  assert.equal(JSON.stringify(p.baseline),baseline);assert.equal(p.events.at(-1).id,q.id);assert.ok(Object.values(p.balances).every(x=>Number(x)>=0));
  state={...d.rebalance,stepsCompleted:d.rebalance.stepsCompleted+1};
  if(d.rebalance.completesAfterNext)break;
 }
 const marks={CAD:1,...Object.fromEntries(['BTC','ETH','LINK'].map(a=>[a,(Number(market.books[a].bid)+Number(market.books[a].ask))/2]))};
 const total=Object.entries(p.balances).reduce((s,[a,q])=>s+Number(q)*marks[a],0);
 const achieved=target==='CAD'?Number(p.balances.CAD)/total:Number(p.balances[target])*marks[target]/total;
 if(label==='depth-rejection'){assert.equal(decisions[0].decision,'blocked');assert.equal(steps,0);}
 else if(label==='venue-dust'){assert.equal(decisions[0].decision,'hold');assert.equal(steps,0);assert.ok(decisions[0].rebalance.dust.length>0);assert.equal(p.balances.BTC,'0.00000001');}
 else {assert.ok(steps<=3);assert.ok(Math.abs(achieved-(target==='CAD'?1:risk))<0.0001);}
 output.push({label,steps,feesCad:fees,targetShare:achieved,final:p.balances,decisions});
}
fs.writeFileSync(outputFile,JSON.stringify({source:market.source,marketId:market.id,fetchedAt:market.fetchedAt,checks:output},null,2));
console.log(JSON.stringify(output.map(({label,steps,feesCad,targetShare,decisions})=>({label,steps,feesCad,targetShare,decision:decisions.at(-1).decision})),null,2));
