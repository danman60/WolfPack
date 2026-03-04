"use client";

import { useState } from "react";
import {
  useAutoTraderStatus,
  useToggleAutoTrader,
  useAutoTraderTrades,
  useConfigureAutoTrader,
  usePositionActions,
} from "@/lib/hooks/useIntelligence";

export default function AutoBotPage() {
  const { data: status } = useAutoTraderStatus();
  const { data: trades } = useAutoTraderTrades(30);
  const { data: positionActions } = usePositionActions("pending");
  const toggleMutation = useToggleAutoTrader();
  const configMutation = useConfigureAutoTrader();

  const [editEquity, setEditEquity] = useState("");
  const [editThreshold, setEditThreshold] = useState("");
  const [configSaved, setConfigSaved] = useState(false);

  const enabled = status?.enabled ?? false;
  const equity = status?.equity ?? 0;
  const startingEquity = status?.starting_equity ?? 5000;
  const realizedPnl = status?.realized_pnl ?? 0;
  const unrealizedPnl = status?.unrealized_pnl ?? 0;
  const returnPct = startingEquity > 0 ? ((equity - startingEquity) / startingEquity) * 100 : 0;
  const positions = status?.positions ?? [];

  const handleSaveConfig = () => {
    const updates: { equity?: number; conviction_threshold?: number } = {};
    if (editEquity) updates.equity = Number(editEquity);
    if (editThreshold) updates.conviction_threshold = Number(editThreshold);
    if (Object.keys(updates).length === 0) return;
    configMutation.mutate(updates, {
      onSuccess: () => {
        setConfigSaved(true);
        setEditEquity("");
        setEditThreshold("");
        setTimeout(() => setConfigSaved(false), 2000);
      },
    });
  };

  return (
    <div className="space-y-7">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="page-header">
          <h1 className="page-title">Auto-Bot</h1>
          <p className="page-subtitle">
            Autonomous trading powered by Brief intelligence
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span
            className={`px-3 py-1 rounded-full text-xs font-bold ${
              enabled
                ? "bg-[var(--wolf-emerald)]/15 text-[var(--wolf-emerald)]"
                : "bg-gray-700/50 text-gray-400"
            }`}
          >
            {enabled ? "Active" : "Paused"}
          </span>
          <button
            onClick={() => toggleMutation.mutate()}
            disabled={toggleMutation.isPending}
            className={`px-4 py-2 rounded-lg text-sm font-semibold transition ${
              enabled
                ? "bg-[var(--wolf-red)]/20 text-[var(--wolf-red)] hover:bg-[var(--wolf-red)]/30"
                : "bg-[var(--wolf-emerald)]/20 text-[var(--wolf-emerald)] hover:bg-[var(--wolf-emerald)]/30"
            }`}
          >
            {toggleMutation.isPending ? "..." : enabled ? "Disable" : "Enable"}
          </button>
        </div>
      </div>

      {/* How It Works */}
      <div className="wolf-card p-5 border-l-2 border-[var(--wolf-amber)]">
        <p className="text-sm text-gray-300 leading-relaxed">
          <span className="text-[var(--wolf-amber)] font-semibold">How it works:</span>{" "}
          The Auto-Bot follows Brief intelligence — when Brief recommends a trade above
          the conviction threshold, the bot executes it automatically. It also manages
          positions by auto-executing close, stop-loss, and take-profit adjustments.
          Operates a separate equity bucket from manual trading.
        </p>
      </div>

      {/* Bucket Stats */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <StatCard label="Equity" value={`$${equity.toLocaleString()}`} color="emerald" />
        <StatCard label="Starting" value={`$${startingEquity.toLocaleString()}`} color="blue" />
        <StatCard
          label="Realized P&L"
          value={`${realizedPnl >= 0 ? "+" : ""}$${realizedPnl.toFixed(2)}`}
          color={realizedPnl >= 0 ? "emerald" : "red"}
        />
        <StatCard
          label="Unrealized P&L"
          value={`${unrealizedPnl >= 0 ? "+" : ""}$${unrealizedPnl.toFixed(2)}`}
          color={unrealizedPnl >= 0 ? "emerald" : "red"}
        />
        <StatCard
          label="Return"
          value={`${returnPct >= 0 ? "+" : ""}${returnPct.toFixed(2)}%`}
          color={returnPct >= 0 ? "emerald" : "red"}
        />
      </div>

      {/* Configuration */}
      <div className="wolf-card p-6">
        <div className="flex items-center gap-2 mb-5">
          <div className="w-1 h-4 rounded-full bg-[var(--wolf-purple)]" />
          <h2 className="section-title">Configuration</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="text-xs text-gray-500 uppercase">Conviction Threshold</label>
            <div className="flex items-center gap-2 mt-1">
              <input
                type="number"
                min={50}
                max={100}
                placeholder={String(status?.conviction_threshold ?? 75)}
                value={editThreshold}
                onChange={(e) => setEditThreshold(e.target.value)}
                className="w-full bg-[var(--surface)] border border-[var(--border)] rounded-md px-3 py-2 text-white text-sm"
              />
              <span className="text-sm text-gray-400">%</span>
            </div>
            <p className="text-[10px] text-gray-600 mt-1">
              Current: {status?.conviction_threshold ?? 75}% — Only executes recs above this level
            </p>
          </div>
          <div>
            <label className="text-xs text-gray-500 uppercase">Equity Allocation</label>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-sm text-gray-400">$</span>
              <input
                type="number"
                min={100}
                placeholder={String(startingEquity)}
                value={editEquity}
                onChange={(e) => setEditEquity(e.target.value)}
                className="w-full bg-[var(--surface)] border border-[var(--border)] rounded-md px-3 py-2 text-white text-sm"
              />
            </div>
            <p className="text-[10px] text-gray-600 mt-1">
              Resets equity if no open positions
            </p>
          </div>
          <div className="flex items-end">
            <button
              onClick={handleSaveConfig}
              disabled={configMutation.isPending || (!editEquity && !editThreshold)}
              className="px-5 py-2 bg-[var(--wolf-purple)]/20 text-[var(--wolf-purple)] rounded-md text-sm font-semibold hover:bg-[var(--wolf-purple)]/30 transition disabled:opacity-50"
            >
              {configMutation.isPending ? "Saving..." : configSaved ? "Saved!" : "Save Config"}
            </button>
          </div>
        </div>
      </div>

      {/* Open Positions */}
      <div className="wolf-card p-6">
        <div className="flex items-center gap-2 mb-5">
          <div className="w-1 h-4 rounded-full bg-[var(--wolf-emerald)]" />
          <h2 className="section-title">Open Positions</h2>
          <span className="ml-auto text-[11px] text-gray-500 font-mono">
            {positions.length} active
          </span>
        </div>
        {positions.length > 0 ? (
          <div className="space-y-2">
            {positions.map((pos: Record<string, unknown>) => {
              const pnl = Number(pos.unrealized_pnl ?? 0);
              return (
                <div
                  key={pos.symbol as string}
                  className="flex items-center justify-between py-3 border-b border-[var(--border)] last:border-0"
                >
                  <div className="flex items-center gap-4">
                    <span
                      className={`px-3 py-1 rounded text-xs font-bold uppercase ${
                        pos.direction === "long"
                          ? "bg-[var(--wolf-emerald)]/20 text-[var(--wolf-emerald)]"
                          : "bg-[var(--wolf-red)]/20 text-[var(--wolf-red)]"
                      }`}
                    >
                      {pos.direction as string}
                    </span>
                    <div>
                      <span className="text-white font-mono font-semibold">{pos.symbol as string}</span>
                      <p className="text-xs text-gray-400 mt-0.5 font-mono">
                        Entry: ${Number(pos.entry_price).toLocaleString()} | Size: ${Number(pos.size_usd).toFixed(0)}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-6">
                    <div className="text-right">
                      <div className="text-xs text-gray-500">P&L</div>
                      <div className={`text-sm font-bold ${pnl >= 0 ? "text-[var(--wolf-emerald)]" : "text-[var(--wolf-red)]"}`}>
                        {pnl >= 0 ? "+" : ""}${pnl.toFixed(2)}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-xs text-gray-500">Current</div>
                      <div className="text-sm text-white font-mono">
                        ${Number(pos.current_price).toLocaleString()}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="text-center py-6 text-gray-500 text-sm">
            No open auto-bot positions
          </div>
        )}
      </div>

      {/* Pending Position Actions */}
      {positionActions && positionActions.length > 0 && (
        <div className="wolf-card p-6">
          <div className="flex items-center gap-2 mb-5">
            <div className="w-1 h-4 rounded-full bg-[var(--wolf-cyan)]" />
            <h2 className="section-title">Pending Position Actions</h2>
          </div>
          <div className="space-y-2">
            {positionActions.map((pa) => (
              <div
                key={pa.id}
                className="flex items-center justify-between py-3 border-b border-[var(--border)] last:border-0"
              >
                <div className="flex items-center gap-3">
                  <span className={`px-2 py-1 rounded text-[10px] font-bold uppercase ${
                    pa.action === "close" ? "bg-[var(--wolf-red)]/20 text-[var(--wolf-red)]"
                    : pa.action === "adjust_stop" ? "bg-[var(--wolf-amber)]/20 text-[var(--wolf-amber)]"
                    : "bg-[var(--wolf-cyan)]/20 text-[var(--wolf-cyan)]"
                  }`}>
                    {pa.action.replace("_", " ")}
                  </span>
                  <span className="text-white font-mono text-sm">{pa.symbol}</span>
                  <span className="text-xs text-gray-500">{pa.reason}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className={`text-[10px] font-semibold px-2 py-0.5 rounded ${
                    pa.urgency === "high" ? "bg-[var(--wolf-red)]/15 text-[var(--wolf-red)]"
                    : pa.urgency === "medium" ? "bg-[var(--wolf-amber)]/15 text-[var(--wolf-amber)]"
                    : "bg-[var(--surface)] text-gray-400"
                  }`}>
                    {pa.urgency}
                  </span>
                  <span className="text-[10px] text-gray-600">
                    {new Date(pa.created_at).toLocaleTimeString()}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Activity Log */}
      <div className="wolf-card p-6">
        <div className="flex items-center gap-2 mb-5">
          <div className="w-1 h-4 rounded-full bg-[var(--wolf-amber)]" />
          <h2 className="section-title">Activity Log</h2>
          <span className="ml-auto text-[11px] text-gray-500 font-mono">
            {trades?.length ?? 0} trades
          </span>
        </div>
        {trades && trades.length > 0 ? (
          <div className="space-y-2">
            {trades.map((t) => (
              <div
                key={t.id}
                className="flex items-center justify-between py-2.5 px-3 -mx-3 rounded-lg hover:bg-[var(--surface-hover)]/50 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <span
                    className={`badge ${
                      t.direction === "long"
                        ? "bg-[var(--wolf-emerald)]/15 text-[var(--wolf-emerald)]"
                        : "bg-[var(--wolf-red)]/15 text-[var(--wolf-red)]"
                    }`}
                  >
                    {t.direction}
                  </span>
                  <span className="text-[13px] text-white font-mono font-medium">{t.symbol}</span>
                  <span className="text-[11px] text-gray-500 font-mono">
                    @ ${t.entry_price.toLocaleString()}
                  </span>
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-[11px] text-gray-400 font-mono">${t.size_usd.toFixed(0)}</span>
                  <div className="w-12 h-1.5 rounded-full bg-[var(--surface)] overflow-hidden">
                    <div
                      className="h-full rounded-full bg-[var(--wolf-amber)]"
                      style={{ width: `${t.conviction}%` }}
                    />
                  </div>
                  <span className="text-[11px] text-gray-400 font-mono w-8 text-right">{t.conviction}%</span>
                  <span className={`text-[10px] font-semibold px-2 py-0.5 rounded ${
                    t.status === "open" ? "bg-[var(--wolf-emerald)]/15 text-[var(--wolf-emerald)]" : "bg-[var(--surface)] text-gray-400"
                  }`}>
                    {t.status}
                  </span>
                  <span className="text-[10px] text-gray-600">
                    {new Date(t.opened_at).toLocaleDateString()}
                  </span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-6 text-gray-500 text-sm">
            No auto-bot trades yet. Enable the bot and run intelligence to start.
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color: string;
}) {
  const colorMap: Record<string, string> = {
    emerald: "text-[var(--wolf-emerald)]",
    blue: "text-[var(--wolf-blue)]",
    red: "text-[var(--wolf-red)]",
    purple: "text-[var(--wolf-purple)]",
    amber: "text-[var(--wolf-amber)]",
  };

  return (
    <div className={`wolf-card stat-card stat-card-${color} p-4`}>
      <p className="text-[11px] text-gray-500 uppercase tracking-wider font-medium">{label}</p>
      <p className={`text-xl font-bold mt-1.5 tracking-tight ${colorMap[color] ?? "text-white"}`}>
        {value}
      </p>
    </div>
  );
}
