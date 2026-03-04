"use client";

import Link from "next/link";
import { useExchange } from "@/lib/exchange";
import { useAgentOutputs, useAgentStatus, useRecommendations, usePortfolio } from "@/lib/hooks/useIntelligence";
import { usePrice } from "@/lib/hooks/useMarketData";

export default function Dashboard() {
  const { config } = useExchange();
  const { data: agentOutputs } = useAgentOutputs();
  const { data: agentStatus } = useAgentStatus();
  const { data: recommendations } = useRecommendations("pending");
  const { data: portfolio } = usePortfolio();
  const { data: btcPrice } = usePrice("BTC");
  const { data: ethPrice } = usePrice("ETH");

  const agents = agentStatus?.agents ?? [];
  const isActive = portfolio?.status === "active";

  return (
    <div className="space-y-7">
      {/* Portfolio Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard
          label="Portfolio Value"
          value={isActive ? `$${portfolio.equity.toLocaleString()}` : "--"}
          suffix="USD"
          color="emerald"
          delay={1}
        />
        <StatCard
          label="Unrealized P&L"
          value={
            isActive
              ? `${portfolio.unrealized_pnl >= 0 ? "+" : ""}$${portfolio.unrealized_pnl.toFixed(2)}`
              : "--"
          }
          color={isActive && portfolio.unrealized_pnl >= 0 ? "emerald" : "red"}
          delay={2}
        />
        <StatCard
          label="Open Positions"
          value={isActive ? String(portfolio.positions?.length ?? 0) : "--"}
          color="purple"
          delay={3}
        />
        <StatCard
          label="Pending Recs"
          value={recommendations?.length?.toString() ?? "--"}
          color="amber"
          delay={4}
        />
      </div>

      {/* Live Prices + Active Exchange */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="wolf-card p-4 flex items-center justify-between animate-in animate-in-3">
          <div className="flex items-center gap-3">
            <div className="w-2 h-2 rounded-full bg-[var(--wolf-emerald)] pulse-glow" style={{ color: "var(--wolf-emerald)" }} />
            <span className="text-[13px] text-gray-400">
              Active: <span className="text-white font-semibold">{config.name}</span>
            </span>
          </div>
          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-[var(--wolf-emerald)]/15 text-[var(--wolf-emerald)]">Connected</span>
        </div>
        <PriceTicker label="BTC" price={btcPrice?.price} delay={4} />
        <PriceTicker label="ETH" price={ethPrice?.price} delay={5} />
      </div>

      {/* Intelligence Summary + Recommendations */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Intelligence Brief */}
        <div className="wolf-card p-6 animate-in animate-in-4">
          <div className="flex items-center justify-between mb-5">
            <div className="flex items-center gap-2">
              <div className="w-1 h-4 rounded-full bg-[var(--wolf-cyan)]" />
              <h2 className="section-title">Intelligence Brief</h2>
            </div>
            <Link href="/intelligence" className="text-[11px] text-[var(--wolf-cyan)] hover:underline">View all</Link>
          </div>
          <div className="space-y-1">
            {agents.length > 0
              ? agents.map((a: { name: string; key: string; status: string; last_run: string | null }) => (
                  <AgentRow
                    key={a.key}
                    name={a.name}
                    status={a.status === "running" ? "active" : agentOutputs?.[a.key] ? "active" : "idle"}
                    lastRun={
                      agentOutputs?.[a.key]?.created_at
                        ? new Date(agentOutputs[a.key].created_at).toLocaleTimeString()
                        : "--"
                    }
                  />
                ))
              : (
                <>
                  <AgentRow name="The Quant" status={agentOutputs?.quant ? "active" : "idle"} lastRun={agentOutputs?.quant ? new Date(agentOutputs.quant.created_at).toLocaleTimeString() : "--"} />
                  <AgentRow name="The Snoop" status="idle" lastRun="--" />
                  <AgentRow name="The Sage" status="idle" lastRun="--" />
                  <AgentRow name="The Brief" status="idle" lastRun="--" />
                </>
              )}
          </div>
          {agentOutputs?.brief?.summary ? (
            <div className="mt-5 pt-4 border-t border-[var(--border)]">
              <p className="text-[10px] text-[var(--wolf-amber)] font-semibold uppercase mb-1">The Brief</p>
              <p className="text-[12px] text-gray-400 leading-relaxed line-clamp-3">{agentOutputs.brief.summary}</p>
            </div>
          ) : agentOutputs?.quant?.summary ? (
            <div className="mt-5 pt-4 border-t border-[var(--border)]">
              <p className="text-[10px] text-[var(--wolf-cyan)] font-semibold uppercase mb-1">The Quant</p>
              <p className="text-[12px] text-gray-400 leading-relaxed line-clamp-3">{agentOutputs.quant.summary}</p>
            </div>
          ) : null}
        </div>

        {/* Trade Recommendations */}
        <div className="wolf-card p-6 animate-in animate-in-5">
          <div className="flex items-center justify-between mb-5">
            <div className="flex items-center gap-2">
              <div className="w-1 h-4 rounded-full bg-[var(--wolf-amber)]" />
              <h2 className="section-title">Trade Recommendations</h2>
            </div>
            <Link href="/trading" className="text-[11px] text-[var(--wolf-amber)] hover:underline">Trade</Link>
          </div>
          {recommendations && recommendations.length > 0 ? (
            <div className="space-y-1">
              {recommendations.slice(0, 5).map((rec: Record<string, unknown>) => (
                <div
                  key={rec.id as string}
                  className="flex items-center justify-between py-2.5 px-3 -mx-3 rounded-lg hover:bg-[var(--surface-hover)]/50 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <span
                      className={`badge ${
                        rec.direction === "long"
                          ? "bg-[var(--wolf-emerald)]/15 text-[var(--wolf-emerald)]"
                          : "bg-[var(--wolf-red)]/15 text-[var(--wolf-red)]"
                      }`}
                    >
                      {rec.direction as string}
                    </span>
                    <span className="text-[13px] text-white font-mono font-medium">{rec.symbol as string}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="w-16 h-1.5 rounded-full bg-[var(--surface)] overflow-hidden">
                      <div
                        className="h-full rounded-full bg-[var(--wolf-amber)] transition-all"
                        style={{ width: `${rec.conviction as number}%` }}
                      />
                    </div>
                    <span className="text-[11px] text-gray-400 font-mono w-8 text-right">
                      {rec.conviction as number}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-state">
              <p className="text-gray-500">No pending recommendations</p>
              <p className="text-gray-600 text-[11px] mt-1">Run intelligence to generate trade signals</p>
            </div>
          )}
        </div>
      </div>

      {/* Open Positions */}
      {isActive && portfolio.positions?.length > 0 && (
        <div className="wolf-card p-6 animate-in animate-in-6">
          <div className="flex items-center gap-2 mb-5">
            <div className="w-1 h-4 rounded-full bg-[var(--wolf-purple)]" />
            <h2 className="section-title">Open Positions</h2>
            <span className="ml-auto text-[11px] text-gray-500 font-mono">
              {portfolio.positions.length} active
            </span>
          </div>
          <div className="space-y-1">
            {portfolio.positions.map(
              (pos: {
                symbol: string;
                direction: string;
                entry_price: number;
                size_usd: number;
                unrealized_pnl: number;
              }) => (
                <div
                  key={pos.symbol}
                  className="flex items-center justify-between py-2.5 px-3 -mx-3 rounded-lg hover:bg-[var(--surface-hover)]/50 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <span
                      className={`badge ${
                        pos.direction === "long"
                          ? "bg-[var(--wolf-emerald)]/15 text-[var(--wolf-emerald)]"
                          : "bg-[var(--wolf-red)]/15 text-[var(--wolf-red)]"
                      }`}
                    >
                      {pos.direction}
                    </span>
                    <span className="text-[13px] text-white font-mono font-medium">{pos.symbol}</span>
                    <span className="text-[11px] text-gray-500 font-mono">
                      ${pos.size_usd.toFixed(0)} @ ${pos.entry_price.toLocaleString()}
                    </span>
                  </div>
                  <span
                    className={`text-[13px] font-semibold font-mono ${
                      pos.unrealized_pnl >= 0
                        ? "text-[var(--wolf-emerald)]"
                        : "text-[var(--wolf-red)]"
                    }`}
                  >
                    {pos.unrealized_pnl >= 0 ? "+" : ""}${pos.unrealized_pnl.toFixed(2)}
                  </span>
                </div>
              )
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function PriceTicker({ label, price, delay }: { label: string; price?: number | null; delay: number }) {
  return (
    <div className={`wolf-card p-4 flex items-center justify-between animate-in animate-in-${delay}`}>
      <span className="text-[13px] text-gray-500 font-mono">{label}-USD</span>
      {price ? (
        <span className="text-lg font-bold text-white font-mono tracking-tight">
          ${price.toLocaleString(undefined, { maximumFractionDigits: 2 })}
        </span>
      ) : (
        <div className="w-20 h-5 rounded skeleton-shimmer" />
      )}
    </div>
  );
}

function StatCard({
  label,
  value,
  suffix,
  color,
  delay,
}: {
  label: string;
  value: string;
  suffix?: string;
  color: string;
  delay: number;
}) {
  const colorMap: Record<string, string> = {
    emerald: "text-[var(--wolf-emerald)]",
    blue: "text-[var(--wolf-blue)]",
    red: "text-[var(--wolf-red)]",
    purple: "text-[var(--wolf-purple)]",
    amber: "text-[var(--wolf-amber)]",
  };

  return (
    <div className={`wolf-card stat-card stat-card-${color} p-5 animate-in animate-in-${delay}`}>
      <p className="text-[11px] text-gray-500 uppercase tracking-wider font-medium">{label}</p>
      <p className={`text-2xl font-bold mt-2 tracking-tight ${colorMap[color] ?? "text-white"}`}>
        {value}
        {suffix && <span className="text-[11px] font-normal text-gray-600 ml-1.5">{suffix}</span>}
      </p>
    </div>
  );
}

function AgentRow({
  name,
  status,
  lastRun,
}: {
  name: string;
  status: string;
  lastRun: string;
}) {
  return (
    <div className="flex items-center justify-between py-2.5 px-3 -mx-3 rounded-lg hover:bg-[var(--surface-hover)]/50 transition-colors">
      <div className="flex items-center gap-3">
        <div
          className={`w-1.5 h-1.5 rounded-full ${
            status === "active" ? "bg-[var(--wolf-emerald)]" : "bg-gray-600"
          }`}
          style={status === "active" ? { boxShadow: "0 0 6px var(--wolf-emerald)" } : undefined}
        />
        <span className="text-[13px] text-gray-300">{name}</span>
      </div>
      <span className="text-[11px] text-gray-600 font-mono">{lastRun}</span>
    </div>
  );
}
