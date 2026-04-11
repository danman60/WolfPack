"use client";

import { useState } from "react";
import Link from "next/link";
import { useExchange } from "@/lib/exchange";
import { useAgentOutputs, useAgentStatus, useRecommendations, usePortfolio, usePortfolioHistory, useWatchlist, useAutoTraderStatus, useProfit, useStrategyMode, useClosePosition, useSetYoloLevel, useWalletsSummary } from "@/lib/hooks/useIntelligence";
import { useWalletContext } from "@/lib/wallet/context";
import { WolfHead } from "@/components/WolfHead";
import { usePrice, use24hChange } from "@/lib/hooks/useMarketData";
import { useLPStatus } from "@/lib/hooks/usePools";
import { Term } from "@/components/Term";
import { AreaChart, Area, ResponsiveContainer } from "recharts";

export default function Dashboard() {
  const { perpWallet } = useWalletContext();
  const { config } = useExchange();
  const { data: agentOutputs } = useAgentOutputs();
  const { data: agentStatus } = useAgentStatus();
  const { data: recommendations } = useRecommendations("pending");
  const { data: portfolio } = usePortfolio(perpWallet);
  const { data: btcPrice } = usePrice("BTC");
  const { data: ethPrice } = usePrice("ETH");
  const { data: watchlist } = useWatchlist();
  const { data: autoTrader } = useAutoTraderStatus(perpWallet);
  const { data: lpStatus } = useLPStatus();
  const { data: strategyMode } = useStrategyMode();
  const { data: history } = usePortfolioHistory(perpWallet, 200);
  const { data: walletSummaries } = useWalletsSummary();
  const perpWallets = (walletSummaries ?? []).filter((w: any) => w.status === "active");

  const agents = agentStatus?.agents ?? [];
  const isActive = portfolio?.status === "active";
  const isLive = strategyMode?.mode === "live";

  // Compact equity curve data
  const snapshots = history?.snapshots ?? [];
  const equityData = snapshots.map(
    (s: { created_at: string; equity: number }) => ({
      time: new Date(s.created_at).getTime(),
      equity: s.equity,
    })
  );
  const currentEquity = equityData.length > 0 ? equityData[equityData.length - 1].equity : null;
  const startEquity = equityData.length > 0 ? equityData[0].equity : null;
  const equityUp = currentEquity && startEquity ? currentEquity >= startEquity : true;

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

      {/* YOLO Meter */}
      <YoloMeter />

      {/* Profit Report */}
      <ProfitReport />

      {/* 7-Day Equity Curve */}
      {equityData.length > 1 && (
        <div className="wolf-card p-4 relative">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[11px] font-medium text-gray-500 uppercase tracking-wider">Equity Curve (7d)</span>
            {currentEquity && (
              <span className={`text-[15px] font-bold ${equityUp ? "text-emerald-400" : "text-red-400"}`}>
                ${currentEquity.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            )}
          </div>
          <div style={{ height: 120 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={equityData} margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={equityUp ? "#10b981" : "#ef4444"} stopOpacity={0.3} />
                    <stop offset="100%" stopColor={equityUp ? "#10b981" : "#ef4444"} stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <Area
                  type="monotone"
                  dataKey="equity"
                  stroke={equityUp ? "#10b981" : "#ef4444"}
                  strokeWidth={2}
                  fill="url(#equityGrad)"
                  dot={false}
                  isAnimationActive={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Evolution Wallets */}
      {perpWallets.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-1 h-4 rounded-full bg-[var(--wolf-purple)]" />
              <h2 className="text-[15px] font-semibold text-white tracking-tight">Evolution Wallets</h2>
            </div>
            <Link href="/evolution" className="text-[11px] text-[var(--wolf-purple)] hover:text-white transition-colors">
              View All →
            </Link>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {perpWallets.map((w: any) => {
              const returnPct = w.starting_equity > 0
                ? (((w.equity || w.starting_equity) - w.starting_equity) / w.starting_equity * 100)
                : 0;
              const profitable = (w.total_pnl || 0) > 0;
              return (
                <Link key={w.name} href="/evolution" className="block">
                  <div className={`wolf-card p-4 hover:border-white/20 transition-colors ${profitable ? "border-emerald-500/20" : "border-red-500/20"}`}>
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <span className="text-[13px] font-semibold text-white">{w.display_name || w.name}</span>
                        {w.version && (
                          <span className="text-[9px] px-1.5 py-0.5 rounded bg-white/5 text-gray-500 font-mono">v{w.version}</span>
                        )}
                      </div>
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-[var(--wolf-purple)]/15 text-[var(--wolf-purple)] font-semibold">
                        YOLO {w.yolo_level || w.config?.yolo_level || "?"}
                      </span>
                    </div>
                    <div className="grid grid-cols-3 gap-2 text-center">
                      <div>
                        <p className="text-[10px] text-gray-500 uppercase">Equity</p>
                        <p className="text-[14px] font-bold text-white">${(w.equity || w.starting_equity || 0).toLocaleString(undefined, {maximumFractionDigits: 0})}</p>
                      </div>
                      <div>
                        <p className="text-[10px] text-gray-500 uppercase">P&L</p>
                        <p className={`text-[14px] font-bold ${profitable ? "text-emerald-400" : "text-red-400"}`}>
                          {(w.total_pnl || 0) >= 0 ? "+" : ""}${(w.total_pnl || 0).toFixed(0)}
                        </p>
                      </div>
                      <div>
                        <p className="text-[10px] text-gray-500 uppercase">Trades</p>
                        <p className="text-[14px] font-bold text-white">{w.trade_count || 0}</p>
                      </div>
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
        </div>
      )}

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
                  <AgentRow name="The Snoop" status={agentOutputs?.snoop ? "active" : "idle"} lastRun={agentOutputs?.snoop ? new Date(agentOutputs.snoop.created_at).toLocaleTimeString() : "--"} />
                  <AgentRow name="The Sage" status={agentOutputs?.sage ? "active" : "idle"} lastRun={agentOutputs?.sage ? new Date(agentOutputs.sage.created_at).toLocaleTimeString() : "--"} />
                  <AgentRow name="The Brief" status={agentOutputs?.brief ? "active" : "idle"} lastRun={agentOutputs?.brief ? new Date(agentOutputs.brief.created_at).toLocaleTimeString() : "--"} />
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

const YOLO_LABELS: Record<number, string> = {
  0: "Off",
  1: "Cautious",
  2: "Balanced",
  3: "Aggressive",
  4: "YOLO",
  5: "Full Send",
};

const YOLO_COLORS: Record<number, string> = {
  0: "#6b7280",
  1: "#22c55e",
  2: "#10b981",
  3: "#eab308",
  4: "#f97316",
  5: "#ef4444",
};

function YoloMeter() {
  const { data: autoTrader } = useAutoTraderStatus();
  const setYolo = useSetYoloLevel();
  const currentLevel = autoTrader?.enabled === false ? 0 : (autoTrader?.yolo_level ?? 4);
  const profile = autoTrader?.yolo_profile;
  const color = YOLO_COLORS[currentLevel] ?? "#6b7280";
  const label = YOLO_LABELS[currentLevel] ?? "Unknown";

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const level = parseInt(e.target.value, 10);
    setYolo.mutate(level);
  };

  return (
    <div className="wolf-card p-4 animate-in animate-in-1">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="w-1 h-4 rounded-full" style={{ backgroundColor: color }} />
          <h2 className="text-[15px] font-semibold text-white tracking-tight">YOLO Meter</h2>
        </div>
        <span
          className="text-[13px] font-bold px-2 py-0.5 rounded"
          style={{ color, backgroundColor: `${color}20` }}
        >
          {label}
        </span>
      </div>

      {/* Slider */}
      <div className="relative mb-3">
        <input
          type="range"
          min={0}
          max={5}
          step={1}
          value={currentLevel}
          onChange={handleChange}
          disabled={setYolo.isPending}
          className="w-full h-2 rounded-full appearance-none cursor-pointer disabled:opacity-50"
          style={{
            background: `linear-gradient(to right, #6b7280 0%, #22c55e 20%, #10b981 40%, #eab308 60%, #f97316 80%, #ef4444 100%)`,
            accentColor: color,
          }}
        />
        <div className="flex justify-between mt-1.5 px-0.5">
          {[0, 1, 2, 3, 4, 5].map((l) => (
            <span
              key={l}
              className={`text-[9px] font-medium ${
                l === currentLevel ? "text-white" : "text-gray-600"
              }`}
            >
              {l}
            </span>
          ))}
        </div>
      </div>

      {/* Stats row */}
      {profile && currentLevel > 0 && (
        <div className="flex items-center justify-center gap-3 text-[11px] text-gray-500">
          <span>Floor: <span className="text-gray-300 font-mono">{profile.conviction_threshold}</span></span>
          <span className="text-gray-700">|</span>
          <span>Max/day: <span className="text-gray-300 font-mono">{profile.max_trades_per_day}</span></span>
          <span className="text-gray-700">|</span>
          <span>Cooldown: <span className="text-gray-300 font-mono">{profile.cooldown_seconds < 60 ? `${profile.cooldown_seconds}s` : `${Math.round(profile.cooldown_seconds / 60)}m`}</span></span>
        </div>
      )}
    </div>
  );
}

function ProfitReport() {
  const { perpWallet } = useWalletContext();
  const [hours, setHours] = useState(24);
  const [locking, setLocking] = useState(false);
  const { data: profit, isFetching } = useProfit(hours);
  const { data: autoTraderData } = useAutoTraderStatus(perpWallet);
  const closePosition = useClosePosition();

  const periods = [
    { label: "1H", value: 1 },
    { label: "4H", value: 4 },
    { label: "12H", value: 12 },
    { label: "24H", value: 24 },
  ];

  if (!profit) return null;

  const realizedPnl = profit.total_pnl ?? 0;
  const unrealizedPnl = autoTraderData?.unrealized_pnl ?? 0;
  const positions = (autoTraderData?.positions ?? []) as Array<Record<string, unknown>>;
  const totalPnl = realizedPnl + unrealizedPnl;

  // For the hero: include LP if available
  const hasCombined = profit.combined_pnl !== undefined;
  const heroRealized = hasCombined ? profit.combined_pnl : realizedPnl;
  const heroPnl = (heroRealized ?? 0) + unrealizedPnl;
  const lp = profit.lp;

  // Profitable positions for lock-in
  const profitablePositions = positions.filter((p) => ((p.unrealized_pnl as number) ?? 0) > 0);
  const profitableUnrealized = profitablePositions.reduce((sum, p) => sum + ((p.unrealized_pnl as number) ?? 0), 0);

  const handleLockIn = async () => {
    if (locking || profitablePositions.length === 0) return;
    setLocking(true);
    try {
      for (const pos of profitablePositions) {
        await closePosition.mutateAsync({
          symbol: pos.symbol as string,
          exchange: "hyperliquid",
        });
      }
    } finally {
      setLocking(false);
    }
  };

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

      {/* Total P&L Hero (realized + unrealized) */}
      <div className="text-center mb-3">
        <p className="text-[11px] text-gray-500 uppercase tracking-wider font-medium mb-1">
          Total P&L — Last {hours}h
        </p>
        <p className={`text-3xl md:text-4xl font-bold tracking-tight ${
          heroPnl >= 0 ? "text-[var(--wolf-emerald)]" : "text-[var(--wolf-red)]"
        }`}>
          {heroPnl >= 0 ? "+" : ""}${Math.abs(heroPnl).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </p>
      </div>

      {/* Realized / Unrealized Breakdown */}
      <div className="flex items-center justify-center gap-4 sm:gap-6 mb-3 text-[13px]">
        <div className="text-center">
          <p className="text-[11px] text-gray-500 uppercase tracking-wider mb-0.5">Realized</p>
          <p className={`font-semibold font-mono ${realizedPnl >= 0 ? "text-[var(--wolf-emerald)]" : "text-[var(--wolf-red)]"}`}>
            {realizedPnl >= 0 ? "+" : ""}${Math.abs(realizedPnl).toFixed(2)}
          </p>
        </div>
        <div className="w-px h-6 bg-[var(--border)]" />
        <div className="text-center">
          <p className="text-[11px] text-gray-500 uppercase tracking-wider mb-0.5">Unrealized</p>
          <p className={`font-semibold font-mono ${unrealizedPnl >= 0 ? "text-[var(--wolf-emerald)]" : "text-[var(--wolf-red)]"}`}>
            {unrealizedPnl >= 0 ? "+" : ""}${Math.abs(unrealizedPnl).toFixed(2)}
          </p>
        </div>
        {positions.length > 0 && (
          <>
            <div className="w-px h-6 bg-[var(--border)]" />
            <div className="text-center">
              <p className="text-[11px] text-gray-500 uppercase tracking-wider mb-0.5">Open</p>
              <p className="font-semibold font-mono text-[var(--wolf-cyan)]">{positions.length}</p>
            </div>
          </>
        )}
      </div>

      {/* Lock In Button */}
      {profitableUnrealized > 0 && (
        <div className="flex justify-center mb-4">
          <button
            onClick={handleLockIn}
            disabled={locking}
            className="px-4 py-2 rounded-lg text-[12px] font-bold bg-[var(--wolf-emerald)] text-white hover:brightness-110 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {locking ? "Closing..." : `Lock In +$${profitableUnrealized.toFixed(2)}`}
          </button>
        </div>
      )}

      {/* Open Positions Summary */}
      {positions.length > 0 && (
        <div className="mb-4 bg-[var(--surface)]/50 rounded-lg px-3 py-2">
          {positions.map((pos, i) => {
            const pnl = (pos.unrealized_pnl as number) ?? 0;
            const symbol = (pos.symbol as string) ?? "???";
            const direction = (pos.direction as string) ?? (pos.side as string) ?? "";
            const sl = pos.stop_loss as number | undefined;
            const tp = pos.take_profit as number | undefined;
            return (
              <div key={i} className="flex items-center justify-between text-[12px] py-0.5">
                <span className="text-gray-300">
                  <span className="font-medium text-white">{symbol}</span>{" "}
                  <span className="text-gray-500">{direction}</span>
                  {sl && tp ? (
                    <span className="text-gray-600 ml-1">(SL ${sl.toFixed(2)} / TP ${tp.toFixed(2)})</span>
                  ) : null}
                </span>
                <span className={`font-mono font-semibold ${pnl >= 0 ? "text-[var(--wolf-emerald)]" : "text-[var(--wolf-red)]"}`}>
                  {pnl >= 0 ? "+" : ""}${pnl.toFixed(2)}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* Benchmark / Alpha */}
      {profit.benchmark && (
        <div className="flex flex-col sm:flex-row items-center justify-center gap-2 sm:gap-4 text-[12px] mb-5">
          <span className="text-gray-500">
            BTC {profit.benchmark.btc_change_pct >= 0 ? "+" : ""}{profit.benchmark.btc_change_pct.toFixed(1)}%
          </span>
          <span className="text-gray-600 hidden sm:inline">|</span>
          <span className="text-gray-400">
            Buy & Hold: <span className={`font-mono ${profit.benchmark.buy_hold_return >= 0 ? "text-gray-300" : "text-[var(--wolf-red)]"}`}>
              {profit.benchmark.buy_hold_return >= 0 ? "+" : ""}${profit.benchmark.buy_hold_return.toFixed(2)}
            </span>
          </span>
          <span className="text-gray-600 hidden sm:inline">|</span>
          <span className={`font-semibold ${
            profit.benchmark.alpha >= 0 ? "text-[var(--wolf-cyan)]" : "text-[var(--wolf-red)]"
          }`}>
            Alpha: {profit.benchmark.alpha >= 0 ? "+" : ""}${profit.benchmark.alpha.toFixed(2)}
          </span>
        </div>
      )}

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
