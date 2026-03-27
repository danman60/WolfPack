"use client";

import { useState } from "react";
import {
  useAutoTraderStatus,
  useToggleAutoTrader,
  useAutoTraderTrades,
  useConfigureAutoTrader,
  usePositionActions,
  useSetYoloLevel,
} from "@/lib/hooks/useIntelligence";

const YOLO_LABELS = [
  { level: 1, label: "Cautious", icon: "\u{1F6E1}\uFE0F", color: "text-[var(--wolf-emerald)]" },
  { level: 2, label: "Balanced", icon: "\u2696\uFE0F", color: "text-[var(--wolf-blue)]" },
  { level: 3, label: "Aggressive", icon: "\u{1F525}", color: "text-[var(--wolf-amber)]" },
  { level: 4, label: "YOLO", icon: "\u{1F680}", color: "text-[var(--wolf-purple)]" },
  { level: 5, label: "Full Send", icon: "\u{1F480}", color: "text-[var(--wolf-red)]" },
];

const YOLO_DEFAULTS: Record<number, { conviction_threshold: number; veto_floor: number; max_trades_per_day: number; penalty_multiplier: number; cooldown_seconds: number; max_size_pct: number; rejection_cooldown_hours: number }> = {
  1: { conviction_threshold: 85, veto_floor: 60, max_trades_per_day: 3, penalty_multiplier: 1.5, cooldown_seconds: 2700, max_size_pct: 10, rejection_cooldown_hours: 4 },
  2: { conviction_threshold: 75, veto_floor: 55, max_trades_per_day: 4, penalty_multiplier: 1.0, cooldown_seconds: 1800, max_size_pct: 15, rejection_cooldown_hours: 2 },
  3: { conviction_threshold: 65, veto_floor: 45, max_trades_per_day: 8, penalty_multiplier: 0.5, cooldown_seconds: 900, max_size_pct: 20, rejection_cooldown_hours: 0.5 },
  4: { conviction_threshold: 55, veto_floor: 35, max_trades_per_day: 12, penalty_multiplier: 0.25, cooldown_seconds: 300, max_size_pct: 25, rejection_cooldown_hours: 0.25 },
  5: { conviction_threshold: 45, veto_floor: 25, max_trades_per_day: 20, penalty_multiplier: 0.0, cooldown_seconds: 0, max_size_pct: 25, rejection_cooldown_hours: 0 },
};

export default function AutoBotPage() {
  const { data: status } = useAutoTraderStatus();
  const { data: trades } = useAutoTraderTrades(30);
  const { data: positionActions } = usePositionActions("pending");
  const toggleMutation = useToggleAutoTrader();
  const configMutation = useConfigureAutoTrader();

  const yoloMutation = useSetYoloLevel();
  const [pendingYolo, setPendingYolo] = useState<number | null>(null);

  const [editEquity, setEditEquity] = useState("");
  const [editThreshold, setEditThreshold] = useState("");
  const [configSaved, setConfigSaved] = useState(false);

  const currentYolo = pendingYolo ?? status?.yolo_level ?? 4;

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

      {/* YOLO Meter */}
      <div className="wolf-card p-6">
        <div className="flex items-center gap-2 mb-5">
          <div className="w-1 h-4 rounded-full bg-[var(--wolf-amber)]" />
          <h2 className="section-title">YOLO Meter</h2>
          <span className="ml-auto text-xs text-gray-500">
            Trading aggressiveness
          </span>
        </div>

        {/* Slider */}
        <div className="mb-6">
          <div className="relative">
            {/* Gradient track background */}
            <div className="h-2 rounded-full bg-gradient-to-r from-[var(--wolf-emerald)] via-[var(--wolf-amber)] to-[var(--wolf-red)]" />
            {/* Range input overlay */}
            <input
              type="range"
              min={1}
              max={5}
              step={1}
              value={currentYolo}
              onChange={(e) => {
                const level = Number(e.target.value);
                setPendingYolo(level);
                yoloMutation.mutate(level, {
                  onSuccess: () => setPendingYolo(null),
                });
              }}
              className="absolute inset-0 w-full opacity-0 cursor-pointer h-2"
              style={{ top: 0 }}
            />
            {/* Custom thumb indicator */}
            <div
              className="absolute top-1/2 -translate-y-1/2 w-5 h-5 rounded-full border-2 border-white bg-[var(--surface)] shadow-lg shadow-black/50 pointer-events-none transition-all duration-200"
              style={{ left: `${((currentYolo - 1) / 4) * 100}%`, transform: `translateX(-50%) translateY(-50%)` }}
            />
          </div>

          {/* Labels */}
          <div className="flex justify-between mt-3 px-0">
            {YOLO_LABELS.map((item) => (
              <button
                key={item.level}
                onClick={() => {
                  setPendingYolo(item.level);
                  yoloMutation.mutate(item.level, {
                    onSuccess: () => setPendingYolo(null),
                  });
                }}
                className={`flex flex-col items-center gap-1 transition-all ${
                  currentYolo === item.level
                    ? "opacity-100 scale-105"
                    : "opacity-40 hover:opacity-70"
                }`}
              >
                <span className="text-base">{item.icon}</span>
                <span className={`text-[10px] font-bold uppercase tracking-wider ${
                  currentYolo === item.level ? item.color : "text-gray-500"
                }`}>
                  {item.label}
                </span>
              </button>
            ))}
          </div>
        </div>

        {/* Active profile details */}
        {(() => {
          const profile = status?.yolo_profile ?? YOLO_DEFAULTS[currentYolo as keyof typeof YOLO_DEFAULTS];
          if (!profile) return null;
          return (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3 p-4 rounded-lg bg-[var(--surface)] border border-[var(--border)]">
              <ProfileStat label="Conviction" value={`${profile.conviction_threshold}%`} />
              <ProfileStat label="Veto Floor" value={`${profile.veto_floor}%`} />
              <ProfileStat label="Max Trades/Day" value={String(profile.max_trades_per_day)} />
              <ProfileStat label="Penalty Scale" value={`${(profile.penalty_multiplier * 100).toFixed(0)}%`} />
              <ProfileStat label="Cooldown" value={profile.cooldown_seconds >= 60 ? `${Math.round(profile.cooldown_seconds / 60)}min` : profile.cooldown_seconds > 0 ? `${profile.cooldown_seconds}s` : "None"} />
              <ProfileStat label="Max Size" value={`${profile.max_size_pct}%`} />
            </div>
          );
        })()}
      </div>

      {/* Advanced Configuration (collapsed) */}
      <details className="wolf-card">
        <summary className="p-5 cursor-pointer text-sm text-gray-400 hover:text-gray-300 transition select-none">
          Advanced Configuration
        </summary>
        <div className="px-6 pb-6 pt-1">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="text-xs text-gray-500 uppercase">Conviction Override</label>
              <div className="flex items-center gap-2 mt-1">
                <input
                  type="number"
                  min={30}
                  max={100}
                  placeholder={String(status?.conviction_threshold ?? 55)}
                  value={editThreshold}
                  onChange={(e) => setEditThreshold(e.target.value)}
                  className="w-full bg-[var(--surface)] border border-[var(--border)] rounded-md px-3 py-2 text-white text-sm"
                />
                <span className="text-sm text-gray-400">%</span>
              </div>
              <p className="text-[10px] text-gray-600 mt-1">
                Overrides YOLO meter conviction
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
      </details>

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

function ProfileStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="text-center">
      <p className="text-[10px] text-gray-500 uppercase tracking-wider">{label}</p>
      <p className="text-sm text-white font-mono font-semibold mt-0.5">{value}</p>
    </div>
  );
}
