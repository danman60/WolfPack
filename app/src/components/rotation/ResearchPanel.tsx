"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ROTATION_STYLE, cad, eastern, type MarketSnapshot, type Portfolio, type ResearchConfig } from "@/lib/rotation/contract";
import { RESEARCH_VERSION, type ResearchProtocol, type ResearchTrial, type ResearchTrialSummary, type ValidationReport } from "@/lib/rotation/research-contract";

type Props = { portfolio: Portfolio | null; market: MarketSnapshot | null; active?: boolean; onTrial?: (trial: ResearchTrial) => void | Promise<void> };
type FormValues = { capitalCad: string; cadence: string; lookbackDays: string; riskPercent: string; feeBps: string; slippageBps: string };
const emptyForm: FormValues = { capitalCad: "", cadence: "", lookbackDays: "", riskPercent: "", feeBps: "", slippageBps: "" };

async function responseJson<T>(response: Response): Promise<T> {
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || `Request failed (${response.status}).`);
  return body as T;
}

export function ResearchPanel({ portfolio, active = true, onTrial }: Props) {
  const [form, setForm] = useState<FormValues>(emptyForm);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [report, setReport] = useState<ValidationReport | null>(null);
  const [protocol, setProtocol] = useState<ResearchProtocol | null>(null);
  const [trials, setTrials] = useState<ResearchTrialSummary[]>([]);
  const [savedMessage, setSavedMessage] = useState("");
  const [holdoutResult, setHoldoutResult] = useState<Extract<ResearchTrial["data"], { folds: unknown }> | null>(null);

  const restoreTrial = useCallback(async (id: string) => {
    const { trial } = await responseJson<{ trial: ResearchTrial }>(await fetch(`/api/rotation/trials?id=${encodeURIComponent(id)}`, { cache: "no-store" }));
    let frozen: ResearchProtocol;
    if ("protocolId" in trial.data) {
      const registered = await responseJson<{ trial: ResearchTrial }>(await fetch(`/api/rotation/trials?id=${encodeURIComponent(trial.data.protocolId)}`, { cache: "no-store" }));
      if (!("config" in registered.trial.data)) throw new Error("Saved protocol is incomplete.");
      frozen = registered.trial.data;
    } else frozen = trial.data;
    setProtocol(frozen);
    setForm({ capitalCad: String(frozen.config.capitalCad), cadence: frozen.config.cadence, lookbackDays: String(frozen.config.lookbackDays), riskPercent: String(frozen.config.riskPercent), feeBps: String(frozen.config.feeBps), slippageBps: String(frozen.config.slippageBps) });
    setReport("report" in trial.data ? trial.data.report : null);
    setHoldoutResult("folds" in trial.data ? trial.data : null);
    setSavedMessage(`Loaded saved ${trial.kind} and its frozen scenario inputs.`);
  }, []);

  useEffect(() => {
    if (!portfolio) return;
    setForm((current) => ({ ...current,
      capitalCad: current.capitalCad || portfolio.initialValueCad,
      cadence: current.cadence || portfolio.cadence,
      feeBps: current.feeBps || String(portfolio.feeBps),
    }));
  }, [portfolio]);

  useEffect(() => {
    let active = true;
    fetch("/api/rotation/trials", { cache: "no-store" }).then((response) => responseJson<{ trials: ResearchTrialSummary[] }>(response))
      .then(async (body) => {
        if (!active) return;
        setTrials(body.trials);
        const latest = body.trials.find((trial) => trial.kind === "development") ?? body.trials[0];
        if (latest) await restoreTrial(latest.id);
      })
      .catch((reason) => { if (active) setError(reason instanceof Error ? reason.message : "Trial registry could not be loaded."); });
    return () => { active = false; };
  }, [restoreTrial]);

  async function refreshTrials() {
    const response = await responseJson<{ trials: ResearchTrialSummary[] }>(await fetch("/api/rotation/trials", { cache: "no-store" }));
    setTrials(response.trials);
  }

  async function postTrial(kind: ResearchTrial["kind"], data: unknown): Promise<ResearchTrial> {
    const { trial } = await responseJson<{ trial: ResearchTrial }>(await fetch("/api/rotation/trials", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id: crypto.randomUUID(), kind, data }),
    }));
    await onTrial?.(trial);
    return trial;
  }

  async function run(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setError(""); setSavedMessage(""); setHoldoutResult(null); setReport(null);
    try {
      for (const [key, text] of Object.entries(form)) if (!text.trim()) throw new Error(`Enter ${key.replace(/([A-Z])/g, " $1").toLowerCase()}.`);
      const config: ResearchConfig = { capitalCad: Number(form.capitalCad), cadence: form.cadence as ResearchConfig["cadence"], lookbackDays: Number(form.lookbackDays), riskPercent: Number(form.riskPercent), feeBps: Number(form.feeBps), slippageBps: Number(form.slippageBps) };
      // Archive and register BEFORE evaluating. The server computes the hash and
      // future dates, then computes results from this immutable archived input.
      const registration = await postTrial("protocol", { protocolVersion: RESEARCH_VERSION, config });
      setProtocol(registration.data as ResearchProtocol);
      const evaluation = await postTrial("development", { protocolId: registration.id });
      if (!("report" in evaluation.data)) throw new Error("The saved trial has no evaluation report.");
      setReport(evaluation.data.report);
      setSavedMessage("Protocol and evaluated trial saved. This protocol’s future scoring endpoint remains sealed.");
      await refreshTrials();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Research could not be completed.");
      // A registered protocol remains in the append-only history even if its
      // evaluation failed. Never erase failed/abandoned trial evidence.
      await refreshTrials().catch(() => undefined);
    } finally { setBusy(false); }
  }

  async function openHoldout(protocolId: string) {
    setBusy(true); setError("");
    try {
      const trial = await postTrial("holdout", { protocolId });
      if (!("folds" in trial.data)) throw new Error("Holdout response is incomplete.");
      setHoldoutResult(trial.data);
      setSavedMessage("Registered prospective evaluation opened and recorded. Subsequent tuning needs a new future registration.");
      await refreshTrials();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Holdout could not be opened."); }
    finally { setBusy(false); }
  }

  async function viewTrial(id: string) {
    setBusy(true); setError("");
    try {
      await restoreTrial(id);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Saved trial could not be loaded."); }
    finally { setBusy(false); }
  }

  const forecast = report?.forecast;
  return <section className="space-y-5" aria-labelledby="rotation-research-title">
    <div className={ROTATION_STYLE.panel}>
      <div className="flex flex-wrap items-center justify-between gap-3"><h2 id="rotation-research-title" className={ROTATION_STYLE.title}>Historical research & future validation</h2><span className="rounded border border-amber-400/50 px-3 py-1 text-xs text-amber-200">Experimental · unvalidated</span></div>
      <p className={`${ROTATION_STYLE.muted} mt-3`}>Compare one disclosed momentum rule with unchanged holdings using real Kraken spot history. Enter your scenario. Each run saves its inputs, source data and result in your account’s trial registry.</p>
      <form onSubmit={run} className="mt-5 space-y-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <label>Historical scenario capital (CAD)<input className="rotation-input" required inputMode="decimal" type="number" min="0.01" step="any" value={form.capitalCad} onChange={(e) => setForm({ ...form, capitalCad: e.target.value })} /></label>
          <label>Review cadence<select className="rotation-input" required value={form.cadence} onChange={(e) => setForm({ ...form, cadence: e.target.value })}><option value="">Choose cadence</option><option value="weekly">Weekly</option><option value="monthly">Calendar monthly</option></select></label>
          <label>Lookback (14–180 calendar days)<input className="rotation-input" required inputMode="numeric" type="number" min="14" max="180" step="1" value={form.lookbackDays} onChange={(e) => setForm({ ...form, lookbackDays: e.target.value })} /></label>
          <label>Crypto allocation (0–100%)<input className="rotation-input" required inputMode="decimal" type="number" min="0" max="100" step="any" value={form.riskPercent} onChange={(e) => setForm({ ...form, riskPercent: e.target.value })} /></label>
          <label>Fee per leg (basis points)<input className="rotation-input" required inputMode="decimal" type="number" min="0" max="1000" step="any" value={form.feeBps} onChange={(e) => setForm({ ...form, feeBps: e.target.value })} /></label>
          <label>Adverse slippage (basis points)<input className="rotation-input" required inputMode="decimal" type="number" min="0" max="1000" step="any" value={form.slippageBps} onChange={(e) => setForm({ ...form, slippageBps: e.target.value })} /></label>
        </div>
        <p className="text-xs leading-relaxed text-slate-300">100 basis points = 1%. Portfolio capital, cadence and fee are copied only from your entered portfolio. Other fields stay empty until chosen. Allocation is an experiment parameter, not a loss limit. No parameter search is performed.</p>
        <button type="submit" disabled={busy} className="rotation-primary cursor-pointer">{busy ? "Saving and evaluating…" : "Register scenario & run research"}</button>
      </form>
      {error && <p className="rotation-error mt-4" role="alert">{error}</p>}
      {savedMessage && <p className="mt-4 text-sm text-emerald-200" role="status">{savedMessage}</p>}
    </div>

    {forecast && <div className={ROTATION_STYLE.panel}>
      <h3 className={ROTATION_STYLE.title}>Shift to {forecast.target} versus HOLD</h3>
      <p className={`${ROTATION_STYLE.muted} mt-2`}>{forecast.start} → {forecast.horizonEnd}. {forecast.observations} completed historical horizon samples. Starting value {cad(forecast.startingValueCad)}.</p>
      <p className="mt-2 text-sm text-slate-300">{forecast.basis === "entered-portfolio" ? "Both scenarios use the portfolio units and public quote midpoints saved at registration." : "Both scenarios start with the disclosed equal-basket research endowment at historical reference closes."} Signal data through {forecast.signalThrough}; outcome samples through {forecast.trainingThrough}.</p>
      <div className="mt-4 space-y-3 sm:hidden" aria-label="Unvalidated historical scenario outcomes in CAD">
        {[["Shift", forecast.shift], ["HOLD", forecast.hold], ["Shift minus HOLD", forecast.advantage]].map(([label, row]) => {
          const outcome = row as typeof forecast.shift;
          return <article key={label as string} className="rounded-lg border border-white/10 bg-black/15 p-4">
            <h4 className="text-sm font-semibold text-white">{label as string}</h4>
            <dl className="mt-3 space-y-3 text-sm">
              {[["Historical mean", outcome.meanCad], ["Downside · 10th percentile", outcome.downside10Cad], ["90th percentile", outcome.upper90Cad]].map(([metric, amount]) => <div key={metric as string} className="flex flex-wrap justify-between gap-x-3 gap-y-1"><dt className="text-slate-300">{metric as string}</dt><dd className="min-w-0 break-all font-medium tabular-nums text-white">{cad(amount as number)}</dd></div>)}
            </dl>
          </article>;
        })}
      </div>
      <div className={`${ROTATION_STYLE.tableWrap} mt-4 hidden sm:block`}><table className={ROTATION_STYLE.table} aria-label="Unvalidated historical scenario outcomes in CAD"><thead><tr>{["One-horizon profit / loss", "Historical mean", "Downside: 10th percentile", "90th percentile"].map((label) => <th key={label} className={ROTATION_STYLE.cell}>{label}</th>)}</tr></thead><tbody>
        {[["Shift", forecast.shift], ["HOLD", forecast.hold], ["Shift minus HOLD", forecast.advantage]].map(([label, row]) => { const outcome = row as typeof forecast.shift; return <tr key={label as string}><th className={ROTATION_STYLE.cell}>{label as string}</th><td className={ROTATION_STYLE.cell}>{cad(outcome.meanCad)}</td><td className={ROTATION_STYLE.cell}>{cad(outcome.downside10Cad)}</td><td className={ROTATION_STYLE.cell}>{cad(outcome.upper90Cad)}</td></tr>; })}
      </tbody></table></div>
      <p className="rotation-note mt-4"><strong>{forecast.advantage.meanCad <= 0 ? "This historical estimate favors HOLD after costs. " : "This historical estimate favors the shift, but remains unvalidated. "}</strong>These averages describe past samples, not dependable expected profit. The downside percentile is not a maximum loss. No order is proposed for automatic execution.</p>
      <details className="mt-4 text-sm text-slate-300"><summary className="cursor-pointer">Scenario method and limits</summary><p className="mt-3 leading-relaxed">{forecast.note}</p></details>
    </div>}

    {report && <>
      <div className={ROTATION_STYLE.panel}><h3 className={ROTATION_STYLE.title}>Chronological evaluation</h3><p className={`${ROTATION_STYLE.muted} mt-2`}>Initial training prefix: {report.trainingStart} → the day before {report.firstTestDate}. Each later review estimates outcomes from earlier completed horizons only. The final historical tail was already exposed and is not an untouched test.</p>
        <div className="mt-4 space-y-3 sm:hidden" aria-label="Chronological evaluation periods">{report.folds.map((row) => <article key={row.start} className="rounded-lg border border-white/10 bg-black/15 p-4">
          <h4 className="flex flex-wrap gap-x-2 text-sm font-semibold text-white"><span>{row.start}</span><span>→ {row.end}</span></h4>
          <p className="mt-1 text-xs text-slate-300">{row.kind === "exposed-tail" ? "Previously exposed final tail" : "Expanding walk-forward"}</p>
          <dl className="mt-4 space-y-3 text-sm">
            {[["Complete decisions", String(row.decisions)], ["Mean shift advantage", row.meanAdvantageCad === null ? "Insufficient horizons" : cad(row.meanAdvantageCad)], ["Mean forecast error", row.meanAbsoluteErrorCad === null ? "—" : cad(row.meanAbsoluteErrorCad)], ["Observed interval coverage", row.intervalCoveragePercent === null ? "—" : `${row.intervalCoveragePercent.toFixed(1)}%`]].map(([metric, amount]) => <div key={metric} className="flex flex-wrap justify-between gap-x-3 gap-y-1"><dt className="text-slate-300">{metric}</dt><dd className="min-w-0 break-all font-medium tabular-nums text-white">{amount}</dd></div>)}
          </dl>
        </article>)}</div>
        <div className={`${ROTATION_STYLE.tableWrap} mt-4 hidden sm:block`}><table className={ROTATION_STYLE.table}><thead><tr>{["Period", "Decisions", "Mean shift advantage", "Mean forecast error", "Observed interval coverage"].map((label) => <th key={label} className={ROTATION_STYLE.cell}>{label}</th>)}</tr></thead><tbody>{report.folds.map((row) => <tr key={row.start}><th className={ROTATION_STYLE.cell}><span className="block whitespace-nowrap">{row.start} → {row.end}</span><span className="mt-1 block text-xs font-normal text-slate-300">{row.kind === "exposed-tail" ? "Previously exposed final tail" : "Expanding walk-forward"}</span></th><td className={ROTATION_STYLE.cell}>{row.decisions}</td><td className={ROTATION_STYLE.cell}>{row.meanAdvantageCad === null ? "Insufficient horizons" : cad(row.meanAdvantageCad)}</td><td className={ROTATION_STYLE.cell}>{row.meanAbsoluteErrorCad === null ? "—" : cad(row.meanAbsoluteErrorCad)}</td><td className={ROTATION_STYLE.cell}>{row.intervalCoveragePercent === null ? "—" : `${row.intervalCoveragePercent.toFixed(1)}%`}</td></tr>)}</tbody></table></div>
        <p className="mt-3 text-xs leading-relaxed text-slate-300">Coverage measures how often the subsequent net advantage fell inside the earlier samples’ 10–90% range. It is not a confidence score. Horizon outcomes crossing a fold boundary are excluded from that fold. Each decision starts a fresh matched basket; these row averages are not additive portfolio profit.</p>
        <details className="mt-4 text-sm text-slate-300"><summary className="cursor-pointer">Validation protocol</summary><p className="mt-3 leading-relaxed">{report.note}</p></details>
      </div>
      <div className={ROTATION_STYLE.panel}><h3 className={ROTATION_STYLE.title}>Continual replay versus unchanged holdings</h3><div className="mt-4 grid grid-cols-2 gap-4 lg:grid-cols-4">{[["Strategy", cad(report.replay.finalCad)], ["Unchanged HOLD", cad(report.replay.holdCad)], ["Net difference", cad(report.replay.incrementalCad)], ["Worst daily drawdown", `${report.replay.maxDrawdownPercent.toFixed(2)}%`]].map(([label, amount]) => <div key={label}><p className={ROTATION_STYLE.label}>{label}</p><p className="mt-2 text-xl font-semibold text-white">{amount}</p></div>)}</div>
        <div className="rotation-chart mt-6" aria-label="Historical strategy and unchanged holdings value in CAD">{active && <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 640, height: 280 }}><LineChart data={report.replay.points}><CartesianGrid stroke="#344155" strokeDasharray="3 3" /><XAxis dataKey="date" stroke="#b8c4d8" minTickGap={50} tick={{ fontSize: 11 }} /><YAxis stroke="#b8c4d8" width={74} tickFormatter={(amount: number) => `$${Math.round(amount).toLocaleString("en-CA")}`} tick={{ fontSize: 11 }} /><Tooltip contentStyle={{ background: "#111a2e", border: "1px solid #526078", color: "#e4e7eb" }} formatter={(amount) => cad(Number(amount))} /><Legend wrapperStyle={{ fontSize: 12, paddingTop: 12 }} /><Line name="Strategy" type="linear" dataKey="strategyCad" stroke="#34d399" dot={false} strokeWidth={2} isAnimationActive={false} /><Line name="Unchanged HOLD" type="linear" dataKey="holdCad" stroke="#93c5fd" dot={false} strokeWidth={2} isAnimationActive={false} /></LineChart></ResponsiveContainer>}</div>
        <p className="mt-3 text-sm text-slate-300">{report.replay.trades} executed legs · {cad(report.replay.feesCad)} in fees · {report.replay.start} → {report.replay.end}. Both paths start with the same equal-basket endowment.</p><details className="mt-4 text-sm text-slate-300"><summary className="cursor-pointer">Replay costs, chronology and data provenance</summary><p className="mt-3 leading-relaxed">{report.replay.note}</p></details>
      </div>
    </>}

    <div className={ROTATION_STYLE.panel}><h3 className={ROTATION_STYLE.title}>Registered prospective evaluation & trial history</h3>
      <p className={`${ROTATION_STYLE.muted} mt-2`}>Each scenario freezes its rule before a future 12-calendar-month period. Its scoring endpoint stays sealed until all those daily observations exist. Other later trials can expose overlapping data, so this is not a guaranteed account-wide untouched test. Changing the rule requires a new future registration.</p>
      <p className="mt-3 text-xs leading-relaxed text-slate-300">Independent statistical validation remains unfinished. A changed evaluator or compiler fingerprint blocks scoring an old protocol; its saved reports remain readable.</p>
      {protocol && <p className="rotation-note mt-4">Registered future period: {protocol.forwardHoldoutStart} → {protocol.forwardHoldoutEnd}. Historical source SHA-256: <span className="break-all font-mono text-xs">{protocol.sourceHash}</span>.</p>}
      {trials.length === 0 ? <p className="mt-4 text-sm text-slate-300">No trial records loaded. Your first run registers its inputs before evaluation.</p> : <>
        <div className="mt-4 space-y-3 sm:hidden" aria-label="Saved research records">{trials.map((trial) => <article key={trial.id} className="rounded-lg border border-white/10 bg-black/15 p-4">
          <h4 className="text-sm font-semibold text-white">{trial.kind === "protocol" ? "Frozen protocol" : trial.kind === "holdout" ? "Holdout opened" : "Historical evaluation"}</h4>
          <p className="mt-2 text-xs leading-relaxed text-slate-300">Saved {eastern(trial.created_at)} ET</p>
          <p className="mt-2 break-all font-mono text-xs text-slate-300">{trial.id}</p>
          {trial.kind === "protocol" ? <div className="mt-4 text-sm text-slate-300"><p className="text-xs uppercase tracking-wide">Registered future period</p><p className="mt-1 flex flex-wrap gap-x-2 font-medium text-white"><span>{trial.forwardHoldoutStart}</span><span>→ {trial.forwardHoldoutEnd}</span></p></div> : <p className="mt-3 text-xs text-slate-300">Recorded and immutable</p>}
          <div className="mt-4 grid gap-2"><button type="button" className="rotation-secondary w-full cursor-pointer text-sm" disabled={busy} onClick={() => void viewTrial(trial.id)}>View saved record</button>{trial.kind === "protocol" && <button type="button" disabled={busy} className="rotation-secondary w-full cursor-pointer text-sm" onClick={() => void openHoldout(trial.id)}>Check holdout eligibility</button>}</div>
        </article>)}</div>
        <div className={`${ROTATION_STYLE.tableWrap} mt-4 hidden sm:block`}><table className={ROTATION_STYLE.table}><thead><tr><th className={ROTATION_STYLE.cell}>Saved (Eastern)</th><th className={ROTATION_STYLE.cell}>Record</th><th className={ROTATION_STYLE.cell}>Future period</th></tr></thead><tbody>{trials.map((trial) => <tr key={trial.id}><td className={`${ROTATION_STYLE.cell} whitespace-nowrap`}>{eastern(trial.created_at)}</td><td className={ROTATION_STYLE.cell}><span className="block">{trial.kind === "protocol" ? "Frozen protocol" : trial.kind === "holdout" ? "Holdout opened" : "Historical evaluation"}</span><span className="font-mono text-xs text-slate-300">{trial.id.slice(0, 8)}</span><button type="button" className="rotation-secondary mt-2 block cursor-pointer text-xs" disabled={busy} onClick={() => void viewTrial(trial.id)}>View saved record</button></td><td className={ROTATION_STYLE.cell}>{trial.kind === "protocol" ? <><span className="block whitespace-nowrap">{trial.forwardHoldoutStart} → {trial.forwardHoldoutEnd}</span><button type="button" disabled={busy} className="rotation-secondary mt-2 cursor-pointer text-xs" onClick={() => void openHoldout(trial.id)}>Check holdout eligibility</button></> : "Recorded and immutable"}</td></tr>)}</tbody></table></div>
      </>}
      {holdoutResult && <div className="rotation-note mt-4">{holdoutResult.folds.map((row) => <p key={row.start}>{row.start} → {row.end}: {row.decisions} decisions, mean paired advantage {row.meanAdvantageCad === null ? "insufficient evidence" : cad(row.meanAdvantageCad)}.</p>)}<p className="mt-2">{holdoutResult.note}</p></div>}
    </div>
  </section>;
}
