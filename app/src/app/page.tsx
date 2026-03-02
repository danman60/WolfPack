"use client";

import { useExchange } from "@/lib/exchange";

export default function Dashboard() {
  const { activeExchange, config } = useExchange();

  return (
    <div className="space-y-6">
      {/* Portfolio Summary */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard label="Portfolio Value" value="—" suffix="USD" color="emerald" />
        <StatCard label="Unrealized P&L" value="—" suffix="USD" color="blue" />
        <StatCard label="Open Positions" value="—" color="purple" />
        <StatCard label="Win Rate" value="—" suffix="%" color="amber" />
      </div>

      {/* Active Exchange Banner */}
      <div className="bg-surface-elevated border border-[var(--border)] rounded-lg p-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-2 h-2 bg-[var(--wolf-emerald)] rounded-full pulse-glow" />
          <span className="text-sm text-gray-400">
            Active Exchange: <span className="text-white font-semibold">{config.name}</span>
          </span>
        </div>
        <span className="text-xs text-gray-500 font-mono">{config.rpcUrl}</span>
      </div>

      {/* Intelligence Summary + Positions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Latest Intelligence */}
        <div className="bg-surface-elevated border border-[var(--border)] rounded-lg p-6">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            🐺 Intelligence Brief
          </h2>
          <div className="space-y-3">
            <AgentStatus name="The Quant" status="idle" lastRun="—" />
            <AgentStatus name="The Snoop" status="idle" lastRun="—" />
            <AgentStatus name="The Sage" status="idle" lastRun="—" />
            <AgentStatus name="The Brief" status="idle" lastRun="—" />
          </div>
          <p className="text-xs text-gray-500 mt-4">
            Connect the intelligence service to activate agents.
          </p>
        </div>

        {/* Open Positions */}
        <div className="bg-surface-elevated border border-[var(--border)] rounded-lg p-6">
          <h2 className="text-lg font-semibold text-white mb-4">
            Open Positions ({config.name})
          </h2>
          <div className="text-center py-8 text-gray-500 text-sm">
            Connect wallet to view positions
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  suffix,
  color,
}: {
  label: string;
  value: string;
  suffix?: string;
  color: string;
}) {
  const colorMap: Record<string, string> = {
    emerald: "text-[var(--wolf-emerald)]",
    blue: "text-[var(--wolf-blue)]",
    purple: "text-[var(--wolf-purple)]",
    amber: "text-[var(--wolf-amber)]",
  };

  return (
    <div className="bg-surface-elevated border border-[var(--border)] rounded-lg p-4">
      <p className="text-xs text-gray-500 uppercase tracking-wider">{label}</p>
      <p className={`text-2xl font-bold mt-1 ${colorMap[color] ?? "text-white"}`}>
        {value}
        {suffix && <span className="text-sm font-normal text-gray-500 ml-1">{suffix}</span>}
      </p>
    </div>
  );
}

function AgentStatus({
  name,
  status,
  lastRun,
}: {
  name: string;
  status: "active" | "idle" | "error";
  lastRun: string;
}) {
  const statusColors = {
    active: "bg-[var(--wolf-emerald)]",
    idle: "bg-gray-600",
    error: "bg-[var(--wolf-red)]",
  };

  return (
    <div className="flex items-center justify-between py-2 border-b border-[var(--border)] last:border-0">
      <div className="flex items-center gap-3">
        <div className={`w-2 h-2 rounded-full ${statusColors[status]}`} />
        <span className="text-sm text-gray-300">{name}</span>
      </div>
      <span className="text-xs text-gray-500">{lastRun}</span>
    </div>
  );
}
