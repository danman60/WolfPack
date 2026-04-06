"use client";

import { useState } from "react";
import Link from "next/link";
import { useExchange } from "@/lib/exchange";
import { useAgentOutputs, useAgentStatus, useRecommendations, usePortfolio, useWatchlist, useAutoTraderStatus, useProfit, useStrategyMode } from "@/lib/hooks/useIntelligence";
import { WolfHead } from "@/components/WolfHead";
import { usePrice, use24hChange } from "@/lib/hooks/useMarketData";
import { useLPStatus } from "@/lib/hooks/usePools";
import { Term } from "@/components/Term";

export default function Dashboard() {
  const { config } = useExchange();
  const { data: agentOutputs } = useAgentOutputs();
  const { data: agentStatus } = useAgentStatus();
  const { data: recommendations } = useRecommendations("pending");
  const { data: portfolio } = usePortfolio();
  const { data: btcPrice } = usePrice("BTC");
  const { data: ethPrice } = usePrice("ETH");
  const { data: watchlist } = useWatchlist();
  const { data: autoTrader } = useAutoTraderStatus();
  const { data: lpStatus } = useLPStatus();
  const { data: strategyMode } = useStrategyMode();

  const agents = agentStatus?.agents ?? [];
  const isActive = portfolio?.status === "active";
  const isLive = strategyMode?.mode === "live";

  return (
    <div className="space-y-5 md:space-y-7">
      {/* Live Mode Banner */}
      {isLive && (
        <div className="wolf-card p-3 border-[var(--wolf-red)]/30 bg-red-500/5 flex items-center justify-between animate-in">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-[var(--wolf-red)] pulse-glow" style={{ color: "var(--wolf-red)" }} />
            <span className="text-[13px] font-semibold text-[var(--wolf-red)]">LIVE TRADING</span>
            <span className="text-[11px] text-gray-500">Real money active</span>
          </div>
          <span className="text-[10px] px-2 py-1 rounded bg-red-500/15 text-red-400 font-semibold">
            {strategyMode?.mode?.toUpperCase()}
          </span>
        </div>
      )}

      {/* Profit Report */}
      <ProfitReport />

      {/* Portfolio Stats */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 md:gap-4">
        <StatCard
          label={<Term id="equity">Portfolio Value</Term>}
          value={isActive ? `$${portfolio.equity.toLocaleString()}` : "--"}
          suffix="USD"
          color="emerald"
          delay={1}
        />
        <StatCard
          label={<Term id="unrealized-pnl">Unrealized P&L</Term>}
          value={
            isActive
              ? `${portfolio.unrealized_pnl >= 0 ? "+" : ""}$${portfolio.unrealized_pnl.toFixed(2)}`
              : "--"
          }
          color={isActive && portfolio.unrealized_pnl >= 0 ? "emerald" : "red"}
          delay={2}
        />
        <StatCard
          label={<Term id="position">Open Positions</Term>}
          value={isActive ? String(portfolio.positions?.length ?? 0) : "--"}
          color="purple"
          delay={3}
        />
        <StatCard
          label={<Term id="watchlist">Watchlist</Term>}
          value={watchlist?.length?.toString() ?? "0"}
          suffix="symbols"
          color="cyan"
          delay={4}
        />
        {autoTrader?.enabled && (
          <StatCard
            label={<Term id="auto-bot">Auto-Bot Equity</Term>}
            value={`$${autoTrader.equity.toLocaleString()}`}
            suffix={`${autoTrader.open_positions} pos`}
            color="amber"
            delay={5}
            className="col-span-2 md:col-span-1"
          />
        )}
      </div>

      {/* Live Prices + Active Exchange */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 md:gap-4">
        <div className="wolf-card p-4 flex items-center justify-between animate-in animate-in-3">
          <div className="flex items-center gap-3">
            <div className="w-2 h-2 rounded-full bg-[var(--wolf-emerald)] pulse-glow" style={{ color: "var(--wolf-emerald)" }} />
            <span className="text-[13px] text-gray-400">
              Active: <span className="text-white font-semibold">{config.name}</span>
            </span>
          </div>
          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-[var(--wolf-emerald)]/15 text-[var(--wolf-emerald)]">Connected</span>
        </div>
        <PriceTicker label="BTC" price={btcPrice?.price} symbol="BTC" delay={4} />
        <PriceTicker label="ETH" price={ethPrice?.price} symbol="ETH" delay={5} />
      </div>

      {/* LP Autobot */}
      {lpStatus && (
        <div className="wolf-card p-5 animate-in animate-in-200">
          <div className="flex items-center gap-2 mb-4">
            <div className="w-1 h-4 rounded-full bg-[var(--wolf-cyan)]" />
            <h2 className="text-[15px] font-semibold text-white tracking-tight">LP Autobot</h2>
            <span className={`ml-auto text-[11px] px-2 py-0.5 rounded-full ${
              lpStatus.enabled
                ? "bg-emerald-500/10 text-emerald-400"
                : "bg-gray-500/10 text-gray-500"
            }`}>
              {lpStatus.enabled ? (lpStatus.paper_mode ? "Paper Mode" : "Live") : "Disabled"}
            </span>
          </div>

          {/* Stats Row */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            <div>
              <p className="text-[11px] text-gray-500 uppercase tracking-wider font-medium">Equity</p>
              <p className="text-lg font-bold text-white mt-1">${lpStatus.equity.toLocaleString()}</p>
            </div>
            <div>
              <p className="text-[11px] text-gray-500 uppercase tracking-wider font-medium">Active Positions</p>
              <p className="text-lg font-bold text-white mt-1">
                {lpStatus.positions} <span className="text-[11px] font-normal text-gray-600">/ {lpStatus.max_positions}</span>
              </p>
            </div>
            <div>
              <p className="text-[11px] text-gray-500 uppercase tracking-wider font-medium">Total Fees</p>
              <p className="text-lg font-bold text-[var(--wolf-emerald)] mt-1">${lpStatus.total_fees.toLocaleString()}</p>
            </div>
            <div>
              <p className="text-[11px] text-gray-500 uppercase tracking-wider font-medium">Net P&L</p>
              <p className={`text-lg font-bold mt-1 ${
                lpStatus.total_fees - lpStatus.total_il >= 0
                  ? "text-[var(--wolf-emerald)]"
                  : "text-[var(--wolf-red)]"
              }`}>
                {lpStatus.total_fees - lpStatus.total_il >= 0 ? "+" : ""}${(lpStatus.total_fees - lpStatus.total_il).toFixed(2)}
              </p>
            </div>
          </div>

          {/* Position Details */}
          {lpStatus.position_details && lpStatus.position_details.length > 0 ? (
            <div className="border-t border-[var(--border)] pt-3 mb-3">
              <div className="space-y-1">
                {lpStatus.position_details.map((pos) => (
                  <div
                    key={pos.pool}
                    className="flex items-center justify-between py-2.5 px-3 -mx-3 rounded-lg hover:bg-[var(--surface-hover)]/50 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <span className={`text-[10px] px-1.5 py-0.5 rounded font-semibold ${
                        pos.in_range
                          ? "bg-emerald-500/15 text-emerald-400"
                          : "bg-amber-500/15 text-amber-400"
                      }`}>
                        {pos.in_range ? "Active" : "OOR"}
                      </span>
                      <span className="text-[13px] text-white font-mono font-medium">{pos.pair}</span>
                    </div>
                    <div className="flex items-center gap-2 md:gap-4">
                      <span className="text-[11px] text-[var(--wolf-emerald)] font-mono">+${pos.fees_earned.toFixed(2)}</span>
                      <span className="text-[11px] text-[var(--wolf-red)] font-mono hidden sm:inline">-{pos.il_pct.toFixed(1)}% IL</span>
                      <span className={`text-[13px] font-semibold font-mono ${
                        pos.net_pnl >= 0 ? "text-[var(--wolf-emerald)]" : "text-[var(--wolf-red)]"
                      }`}>
                        {pos.net_pnl >= 0 ? "+" : ""}${pos.net_pnl.toFixed(2)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="border-t border-[var(--border)] pt-3 mb-3">
              <p className="text-[12px] text-gray-600 text-center py-2">
                No active LP positions — scanner will find pools on next cycle
              </p>
            </div>
          )}

          {/* Footer Row */}
          <div className="flex flex-wrap items-center gap-2 md:gap-4 text-[11px] text-gray-500 border-t border-[var(--border)] pt-3">
            <span>{lpStatus.scanner_candidates} candidates</span>
            <span className="text-gray-700 hidden sm:inline">|</span>
            <span>IL Hedges: {lpStatus.active_il_hedges} active (${lpStatus.total_hedge_usd.toFixed(0)})</span>
            <span className="text-gray-700 hidden sm:inline">|</span>
            <span>{lpStatus.watched_pools} watched pools</span>
          </div>
        </div>
      )}

      {/* Intelligence Summary + Recommendations */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 md:gap-6">
        {/* Intelligence Brief */}
        <div className="wolf-card p-4 md:p-6 animate-in animate-in-4">
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
                    agentKey={a.key}
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
        <div className="wolf-card p-4 md:p-6 animate-in animate-in-5">
          <div className="flex items-center justify-between mb-5">
            <div className="flex items-center gap-2">
              <div className="w-1 h-4 rounded-full bg-[var(--wolf-amber)]" />
              <h2 className="section-title">Trade Recommendations</h2>
            </div>
            <Link href="/trading" className="text-[11px] text-[var(--wolf-amber)] hover:underline">Trade</Link>
          </div>
          {recommendations && recommendations.length > 0 ? (
            <div className="space-y-1">
              {recommendations.slice(0, 5).map((rec) => (
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
                      <Term id={rec.direction === "long" ? "long" : "short"}>{rec.direction as string}</Term>
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
        <div className="wolf-card p-4 md:p-6 animate-in animate-in-6">
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
                  className="flex flex-col sm:flex-row sm:items-center justify-between py-2.5 px-3 -mx-3 rounded-lg hover:bg-[var(--surface-hover)]/50 transition-colors gap-1 sm:gap-0"
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
                    <span className="text-[11px] text-gray-500 font-mono hidden sm:inline">
                      ${pos.size_usd.toFixed(0)} @ ${pos.entry_price.toLocaleString()}
                    </span>
                  </div>
                  <div className="flex items-center justify-between sm:justify-end gap-2 pl-8 sm:pl-0">
                    <span className="text-[11px] text-gray-500 font-mono sm:hidden">
                      ${pos.size_usd.toFixed(0)} @ ${pos.entry_price.toLocaleString()}
                    </span>
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
                </div>
              )
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function ProfitReport() {
  const [hours, setHours] = useState(24);
  const { data: profit, isFetching } = useProfit(hours);

  const periods = [
    { label: "1H", value: 1 },
    { label: "4H", value: 4 },
    { label: "12H", value: 12 },
    { label: "24H", value: 24 },
  ];

  if (!profit) return null;

  const hasCombined = profit.combined_pnl !== undefined;
  const mainPnl = hasCombined ? profit.combined_pnl : (profit.total_pnl ?? 0);
  const lp = profit.lp;

  return (
    <div className={`wolf-card p-4 md:p-6 animate-in animate-in-1 transition-opacity duration-200 ${isFetching ? "opacity-70" : "opacity-100"}`}>
      {/* Header + Period Buttons */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-5">
        <div className="flex items-center gap-2">
          <div className="w-1 h-4 rounded-full bg-[var(--wolf-emerald)]" />
          <h2 className="text-[15px] font-semibold text-white tracking-tight">Profit Report</h2>
        </div>
        <div className="flex gap-1 bg-[var(--surface)] rounded-lg p-1">
          {periods.map((p) => (
            <button
              key={p.value}
              onClick={() => setHours(p.value)}
              className={`px-3 py-2 rounded-md text-[12px] font-semibold transition-all min-h-[36px] ${
                hours === p.value
                  ? "bg-[var(--wolf-emerald)] text-white shadow-sm"
                  : "text-gray-400 hover:text-white hover:bg-[var(--surface-hover)]"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Combined P&L Hero */}
      <div className="text-center mb-5">
        <p className="text-[11px] text-gray-500 uppercase tracking-wider font-medium mb-1">
          {hasCombined ? "Combined" : "Total"} P&L — Last {hours}h
        </p>
        <p className={`text-3xl md:text-4xl font-bold tracking-tight ${
          mainPnl >= 0 ? "text-[var(--wolf-emerald)]" : "text-[var(--wolf-red)]"
        }`}>
          {mainPnl >= 0 ? "+" : ""}${Math.abs(mainPnl).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </p>
      </div>

      {/* Perp + LP Side by Side */}
      <div className={`grid ${lp ? "grid-cols-1 md:grid-cols-2" : "grid-cols-1"} gap-4`}>
        {/* Perp Section */}
        <div className="bg-[var(--surface)]/50 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <span className="text-[12px] text-gray-400 font-semibold uppercase tracking-wider">Perpetual Trading</span>
            <span className={`text-[15px] font-bold font-mono ${
              (profit.total_pnl ?? 0) >= 0 ? "text-[var(--wolf-emerald)]" : "text-[var(--wolf-red)]"
            }`}>
              {(profit.total_pnl ?? 0) >= 0 ? "+" : ""}${(profit.total_pnl ?? 0).toFixed(2)}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <ProfitMiniStat label="Trades" value={String(profit.trades ?? 0)} />
            <ProfitMiniStat label="Win Rate" value={`${profit.win_rate_pct ?? 0}%`} color={(profit.win_rate_pct ?? 0) >= 50 ? "emerald" : "red"} />
            <ProfitMiniStat label="Avg Win" value={`+$${(profit.avg_win ?? 0).toFixed(2)}`} color="emerald" />
            <ProfitMiniStat label="Avg Loss" value={`$${(profit.avg_loss ?? 0).toFixed(2)}`} color="red" />
          </div>
        </div>

        {/* LP Section */}
        {lp && (
          <div className="bg-[var(--surface)]/50 rounded-lg p-4">
            <div className="flex items-center justify-between mb-3">
              <span className="text-[12px] text-gray-400 font-semibold uppercase tracking-wider">Liquidity Pools</span>
              <span className={`text-[15px] font-bold font-mono ${
                (lp.lp_net_pnl ?? 0) >= 0 ? "text-[var(--wolf-emerald)]" : "text-[var(--wolf-red)]"
              }`}>
                {(lp.lp_net_pnl ?? 0) >= 0 ? "+" : ""}${(lp.lp_net_pnl ?? 0).toFixed(2)}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <ProfitMiniStat label="Fees Earned" value={`+$${(lp.lp_total_fees ?? 0).toFixed(2)}`} color="emerald" />
              <ProfitMiniStat label="IL Cost" value={`-$${(lp.lp_total_il ?? 0).toFixed(2)}`} color="red" />
              <ProfitMiniStat label="Positions" value={String(lp.lp_positions ?? 0)} />
              <ProfitMiniStat label="IL Hedges" value={String(lp.lp_hedges ?? 0)} />
            </div>
          </div>
        )}
      </div>

      {/* Bottom stats */}
      {(profit.trades ?? 0) > 0 && (
        <div className="flex items-center justify-between mt-4 pt-3 border-t border-[var(--border)] text-[11px] text-gray-500">
          <span>Best: <span className="text-[var(--wolf-emerald)] font-mono">+${(profit.best_trade ?? 0).toFixed(2)}</span></span>
          <span>Worst: <span className="text-[var(--wolf-red)] font-mono">${(profit.worst_trade ?? 0).toFixed(2)}</span></span>
          <span>{profit.winners ?? 0}W / {profit.losers ?? 0}L</span>
        </div>
      )}
    </div>
  );
}

function ProfitMiniStat({ label, value, color }: { label: string; value: string; color?: string }) {
  const colorClass = color === "emerald" ? "text-[var(--wolf-emerald)]"
    : color === "red" ? "text-[var(--wolf-red)]"
    : "text-white";
  return (
    <div>
      <p className="text-[10px] text-gray-600 uppercase tracking-wider">{label}</p>
      <p className={`text-[14px] font-semibold font-mono mt-0.5 ${colorClass}`}>{value}</p>
    </div>
  );
}

function PriceTicker({ label, price, symbol, delay }: { label: string; price?: number | null; symbol: string; delay: number }) {
  const change24h = use24hChange(symbol);

  return (
    <div className={`wolf-card p-4 flex items-center justify-between animate-in animate-in-${delay}`}>
      <span className="text-[13px] text-gray-500 font-mono">{label}-USD</span>
      {price ? (
        <div className="flex items-center gap-2">
          <span className="text-lg font-bold text-white font-mono tracking-tight">
            ${price.toLocaleString(undefined, { maximumFractionDigits: 2 })}
          </span>
          {change24h !== null && (
            <span className={`text-xs font-semibold ${change24h >= 0 ? "text-[var(--wolf-emerald)]" : "text-[var(--wolf-red)]"}`}>
              {change24h >= 0 ? "+" : ""}{change24h.toFixed(2)}%
            </span>
          )}
        </div>
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
  className,
}: {
  label: React.ReactNode;
  value: string;
  suffix?: string;
  color: string;
  delay: number;
  className?: string;
}) {
  const colorMap: Record<string, string> = {
    emerald: "text-[var(--wolf-emerald)]",
    blue: "text-[var(--wolf-blue)]",
    red: "text-[var(--wolf-red)]",
    purple: "text-[var(--wolf-purple)]",
    amber: "text-[var(--wolf-amber)]",
    cyan: "text-[var(--wolf-cyan)]",
  };

  return (
    <div className={`wolf-card stat-card stat-card-${color} p-4 md:p-5 animate-in animate-in-${delay} ${className ?? ""}`}>
      <p className="text-[11px] text-gray-500 uppercase tracking-wider font-medium">{label}</p>
      <p className={`text-xl md:text-2xl font-bold mt-1.5 md:mt-2 tracking-tight ${colorMap[color] ?? "text-white"}`}>
        {value}
        {suffix && <span className="text-[11px] font-normal text-gray-600 ml-1.5">{suffix}</span>}
      </p>
    </div>
  );
}

function AgentRow({
  name,
  agentKey,
  status,
  lastRun,
}: {
  name: string;
  agentKey?: string;
  status: string;
  lastRun: string;
}) {
  const keyMap: Record<string, "quant" | "snoop" | "sage" | "brief"> = {
    "The Quant": "quant",
    "The Snoop": "snoop",
    "The Sage": "sage",
    "The Brief": "brief",
  };
  const wolfKey = (agentKey as "quant" | "snoop" | "sage" | "brief") || keyMap[name];

  return (
    <div className="flex items-center justify-between py-2.5 px-3 -mx-3 rounded-lg hover:bg-[var(--surface-hover)]/50 transition-colors">
      <div className="flex items-center gap-3">
        {wolfKey ? (
          <WolfHead agent={wolfKey} size={28} />
        ) : (
          <div
            className={`w-1.5 h-1.5 rounded-full ${
              status === "active" ? "bg-[var(--wolf-emerald)]" : "bg-gray-600"
            }`}
            style={status === "active" ? { boxShadow: "0 0 6px var(--wolf-emerald)" } : undefined}
          />
        )}
        <span className="text-[13px] text-gray-300">{name}</span>
      </div>
      <span className="text-[11px] text-gray-600 font-mono">{lastRun}</span>
    </div>
  );
}
