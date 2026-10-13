import { ASSETS, cad, ROTATION_STYLE, type HoldingRow, type MarketSnapshot } from "@/lib/rotation/contract";

export function HoldingsTable({ rows, market }: { rows: HoldingRow[]; market: MarketSnapshot | null }) {
  return <section className={ROTATION_STYLE.panel}>
    <h2 className={ROTATION_STYLE.title}>Your four balances</h2>
    <dl className="sm:hidden mt-3 divide-y divide-white/10">{ASSETS.map(asset => {
      const row = rows.find(item => item.asset === asset);
      return <div key={asset} className="py-4"><div className="flex justify-between gap-3"><dt className="font-semibold text-emerald-300">{asset}</dt><dd className="tabular-nums">{row ? cad(row.valueCad) : "—"}</dd></div><dd className="flex flex-wrap justify-between gap-2 text-xs text-slate-300 mt-2 tabular-nums"><span>{row ? `${Number(row.units).toLocaleString("en-CA", { maximumFractionDigits: 8 })} units` : "No valuation"}</span><span>{row ? `${row.weightPercent.toFixed(1)}% of portfolio` : ""}</span></dd></div>;
    })}</dl>
    <div className={`hidden sm:block ${ROTATION_STYLE.tableWrap}`}><table aria-label="Paper holdings and CAD values" className={ROTATION_STYLE.table}>
      <thead><tr className="text-slate-300"><th className={ROTATION_STYLE.cell}>Asset</th><th className={ROTATION_STYLE.cell}>Units</th><th className={ROTATION_STYLE.cell}>CAD value</th><th className={ROTATION_STYLE.cell}>Weight</th></tr></thead>
      <tbody>{ASSETS.map(asset => {
        const row = rows.find(item => item.asset === asset);
        return <tr key={asset}><th scope="row" className={`${ROTATION_STYLE.cell} text-emerald-300`}>{asset}</th><td className={ROTATION_STYLE.cell}>{row ? Number(row.units).toLocaleString("en-CA", { maximumFractionDigits: 8 }) : "—"}</td><td className={ROTATION_STYLE.cell}>{row ? cad(row.valueCad) : "—"}</td><td className={ROTATION_STYLE.cell}>{row ? `${row.weightPercent.toFixed(1)}%` : "—"}</td></tr>;
      })}</tbody>
    </table></div>
    <p className="text-xs text-slate-300 leading-relaxed mt-4">{market ? "Valued at the midpoint of public CAD bid and ask prices. Shift previews include spread, depth and your paper fee assumption." : "Real market data will appear when the provider responds."}</p>
  </section>;
}
