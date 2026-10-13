import { cad, eastern, ROTATION_STYLE, type LedgerEvent } from "@/lib/rotation/contract";

export function ActivityList({ events }: { events: LedgerEvent[] }) {
  return <section className={ROTATION_STYLE.panel}>
    <h2 className={ROTATION_STYLE.title}>Decision history</h2>
    {!events.length ? <p className="text-sm text-slate-300 mt-4">Your opening balances, paper shifts, HOLD decisions and cash flows will appear here.</p> :
      <ol className="divide-y divide-white/10 mt-3">{events.slice(-30).reverse().map(event => <li key={event.id} className="py-4">
        <div className="flex flex-wrap justify-between gap-2"><span className="text-xs uppercase tracking-wider text-emerald-300">{event.kind}</span><time dateTime={event.at} className="text-xs text-slate-300">{eastern(event.at)} ET</time></div>
        <p className="text-sm mt-2 break-words">{event.description}</p>
        {event.kind === "shift" && <p className="text-xs text-slate-300 mt-2">Fee {cad(event.feeCad)} · Realized P/L {cad(event.realizedPnlCad)}</p>}
      </li>)}</ol>}
    {events.length > 30 && <p className="text-xs text-slate-300 mt-2">Latest 30 events shown. Export includes the full ledger.</p>}
  </section>;
}
