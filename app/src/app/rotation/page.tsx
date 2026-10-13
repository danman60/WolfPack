"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { ActivityList } from "@/components/rotation/ActivityList";
import { HoldingsTable } from "@/components/rotation/HoldingsTable";
import { MetricCard } from "@/components/rotation/MetricCard";
import { ResearchPanel } from "@/components/rotation/ResearchPanel";
import { ASSETS, cad, eastern, ROTATION_STYLE, type Amounts, type Asset, type Cadence, type MarketSnapshot, type Portfolio, type ShiftPreview } from "@/lib/rotation/contract";
import { holdingRows, performance } from "@/lib/rotation/engine";
import "./rotation.css";

type Session = { authenticated: boolean; user: { id: string; email: string; demo: boolean } | null; demoEnabled: boolean };
async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api/rotation/${path}`, { method: body === undefined ? "GET" : "POST", headers: body === undefined ? undefined : { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body), cache: "no-store" });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `Request failed (${response.status}).`);
  return payload as T;
}

export default function RotationPage() {
  const [session, setSession] = useState<Session | null>(null);
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [market, setMarket] = useState<MarketSnapshot | null>(null);
  const [marketError, setMarketError] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState<"workspace" | "research">("workspace");
  const [clock, setClock] = useState(0);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [opening, setOpening] = useState<Amounts>({ CAD: "", BTC: "", ETH: "", LINK: "" });
  const [fee, setFee] = useState("");
  const [cadence, setCadence] = useState<Cadence | "">("");
  const [from, setFrom] = useState<Asset>("CAD");
  const [to, setTo] = useState<Asset>("BTC");
  const [amount, setAmount] = useState("");
  const [preview, setPreview] = useState<ShiftPreview | null>(null);
  const [flowKind, setFlowKind] = useState<"deposit" | "withdrawal">("deposit");
  const [flowAmount, setFlowAmount] = useState("");
  const errorBox = useRef<HTMLDivElement>(null);

  useEffect(() => { if (error) errorBox.current?.focus(); }, [error]);

  const refreshMarket = useCallback(async () => {
    try { setMarket(await api<MarketSnapshot>("market")); setMarketError(""); }
    catch (e) { setMarketError(e instanceof Error ? e.message : "Market data unavailable."); }
  }, []);
  const reloadPortfolio = useCallback(async () => {
    const result = await api<{ portfolio: Portfolio | null }>("portfolio"); setPortfolio(result.portfolio); setPreview(null);
  }, []);
  useEffect(() => {
    let live = true;
    api<Session>("session").then(async result => {
      if (!live) return;
      setSession(result);
      if (result.authenticated) await reloadPortfolio();
    }).catch(e => { if (live) setError(e.message); });
    void refreshMarket();
    const poll = setInterval(() => void refreshMarket(), 25000);
    const tick = setInterval(() => setClock(Date.now()), 1000);
    return () => { live = false; clearInterval(poll); clearInterval(tick); };
  }, [refreshMarket, reloadPortfolio]);

  async function work(action: () => Promise<void>) {
    setBusy(true); setError(""); setNotice("");
    try { await action(); } catch (e) { setError(e instanceof Error ? e.message : "Request failed."); }
    finally { setBusy(false); }
  }
  async function login(action: "demo" | "login" | "logout") {
    await work(async () => {
      const result = await api<Session>("session", { action, email, password });
      setSession(result); setPassword(""); setPortfolio(null); setPreview(null);
      if (result.authenticated) await reloadPortfolio();
    });
  }
  function create(event: FormEvent) {
    event.preventDefault();
    void work(async () => {
      const result = await api<{ portfolio: Portfolio; market: MarketSnapshot }>("portfolio", { name, opening, cadence, feeBps: Number(fee) });
      setPortfolio(result.portfolio); setMarket(result.market); setNotice("Paper portfolio saved. Your unchanged-unit HOLD baseline starts here.");
    });
  }
  function quote(event: FormEvent) {
    event.preventDefault();
    void work(async () => {
      setPreview(null);
      const result = await api<{ preview: ShiftPreview; market: MarketSnapshot }>("preview", { from, to, amount, expectedRevision: portfolio?.revision });
      setPreview(result.preview); setMarket(result.market);
    });
  }
  async function action(kind: "approve" | "hold" | "deposit" | "withdrawal") {
    await work(async () => {
      const result = await api<{ portfolio: Portfolio }>("action", { kind, expectedRevision: portfolio?.revision, previewId: preview?.id, amount: flowAmount });
      setPortfolio(result.portfolio); setPreview(null);
      setNotice(kind === "approve" ? "Paper shift recorded. No real order was sent." : kind === "hold" ? "HOLD recorded. All units unchanged." : "CAD cash flow applied equally to your portfolio and HOLD baseline.");
      if (kind === "deposit" || kind === "withdrawal") setFlowAmount("");
    });
  }

  async function exportLedger() {
    await work(async () => {
      const response = await fetch("/api/rotation/portfolio?export=1", { cache: "no-store" });
      if (!response.ok) throw new Error((await response.json()).error || "Export failed.");
      const href = URL.createObjectURL(await response.blob());
      const link = document.createElement("a");
      link.href = href; link.download = `wolfpack-rotation-${portfolio?.id}.json`;
      document.body.appendChild(link); link.click(); link.remove();
      setTimeout(() => URL.revokeObjectURL(href), 1000);
      setNotice("Complete ledger, research trials and audit history exported.");
    });
  }

  const value = portfolio && market ? performance(portfolio, market) : null;
  const rows = portfolio && market ? holdingRows(portfolio, market) : [];
  const seconds = preview ? Math.max(0, Math.ceil((Date.parse(preview.expiresAt) - clock) / 1000)) : 0;
  const marketStale = market ? clock > Date.parse(market.expiresAt) : true;
  const field = "rotation-input";

  return <div className="rotation-workspace space-y-6">
    <header className="flex flex-wrap items-start justify-between gap-5 border-b border-white/10 pb-6">
      <div><p className="text-xs uppercase tracking-[.18em] text-emerald-300 mb-3">CAD / BTC / ETH / LINK</p><h1 className="text-3xl md:text-4xl font-semibold tracking-tight">Make the shift count.</h1><p className="text-slate-300 mt-3 max-w-2xl leading-relaxed">Weekly or monthly decisions. Every move measured against doing nothing.</p></div>
      <div className="flex flex-col items-start sm:items-end gap-3"><span className="rounded-full border border-emerald-400/40 bg-emerald-400/10 px-3 py-1.5 text-xs text-emerald-200">PAPER WORKSPACE</span>{session?.authenticated && <button className="rotation-secondary" disabled={busy} onClick={() => void login("logout")}>Sign out</button>}</div>
    </header>
    <div className="rotation-note">Practice with real market prices and paper balances. Funding and live execution are gated. Research is experimental; a positive backtest does not establish a reliable forecast.</div>
    {error && <div ref={errorBox} tabIndex={-1} className="rotation-error" role="alert">{error}<button className="rotation-secondary block mt-3" onClick={() => void work(async () => { const result = await api<Session>("session"); setSession(result); if (result.authenticated) await reloadPortfolio(); })}>Reload saved state</button></div>}
    {notice && <p role="status" className="rotation-note">{notice}</p>}

    {!session?.authenticated ? <section className={`${ROTATION_STYLE.panel} max-w-xl`}>
      <h2 className="text-xl font-semibold">Open your workspace</h2><p className="text-sm text-slate-300 mt-2 mb-5">Sign in to keep your ledger and research together across devices. Workshop accounts contain paper data.</p>
      {session === null && !error ? <p role="status">Checking session…</p> : <>
        {session?.demoEnabled && <button className="rotation-primary w-full mb-5" disabled={busy} onClick={() => void login("demo")}>{busy ? "Opening workspace…" : "Enter paper demo"}</button>}
        <form onSubmit={event => { event.preventDefault(); void login("login"); }} className="space-y-4">
          <label>Email<input className={field} type="email" autoComplete="username" required value={email} onChange={e => setEmail(e.target.value)} /></label>
          <label>Password<input className={field} type="password" autoComplete="current-password" required value={password} onChange={e => setPassword(e.target.value)} /></label>
          <button className="rotation-secondary w-full" disabled={busy}>Sign in</button>
        </form>
      </>}
    </section> : <>
      <nav aria-label="Rotation views" className="flex gap-2 border-b border-white/10 pb-4">
        <button className={tab === "workspace" ? "rotation-primary" : "rotation-secondary"} aria-pressed={tab === "workspace"} onClick={() => setTab("workspace")}>Workspace</button>
        <button className={tab === "research" ? "rotation-primary" : "rotation-secondary"} aria-pressed={tab === "research"} onClick={() => setTab("research")}>Backtest & forecast</button>
      </nav>
      <div hidden={tab !== "workspace"} className="space-y-6">
      {!portfolio ? <section className={ROTATION_STYLE.panel}>
        <h2 className="text-xl font-semibold">Set your starting point</h2><p className="text-sm text-slate-300 mt-2 mb-5">Enter paper units, including zero for assets you do not hold. Both portfolios start with these exact balances. Opening crypto cost basis uses today’s midpoint for this paper experiment.</p>
        <form onSubmit={create} className="space-y-5">
          <label>Portfolio name<input className={field} required maxLength={80} value={name} onChange={e => setName(e.target.value)} placeholder="Name this experiment" /></label>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">{ASSETS.map(asset => <label key={asset}>Opening {asset}<input className={field} inputMode="decimal" required pattern="(?:0|[1-9][0-9]*)(?:\.[0-9]{1,8})?" value={opening[asset]} onChange={e => setOpening({ ...opening, [asset]: e.target.value })} /></label>)}</div>
          <div className="grid sm:grid-cols-2 gap-4"><label>Fee (bps)<input className={field} type="number" required min="0" max="1000" step="1" value={fee} onChange={e => setFee(e.target.value)} /><span className="block text-xs text-slate-300 mt-2">Per CAD trade leg. 20 bps = 0.20%. Enter your paper cost assumption.</span></label><label>Review cadence<select className={field} required value={cadence} onChange={e => setCadence(e.target.value as Cadence)}><option value="">Choose cadence</option><option value="weekly">Weekly</option><option value="monthly">Monthly</option></select></label></div>
          <button className="rotation-primary" disabled={busy || !market}>Create paper portfolio</button>
        </form>
      </section> : <>
        <div className="flex flex-wrap justify-between items-center gap-3"><div><h2 className="text-xl font-semibold">{portfolio.name}</h2><p className="text-sm text-slate-300 mt-1 capitalize">{portfolio.cadence} review · {portfolio.feeBps} bps per leg · Revision {portfolio.revision}</p></div><div className="flex flex-wrap gap-2"><button className="rotation-secondary" disabled={busy} onClick={() => void work(reloadPortfolio)}>Refresh ledger</button><button className="rotation-secondary" disabled={busy} onClick={() => void exportLedger()}>Export ledger</button></div></div>
        <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-4">
          <MetricCard label="Portfolio value" value={value ? cad(value.actualCad) : "—"} note="CAD cash plus current crypto value." testId="portfolio-value" />
          <MetricCard label="No-action HOLD" value={value ? cad(value.holdCad) : "—"} note="Original units, with the same cash flows." testId="hold-value" />
          <MetricCard label="Added by decisions" value={value ? cad(value.incrementalCad) : "—"} tone={value && Number(value.incrementalCad) >= 0 ? "positive" : "negative"} note="Portfolio value minus HOLD, after fees." testId="decision-value" />
          <MetricCard label="Net profit / loss" value={value ? cad(value.profitCad) : "—"} note="Deposits and withdrawals excluded." testId="net-profit" />
        </div>
        <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-slate-300"><span>Realized {value ? cad(value.realizedCad) : "—"}</span><span>Unrealized {value ? cad(value.unrealizedCad) : "—"}</span><span>Fees paid {cad(portfolio.feesCad)}</span><span>Net cash flows {cad(portfolio.netFlowsCad)}</span></div>
        <div className="rotation-grid"><HoldingsTable rows={rows} market={market} />
          <section className={ROTATION_STYLE.panel}><h2 className={ROTATION_STYLE.title}>Review a paper shift</h2><p className="text-sm text-slate-300 mt-2 mb-5">Review the exact units and costs before approving. Crypto-to-crypto shifts use two CAD legs.</p>
            <form onSubmit={quote} className="space-y-4"><div className="grid grid-cols-2 gap-3"><label>From<select className={field} value={from} onChange={e => { setFrom(e.target.value as Asset); setPreview(null); }}>{ASSETS.map(a => <option key={a}>{a}</option>)}</select></label><label>To<select className={field} value={to} onChange={e => { setTo(e.target.value as Asset); setPreview(null); }}>{ASSETS.map(a => <option key={a}>{a}</option>)}</select></label></div>
              <label>Amount<input className={field} inputMode="decimal" required value={amount} onChange={e => { setAmount(e.target.value); setPreview(null); }} /><span className="block text-xs text-slate-300 mt-2">Units of {from}. CAD buy amounts include fees.</span></label>
              <div className="flex flex-wrap gap-3"><button className="rotation-primary" disabled={busy || from === to}>Preview shift</button><button type="button" className="rotation-secondary" disabled={busy} onClick={() => void action("hold")}>Record HOLD</button></div>
            </form>
            {preview && <div className="mt-5 rounded-lg border border-emerald-300/40 p-4 space-y-3" aria-live="polite"><h3 className="font-semibold">Approval preview</h3><p className="text-sm">{preview.amount} {preview.from} → {preview.received} {preview.to}</p><p className="text-sm text-slate-300">Total fees {cad(preview.feeCad)} · {seconds > 0 ? `${seconds}s remaining` : "Expired. Request a fresh preview."}</p><ul className="text-xs text-slate-300 space-y-2">{preview.legs.map((leg, i) => <li key={i}>{leg.side.toUpperCase()} {leg.quantity} {leg.asset} · {cad(leg.grossCad)} + {cad(leg.feeCad)} fee</li>)}</ul><button className="rotation-primary w-full" disabled={busy || seconds <= 0} onClick={() => void action("approve")}>Approve paper shift</button></div>}
          </section>
        </div>
        <div className="rotation-grid"><ActivityList events={portfolio.events} /><section className={`${ROTATION_STYLE.panel} self-start`}><h2 className={ROTATION_STYLE.title}>Keep cash flows separate</h2><p className="text-sm text-slate-300 mt-2 mb-5">Record paper CAD deposits or withdrawals. They change both portfolios equally and never count as profit. A withdrawal requires enough CAD in both.</p><form onSubmit={event => { event.preventDefault(); void action(flowKind); }} className="space-y-4"><label>Cash flow type<select className={field} value={flowKind} onChange={e => setFlowKind(e.target.value as "deposit" | "withdrawal")}><option value="deposit">Deposit</option><option value="withdrawal">Withdrawal</option></select></label><label>Cash flow amount<input className={field} inputMode="decimal" required value={flowAmount} onChange={e => setFlowAmount(e.target.value)} /></label><button className="rotation-secondary" disabled={busy}>Record cash flow</button></form></section></div>
      </>}
      </div>
      <div hidden={tab !== "research"}><ResearchPanel portfolio={portfolio} market={market} active={tab === "research"} /></div>
    </>}
    <footer className="border-t border-white/10 pt-5 text-xs text-slate-300 leading-relaxed space-y-2">
      <p>{market ? `Market source: ${market.source}. Received ${eastern(market.fetchedAt)} ET.${marketStale ? " Valuation snapshot is stale; approval always requires a fresh quote." : ""}` : "Loading real CAD market data…"} <button className="underline underline-offset-4 px-2" disabled={busy} onClick={() => void refreshMarket()}>Refresh prices</button></p>
      {marketError && <p role="status" className="text-red-300">{marketError}</p>}
      <p>Workshop paper data · Native BTC, ETH and LINK · Actual CAD denomination · <a className="underline underline-offset-4" href="/rotation/about">Data and research notes</a> · <a className="underline underline-offset-4" href="/api/rotation/readiness" target="_blank" rel="noreferrer">Service readiness</a></p>
    </footer>
  </div>;
}
