"use client";

import { useEffect, useState, type FormEvent } from "react";
import { ASSETS, cad, eastern, ROTATION_STYLE, type HoldingRow, type Portfolio } from "@/lib/rotation/contract";
import { STRATEGY_STUDY_VERSION, type StrategyChoice } from "@/lib/rotation/strategy-contract";
import type { StrategyPlanState, StrategyTrial, StrategyTrialSummary } from "@/lib/rotation/strategy-api-contract";

type Development = Extract<StrategyTrial, { kind: "development" }>;
type Props = {
  portfolio: Portfolio;
  holdings: HoldingRow[];
  planState: StrategyPlanState;
  now: number;
  disabled: boolean;
  request: <T>(path: string, body?: unknown) => Promise<T>;
  onState: (result: { portfolio: Portfolio; planState: StrategyPlanState }) => void;
  onQuote: (recommendation: Development) => Promise<void>;
  onHold: (recommendation: Development) => Promise<void>;
};
const nameOf = (choice: StrategyChoice) => choice === "hold" ? "HOLD" : `${choice.slice(9)}-day momentum`;

const REASONS: Record<string, string> = {
  "not-scheduled-review": "Today is between scheduled reviews. Retain your current units until the next review.",
  "insufficient-completed-outer-blocks": "Fewer than three complete evaluation blocks are available.",
  "insufficient-completed-outer-horizons": "Fewer than twelve complete review horizons are available.",
  "outer-selector-did-not-beat-hold": "The adaptive strategy did not outperform unchanged HOLD after costs in the later historical periods.",
  "outer-selector-did-not-beat-costed-cad": "The adaptive strategy did not outperform the costed CAD strategy in the later historical periods.",
  "no-positive-inner-edge-over-both-baselines": "The latest earlier-period comparison found no momentum window that beat both baselines.",
  "no-positive-current-paired-mean-advantage": "The current hypothetical shift has no positive average advantage over HOLD in its completed historical samples.",
  "engineering-evidence-gates-passed-still-unvalidated": "The configured evidence checks passed. The strategy remains experimental and has no independent validation.",
};

