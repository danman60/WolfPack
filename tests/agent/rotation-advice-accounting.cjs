/* Offline deterministic accounting scenarios. No network, secrets or performance evidence. */
const fs = require('fs');
const path = require('path');
const assert = require('node:assert/strict');
const ts = require(path.resolve('app/node_modules/typescript'));
let forecasts = {BTC: .1, ETH: .05, LINK: -.2};
const cache = {};
function load(file) {
  file = path.resolve(file);
  if (file.endsWith('/rotation/server.ts')) return {ApiError: class ApiError extends Error {}};
  if (file.endsWith('/api/rotation/history/route.ts')) return {GET: () => {throw Error('Network forbidden in accounting fixture');}};
  if (file.endsWith('/rotation/forecast-advice.ts')) return {
    fitForecast: () => ({forecastReturns: forecasts, trainingOrigins: 300, signalAt: new Date().toISOString(), latestTrainingEnd: '2020-01-01'}),
    forecastHorizon: date => new Date(Date.parse(date) + 7*86400000).toISOString(),
  };
  if (cache[file]) return cache[file].exports;
  const m = {exports: {}}; cache[file] = m;
  const js = ts.transpileModule(fs.readFileSync(file,'utf8'), {compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020}}).outputText;
  new Function('require','module','exports', js)(name => name.startsWith('.') ? load(path.resolve(path.dirname(file),name+'.ts')) : name.startsWith('@/') ? load(path.resolve('app/src',name.slice(2)+'.ts')) : require(name), m, m.exports);
  return m.exports;
}
const engine = load('app/src/lib/rotation/engine.ts');
const api = load('app/src/lib/rotation/strategy-server.ts');
function market(depth='1000000') {
  const books = {};
  for (const [asset,p] of Object.entries({BTC:100, ETH:10, LINK:1})) books[asset] = {asset,
    bid:(p*.999).toFixed(8),ask:(p*1.001).toFixed(8),
    bids:[{price:(p*.999).toFixed(8),quantity:depth}],asks:[{price:(p*1.001).toFixed(8),quantity:depth}],
    minimum: '0.00000001', increment:'0.00000001'};
  return {id:crypto.randomUUID(),source:'Explicit synthetic accounting book',fetchedAt:new Date().toISOString(),expiresAt:new Date(Date.now()+30000).toISOString(),books};
}
function portfolio(m, fee=20, opening={CAD:'10000',BTC:'0',ETH:'0',LINK:'0'}) {
  return engine.createPortfolio({name:'Offline accounting fixture',opening,cadence:'weekly',feeBps:fee},m);
}
function near(a,b, tolerance=1e-5) {assert.ok(Math.abs(a-b)<=tolerance,`${a} != ${b}`);}
(async()=>{
  const checks=[];
  const m=market();const p=portfolio(m);const original=JSON.stringify(p);
  const report=await api.buildForecastAdviceReport(p,m,{source:'Accounting fixture'},60,10);
  assert.equal(JSON.stringify(p),original);assert.equal(report.decision,'shift');assert.equal(report.nextShift.to,'BTC');
  // Derive post-fee target directly: q*mid = w*(C - q*(ask*(1+fee)-mid)).
  const ask=100.1,mid=100,fee=.002,w=.6,C=10000;
  const q=Math.floor((w*C/(mid+w*(ask*(1+fee)-mid)))*1e8)/1e8;
  const gross=q*ask;const charged=Math.ceil((gross*fee-1e-10)*1e8)/1e8;
  const cash=C-gross-charged;
  near(report.targetValuesCad.BTC,q*mid);near(report.targetValuesCad.CAD,cash);
  near(report.feesCad,charged);near(report.slippageCad,gross*.001);
  near(report.expectedTargetValueCad,cash+q*mid*1.1-gross*.001);
  near(report.expectedAdvantageCad,report.expectedTargetValueCad-C);
  for (const candidate of report.candidates) {
    assert.equal(candidate.feasible,true);
    if (candidate.target==='HOLD' || candidate.target==='CAD') {near(candidate.expectedValueCad,C);continue;}
    const mark={BTC:100,ETH:10,LINK:1}[candidate.target], offer=mark*1.001;
    const quantity=Math.floor(w*C/(mark+w*(offer*(1+fee)-mark))*1e8)/1e8;
    const grossValue=quantity*offer, candidateFee=Math.ceil((grossValue*fee-1e-10)*1e8)/1e8;
    near(Number(candidate.balances[candidate.target]),quantity);
    near(candidate.expectedValueCad,C-grossValue-candidateFee+quantity*mark*(1+forecasts[candidate.target])-grossValue*.001);
    near(candidate.feesCad,candidateFee);near(candidate.slippageCad,grossValue*.001);
  }
  checks.push('Independent self-financing buy quantity, spread, fee, slippage and terminal value; original portfolio immutable');
  forecasts={BTC:.001,ETH:.001,LINK:.001};
  const hold=await api.buildForecastAdviceReport(portfolio(m,1000),m,{source:'Accounting fixture'},60,1000);
  assert.equal(hold.decision,'hold');assert.equal(hold.nextShift,null);assert.equal(hold.feesCad,0);assert.equal(hold.slippageCad,0);assert.equal(hold.expectedAdvantageCad,0);
  checks.push('High costs select exact current holdings, with no artificial fee');
  forecasts={BTC:-.1,ETH:-.1,LINK:-.1};
  const sell=await api.buildForecastAdviceReport(portfolio(m,20,{CAD:'0',BTC:'100',ETH:'0',LINK:'0'}),m,{source:'Accounting fixture'},60,10);
  assert.equal(sell.decision,'shift');assert.equal(sell.nextShift.to,'CAD');assert.equal(sell.nextShift.from,'BTC');
  near(sell.feesCad,100*99.9*.002);near(sell.slippageCad,100*99.9*.001);
  near(sell.expectedTargetValueCad,100*99.9*(1-.002-.001));
  checks.push('Independent full sale proceeds, fees and slippage select CAD for negative forecasts');
  forecasts={BTC:.1,ETH:.05,LINK:-.2};
  const shallow=await api.buildForecastAdviceReport(p,market('0.000001'),{source:'Accounting fixture'},60,10);
  assert.equal(shallow.decision,'unavailable');assert.equal(shallow.nextShift,null);
  checks.push('Insufficient depth is unavailable, never substituted with HOLD');
  const zero=await api.buildForecastAdviceReport(p,m,{source:'Accounting fixture'},0,10);
  assert.equal(zero.decision,'hold');assert.equal(zero.expectedAdvantageCad,0);
  checks.push('Zero crypto allocation with current cash preserves owned funds');
  console.log(JSON.stringify({status:'PASS',checks,scope:'Synthetic mathematical controls only; no live SHIFT or profitability evidence.'},null,2));
})().catch(error=>{console.error(error);process.exitCode=1;});
