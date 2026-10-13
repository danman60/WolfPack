// Standalone real-data verification runner; no network, credentials or financial writes.
// Usage: node this-file.cjs COMPILED_ROTATION_DIR HISTORY_JSON OUTPUT_JSON
const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const [compiled, historyFile, outputFile] = process.argv.slice(2);
if (!compiled || !historyFile || !outputFile) throw new Error("Explicit compiled module, real history and output paths required");
const { runStrategyStudy, strategyStudyFingerprintSource } = require(path.resolve(compiled, "strategy-study.js"));
const { runResearch } = require(path.resolve(compiled, "replay.js"));
const dataset = JSON.parse(fs.readFileSync(historyFile, "utf8"));
const checks = [];
const record = (name, detail) => checks.push({name, status:"PASS", detail});
const close = (a,b) => assert.ok(Math.abs(a-b) <= 1e-7 * Math.max(1, Math.abs(a)/10000), `${a} != ${b}`);
const assets = ["BTC", "ETH", "LINK"];
const qa = { capitalCad:10000, riskPercent:60, feeBps:20, slippageBps:10 };
const reports = {};
for (const cadence of ["weekly", "monthly"]) {
  const config = {...qa,cadence};
  const report = runStrategyStudy(dataset,config);
  assert.equal(report.candidateCount,5);
  assert.deepEqual(report.candidates.map(x=>x.lookbackDays),[14,30,60,90,180]);
  assert.deepEqual(runStrategyStudy(dataset,config),report);
  reports[cadence] = report;
  const original = runResearch(dataset,{...config,lookbackDays:180});
  const same = report.candidates.find(x=>x.lookbackDays===180);
  close(same.metrics.finalCad,original.finalCad); close(same.metrics.feesCad,original.feesCad);
  assert.equal(same.metrics.trades,original.trades);
  original.points.forEach((point,i)=>{close(point.strategyCad,same.points[i].strategyCad); close(point.holdCad,same.points[i].holdCad);});
  record(`${cadence}: 180-day common-start candidate agrees with independent existing v1 replay`,{points:original.points.length,legs:original.trades});
  for (const result of [...report.candidates,report.outer]) {
    const initialDay = dataset.points.find(x=>x.date===result.points[0].date);
    const index = dataset.points.indexOf(initialDay);
    const initialCash = config.capitalCad*(1-config.riskPercent/100);
    const units = Object.fromEntries(assets.map(asset=>[asset,config.capitalCad*config.riskPercent/300/initialDay.prices[asset]]));
    const nextDay = dataset.points[index+1];
    const sellGross = assets.reduce((sum,asset)=>sum+units[asset]*nextDay.prices[asset]*(1-config.slippageBps/10000),0);
    const costedCash = initialCash+sellGross*(1-config.feeBps/10000);
    result.points.forEach((point,i)=>{
      const day=dataset.points[index+i];
      close(point.holdCad,initialCash+assets.reduce((sum,asset)=>sum+units[asset]*day.prices[asset],0));
      close(point.cashCad,i===0?config.capitalCad:costedCash);
      assert.ok([point.strategyCad,point.holdCad,point.cashCad].every(x=>Number.isFinite(x)&&x>=0));
    });
    close(result.metrics.feesCad,result.metrics.turnoverCad*config.feeBps/10000);
    close(result.metrics.excessHoldCad,result.metrics.finalCad-result.metrics.holdCad);
    close(result.metrics.excessCashCad,result.metrics.finalCad-result.metrics.cashCad);
    let peak=config.capitalCad,dd=0;
    for(const point of result.points) {peak=Math.max(peak,point.strategyCad);dd=Math.max(dd,(peak-point.strategyCad)/peak*100);}
    close(result.metrics.maxDrawdownPercent,dd);
  }
  record(`${cadence}: every observed HOLD/CAD mark independently reconciled; fees/turnover and daily drawdown reconcile`,{curves:6});
  for (const length of [367,425,426,485,486,545,546,605,606,665,666,700]) {
    const points=dataset.points.slice(0,length);
    const prefix={...dataset,points,coverageEnd:points.at(-1).date};
    const earlier=runStrategyStudy(prefix,config);
    assert.deepEqual(earlier.outer.points,report.outer.points.filter(x=>x.date<=prefix.coverageEnd));
    const stripBlock = ({completed,...row})=>row;
    assert.deepEqual(earlier.blocks.map(stripBlock),report.blocks.filter(x=>x.start<=prefix.coverageEnd).map(stripBlock));
    const stripReview = ({completed,...row})=>row;
    assert.deepEqual(earlier.outer.reviews.map(stripReview),report.outer.reviews.filter(x=>x.date<=prefix.coverageEnd).map(stripReview));
    earlier.candidates.forEach((row,i)=>assert.deepEqual(row.points,report.candidates[i].points.filter(x=>x.date<=prefix.coverageEnd)));
    assert.equal(earlier.latestSelection.trainingThrough < earlier.plan.horizonStart,true);
  }
  record(`${cadence}: 12 genuine chronological prefixes preserve earlier scores, choices, reviews and all curve points`,{prefixes:12});
  for (const block of report.blocks) {
    assert.ok(block.trainingThrough<block.start);
    const ranked=[...block.scores].sort((a,b)=>b.scoreCad-a.scoreCad||a.lookbackDays-b.lookbackDays);
    assert.equal(block.selected,ranked[0].scoreCad>0?ranked[0].candidateId:"hold");
    block.scores.forEach(row=>close(row.scoreCad,Math.min(row.metrics.excessHoldCad,row.metrics.excessCashCad)));
  }
  if (report.outer.metrics.excessHoldCad<=0 || report.outer.metrics.excessCashCad<=0) assert.equal(report.plan.status,"hold");
  if (report.plan.status==="hold") {assert.equal(report.plan.targetWeights,null);assert.equal(report.plan.target,null);}
  assert.equal(report.exposure,"already-exposed");
  record(`${cadence}: selector objective/ties, prior-day training and explicit HOLD evidence gates reconcile`,report.plan.reasons);
}
let scenarios=0;
for (const cadence of ["weekly","monthly"]) for (const riskPercent of [0,60,100]) for (const feeBps of [0,20,1000]) for(const slippageBps of [0,1000]) {
  const report=runStrategyStudy(dataset,{...qa,cadence,riskPercent,feeBps,slippageBps});
  scenarios++;
  for(const result of [...report.candidates,report.outer]) {
    assert.ok(result.points.every(point=>[point.strategyCad,point.holdCad,point.cashCad].every(x=>Number.isFinite(x)&&x>=0)));
    if(feeBps===0)close(result.metrics.feesCad,0);
  }
  if(riskPercent===0){assert.equal(report.plan.status,"hold");close(report.outer.metrics.finalCad,qa.capitalCad);assert.equal(report.outer.metrics.trades,0);}
}
record("Real-history boundary scenarios remain finite and nonnegative; zero risk produces no trading",{scenarios});
for(const cadence of ["weekly","monthly"]) for(const date of ["2026-10-01","2026-10-02","2026-10-03"]) {
  const points=dataset.points.filter(day=>day.date<date);
  const marks=points.at(-1).prices;
  const balances={CAD:"4000",...Object.fromEntries(assets.map(asset=>[asset,String(2000/marks[asset])]))};
  const report=runStrategyStudy(dataset,{...qa,cadence},{balances,marks,asOf:date+"T21:00:00-04:00",basis:"entered-portfolio"});
  const due=cadence==="weekly"?date==="2026-10-02":date==="2026-10-01";
  assert.equal(report.plan.reviewDue,due);
  assert.equal(report.plan.signalThrough,points.at(-1).date);
  assert.equal(report.coverageEnd,points.at(-1).date);
  assert.ok(report.plan.nextReviewDate>=date);
  if(!due){assert.equal(report.plan.status,"hold");assert.ok(report.plan.reasons.includes("not-scheduled-review"));assert.equal(report.plan.targetWeights,null);}
  const prefix=runStrategyStudy({...dataset,points,coverageEnd:points.at(-1).date},{...qa,cadence});
  assert.deepEqual(report.outer,prefix.outer);
}
record("Six actual-date scenarios enforce weekly/monthly schedule and prior-Eastern-day evidence",{scenarios:6});
const frozen=JSON.stringify(dataset);
runStrategyStudy(dataset,{...qa,cadence:"weekly"});
assert.equal(JSON.stringify(dataset),frozen);
record("Dataset input unchanged; repeated evaluation deterministic",{});
const evidence={
  generatedAtEastern:new Intl.DateTimeFormat("sv-SE",{timeZone:"America/New_York",dateStyle:"short",timeStyle:"long"}).format(new Date()),
  scope:"QA experimental scenarios only; no owner preferences, recommendation or optimized parameters. All historical dates exposed. No private financial requests.",
  sourceHash:crypto.createHash("sha256").update(JSON.stringify({source:dataset.source,points:dataset.points})).digest("hex"),
  evaluatorHash:crypto.createHash("sha256").update(strategyStudyFingerprintSource()).digest("hex"),
  archive:dataset, explicitQaConfig:qa, reports, checks,
};
fs.writeFileSync(outputFile,JSON.stringify(evidence,null,2)+"\n");
console.log(JSON.stringify({status:"PASS",checks:checks.length,boundaryScenarios:scenarios,sourceHash:evidence.sourceHash,weekly:reports.weekly.outer.metrics,monthly:reports.monthly.outer.metrics},null,2));