export function StrategyPanel({ portfolio, holdings, planState, now, disabled, request, onState, onQuote, onHold }: Props) {
  const [allocation, setAllocation] = useState("");
  const [slippage, setSlippage] = useState("");
  const [study, setStudy] = useState<Development | null>(null);
  const [recommendation, setRecommendation] = useState<Development | null>(null);
  const [working, setWorking] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let live = true;
    async function restore() {
      try {
        const { trials } = await request<{ trials: StrategyTrialSummary[] }>("trials?strategy=1");
        const savedStudy = trials.find(row => row.kind === "development" && row.purpose === "study");
        const savedRecommendation = trials.find(row => row.kind === "development" && row.purpose === "recommendation");
        const records = await Promise.all([savedStudy, savedRecommendation].map(row => row ? request<{ trial: StrategyTrial }>(`trials?id=${encodeURIComponent(row.id)}&strategy=1`) : null));
        if (!live) return;
        if (records[0]?.trial.kind === "development") {
          const restored = records[0].trial;
          setStudy(restored);
          setAllocation(value => value || String(restored.data.report.config.riskPercent));
          setSlippage(value => value || String(restored.data.report.config.slippageBps));
        }
        if (records[1]?.trial.kind === "development") setRecommendation(records[1].trial);
      } catch (reason) { if (live) setError(reason instanceof Error ? reason.message : "Saved strategy could not be loaded."); }
      finally { if (live) setLoaded(true); }
    }
    void restore();
    return () => { live = false; };
  }, [portfolio.id, request]);

  async function perform(label: string, operation: () => Promise<void>) {
    setWorking(label); setError(""); setMessage("");
    try { await operation(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Strategy request failed."); }
    finally { setWorking(""); }
  }
  async function post(data: unknown, kind: "protocol" | "development") {
    return (await request<{ trial: StrategyTrial }>("trials", { id: crypto.randomUUID(), kind, data })).trial;
  }
  function build(event: FormEvent) {
    event.preventDefault();
    void perform("Backtesting the five windows…", async () => {
      if (!allocation.trim() || !slippage.trim()) throw new Error("Enter your target allocation and slippage assumption.");
      const protocol = await post({ namespace: "strategy", protocolVersion: STRATEGY_STUDY_VERSION, config: { riskPercent: Number(allocation), slippageBps: Number(slippage) }, expectedRevision: portfolio.revision }, "protocol");
      const result = await post({ namespace: "strategy", purpose: "study", protocolId: protocol.id }, "development");
      if (result.kind !== "development" || result.data.purpose !== "study") throw new Error("The server did not return a completed strategy study.");
      setStudy(result); setRecommendation(null);
      setMessage("Backtest saved. Review the evidence, then use this strategy to build your current plan.");
    });
  }
  async function refresh(state = planState) {
    const result = await post({ namespace: "strategy", purpose: "recommendation", expectedRevision: portfolio.revision, expectedPlanRevision: state.planRevision }, "development");
    if (result.kind !== "development" || result.data.purpose !== "recommendation") throw new Error("The server did not return a current recommendation.");
    setRecommendation(result);
    setMessage("Recommendation saved against your current holdings. Review each paper action yourself.");
  }
  function adopt() {
    if (!study) return;
    void perform("Saving strategy and preparing your plan…", async () => {
      const result = await request<{ portfolio: Portfolio; planState: StrategyPlanState }>("action", { kind: "adoptPlan", studyId: study.id, expectedRevision: portfolio.revision, expectedPlanRevision: planState.planRevision });
      onState(result);
      await refresh(result.planState);
    });
  }

  const busy = disabled || Boolean(working);
  const activeStudy = study ?? planState.study;
  const adopted = Boolean(activeStudy && planState.activePlanId === activeStudy.id);
  const current = adopted && recommendation?.data.planId === planState.activePlanId ? recommendation : null;
  const currentData = current?.data;
  const stale = Boolean(currentData && (currentData.portfolioRevision !== portfolio.revision || currentData.planRevision !== planState.planRevision || !currentData.expiresAt || Date.parse(currentData.expiresAt) <= now));
  const report = currentData?.report ?? activeStudy?.data.report;
  const plan = report?.plan;
  const decision = currentData?.decision;
  const paired = plan?.paired;
  const continuing = Boolean(currentData?.rebalance && decision === "shift" && (!plan?.reviewDue || currentData.rebalance.stepsCompleted > 0));
  const targetWeights = currentData ? (decision === "hold" ? null : currentData.rebalance?.targetWeights ?? plan?.targetWeights) : plan?.targetWeights;
  const canAdopt = activeStudy && !adopted && activeStudy.data.portfolioRevision === portfolio.revision;

  return <section className="space-y-5" aria-labelledby="rotation-strategy-title">
    <div className={`${ROTATION_STYLE.panel} rotation-strategy-panel`}>
      <div className="flex flex-wrap justify-between items-start gap-3"><div><p className="text-xs tracking-widest uppercase text-emerald-300 mb-2">Your strategy</p><h2 id="rotation-strategy-title" className="text-xl font-semibold">{activeStudy ? "A saved strategy. A clear next decision." : "Set your allocation. The program does the backtesting."}</h2></div><span className="rounded border border-amber-400/50 px-3 py-1 text-xs text-amber-200">Experimental · unvalidated</span></div>
      <p className={`${ROTATION_STYLE.muted} mt-3`}>Compare 14, 30, 60, 90 and 180-day momentum windows with unchanged HOLD and a costed CAD strategy. Completed earlier periods select a momentum window every 60 days; your saved cadence determines trading reviews.</p>
      <div className="flex flex-wrap gap-x-5 gap-y-2 text-xs text-slate-300 mt-4"><span>Current portfolio: {portfolio.name}</span><span className="capitalize">{portfolio.cadence} reviews</span><span>{portfolio.feeBps} bps fee per leg</span><span>Current recommendation: your saved holdings</span></div>
      <form onSubmit={build} className="mt-5 space-y-4">
        <div className="grid sm:grid-cols-2 gap-4"><label>Target crypto allocation when shifting (%)<input className="rotation-input" type="number" min="0" max="100" step="any" required value={allocation} onChange={event => setAllocation(event.target.value)} /><span className="block text-xs text-slate-300 mt-2">HOLD keeps units unchanged, so weights can drift. This is not a loss limit.</span></label><label>Adverse slippage (bps)<input className="rotation-input" type="number" min="0" max="1000" step="any" required value={slippage} onChange={event => setSlippage(event.target.value)} /><span className="block text-xs text-slate-300 mt-2">Extra cost allowance in addition to your saved trading fee.</span></label></div>
        <button className="rotation-primary" disabled={busy || !loaded}>{working || "Backtest & build my plan"}</button>
      </form>
      {!loaded && <p role="status" className="mt-3 text-sm text-slate-300">Loading your saved strategy…</p>}
      {error && <p role="alert" className="rotation-error mt-4">{error}</p>}
      {message && <p role="status" className="rotation-note mt-4">{message}</p>}
      {activeStudy && <div className="mt-5 border-t border-white/10 pt-4 flex flex-wrap items-center gap-3"><button className="rotation-primary" disabled={busy || !canAdopt} onClick={adopt}>{adopted ? "Strategy in use" : "Use this strategy"}</button>{adopted && <button className="rotation-secondary" disabled={busy} onClick={() => void perform("Updating recommendation…", () => refresh())}>Refresh recommendation</button>}{!adopted && planState.study && <button className="rotation-secondary" disabled={busy} onClick={() => setStudy(planState.study)}>View active strategy</button>}<p className="text-xs text-slate-300">{!adopted && !canAdopt ? "Your holdings changed. Run a new study before adopting it." : `Study saved ${eastern(activeStudy.created_at)} ET. Adoption does not trade.`}</p></div>}
    </div>

    {report && plan && <div className={ROTATION_STYLE.panel}>
      <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs text-emerald-300 uppercase tracking-widest mb-2">{current ? "Your plan for this review" : "Completed study"}</p><h3 className="text-xl font-semibold">{current ? decision === "hold" ? "HOLD — keep your current units" : decision === "shift" ? continuing ? `Continue the target reviewed ${currentData?.rebalance?.reviewDate}` : "SHIFT — review the next paper step" : "No executable quote is ready" : "Backtest complete — review and adopt"}</h3></div><span className="text-xs text-amber-200">Retrospective · not independently validated</span></div>
      <p className="mt-3 text-sm text-slate-300">Adaptive momentum selection · Latest choice: {nameOf(plan.candidateId)} · {plan.horizonStart} → {plan.horizonEnd}</p><p className="mt-2 text-sm text-slate-300">Next scheduled review: {plan.nextReviewDate}{plan.reviewDue ? " · Due today" : " · HOLD between reviews"}</p>
      {continuing && <p className="rotation-note mt-4">Finish the saved {currentData?.rebalance?.target} target from {currentData?.rebalance?.reviewDate}, one approved step at a time. Today’s research below is separate from that unfinished review.</p>}<ul className="mt-4 space-y-2 text-sm text-slate-200">{plan.reasons.map(reason => <li key={reason}>{REASONS[reason] ?? reason.replaceAll("-", " ")}</li>)}</ul>
      {continuing && currentData?.rebalance?.reviewExpiresAt && <p className="mt-3 text-sm text-slate-300">This reviewed target expires {eastern(currentData.rebalance.reviewExpiresAt)} ET.</p>}
      {currentData?.executionNote && <p className="rotation-note mt-4">{currentData.executionNote}</p>}
      {stale && <p role="status" className="rotation-error mt-4">This recommendation expired or your portfolio or plan changed. Refresh recommendation before acting.</p>}
      <h4 className="font-semibold mt-6">{continuing ? "Current research scenario · separate from the continuing target" : plan.status === "hold" ? "Rejected candidate scenario" : "Historical outcomes for this review horizon"}</h4>{plan.status === "hold" && (!currentData || decision === "hold") && <p className="text-sm text-slate-300 mt-2">The shift below is hypothetical and failed the strategy’s evidence gates. Your recommended action is HOLD: keep every current unit unchanged.</p>}
      {paired ? <><div className="grid md:grid-cols-3 gap-3 mt-4">{[[`Shift to ${paired.target}`, paired.shift], ["HOLD", paired.hold], ["Shift minus HOLD", paired.advantage]].map(([label, value]) => {
        const outcome = value as typeof paired.shift;
        return <article className="rounded-lg border border-white/10 bg-black/15 p-4" key={label as string}><h5 className="font-semibold">{label as string}</h5><dl className="mt-3 space-y-3 text-sm"><div><dt className="text-slate-300">Historical mean profit / loss</dt><dd className="text-xl font-semibold tabular-nums mt-1">{cad(outcome.meanCad)}</dd></div><div className="flex flex-wrap justify-between gap-2"><dt className="text-slate-300">Downside · 10th percentile</dt><dd className="font-medium tabular-nums">{cad(outcome.downside10Cad)}</dd></div><div className="flex flex-wrap justify-between gap-2"><dt className="text-slate-300">90th percentile</dt><dd className="font-medium tabular-nums">{cad(outcome.upper90Cad)}</dd></div></dl></article>;
      })}</div><p className="text-xs text-slate-300 mt-3">{paired.observations} completed historical samples. Values include modeled costs. The downside percentile is not a maximum loss or a calibrated forecast.</p></> : <p className="rotation-note mt-3">There are not enough completed samples for a paired estimate. No outcome is invented.</p>}
      <h4 className="font-semibold mt-6">{targetWeights ? "Indicative target portfolio, in CAD" : "HOLD keeps these current units"}</h4>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mt-3">{ASSETS.map(asset => { const holding = holdings.find(row => row.asset === asset); return <div key={asset} className="rounded-lg border border-white/10 bg-black/15 p-4"><h5 className="text-sm text-emerald-300 font-semibold">{asset}</h5><p className="mt-2 font-semibold tabular-nums">{targetWeights ? cad(targetWeights[asset] * plan.startingValueCad) : holding ? cad(holding.valueCad) : "—"}</p><p className="text-xs text-slate-300 mt-2">Current {portfolio.balances[asset]} units</p></div>; })}</div>
      {targetWeights && <p className="mt-3 text-xs text-slate-300">CAD targets illustrate the saved target weights. Exact execution amounts and fees come from each fresh quote.</p>}
      {current && <div className="mt-6 border-t border-white/10 pt-5"><h4 className="font-semibold">Next paper action</h4>{decision === "shift" && currentData?.nextShift ? <><p className="text-sm text-slate-300 mt-2">Step {(currentData.rebalance?.stepsCompleted ?? 0) + 1}: {currentData.nextShift.amount} {currentData.nextShift.from} → {currentData.nextShift.to}. Complete this step, then refresh the recommendation from your updated holdings.</p><button className="rotation-primary mt-4" disabled={busy || stale} onClick={() => void perform("Preparing a fresh quote…", () => onQuote(current))}>Review fresh quote</button></> : decision === "hold" ? <button className="rotation-primary mt-3" disabled={busy || stale} onClick={() => void perform("Recording HOLD…", () => onHold(current))}>Record recommended HOLD</button> : <p className="text-sm text-slate-300 mt-3">Refresh when the quoted constraints can be satisfied. A blocked shift is not a model recommendation to HOLD.</p>}<p className="text-xs text-slate-300 mt-3">No automatic or batch execution. Every shift still needs your approval of the existing costed preview.</p></div>}
      <details className="mt-6 border-t border-white/10 pt-4 text-sm"><summary className="cursor-pointer font-semibold">Strategy rules, candidate results & complete backtest evidence</summary><div className="mt-4 space-y-4"><p className="text-slate-300">Historical backtests begin with an equal crypto basket at your target allocation and the remainder in CAD; this benchmark is separate from your current saved holdings. History {report.coverageStart} → {report.coverageEnd}. Selection uses completed earlier periods; the historical data was already exposed. {report.plan.outerCompletedBlocks} complete outer blocks, {report.plan.outerCompletedReviews} complete review horizons.</p><div className="grid sm:grid-cols-3 gap-3">{[["Adaptive strategy", report.outer.metrics.finalCad], ["Unchanged HOLD", report.outer.metrics.holdCad], ["Costed CAD", report.outer.metrics.cashCad]].map(([label, amount]) => <div key={label as string}><p className="text-slate-300">{label as string}</p><p className="font-semibold mt-1">{cad(amount as number)}</p></div>)}</div><p className="text-slate-300">Outer fees {cad(report.outer.metrics.feesCad)} · {report.outer.metrics.trades} executed legs · worst drawdown {report.outer.metrics.maxDrawdownPercent.toFixed(2)}%.</p><div className="grid sm:grid-cols-2 gap-3">{report.candidates.map(candidate => <article className="rounded-lg border border-white/10 p-4" key={candidate.candidateId}><h5 className="font-semibold">{nameOf(candidate.candidateId)}</h5><dl className="mt-3 space-y-2 text-xs">{[["Ending value", cad(candidate.metrics.finalCad)], ["Versus HOLD", cad(candidate.metrics.excessHoldCad)], ["Versus CAD", cad(candidate.metrics.excessCashCad)], ["Fees", cad(candidate.metrics.feesCad)], ["Worst drawdown", `${candidate.metrics.maxDrawdownPercent.toFixed(2)}%`]].map(([label, value]) => <div className="flex flex-wrap justify-between gap-2" key={label}><dt className="text-slate-300">{label}</dt><dd className="tabular-nums">{value}</dd></div>)}</dl></article>)}</div><p className="text-xs text-slate-300">Candidate results are descriptive comparisons, not an independently chosen outer-period winner. The saved procedure reselects the momentum window every 60 days and reviews its trading signal on your weekly or monthly cadence.</p>{report.notes.map(note => <p className="text-xs text-slate-300" key={note}>{note}</p>)}</div></details>
    </div>}
  </section>;
}
