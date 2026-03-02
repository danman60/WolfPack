"use client";

import { useExchange } from "@/lib/exchange";
import { useAgentOutputs, useAgentStatus, useRecommendations } from "@/lib/hooks/useIntelligence";

export default function Dashboard() {
  const { config } = useExchange();
  const { data: agentOutputs } = useAgentOutputs();
  const { data: agentStatus } = useAgentStatus();
  const { data: recommendations } = useRecommendations("pending");

  const agents = agentStatus?.agents ?? [];

  return (
    <div className="space-y-6">
      {/* Portfolio Summary */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard label="Portfolio Value" value="\u2014" suffix="USD" color="emerald" />
        <StatCard label="Unrealized P&L" value="\u2014" suffix="USD" color="blue" />
        <StatCard label="Open Positions" value="\u2014" color="purple" />
        <StatCard
          label="Pending Recs"
          value={recommendations?.length?.toString() ?? "\u2014"}
          color="amber"
        />
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
            Intelligence Brief
          </h2>
          <div className="space-y-3">
            {agents.length > 0
              ? agents.map((a: { name: string; key: string; status: string; last_run: string | null }) => (
                  <AgentStatus
                    key={a.key}
                    name={a.name}
                    status={a.status === "running" ? "active" : agentOutputs?.[a.key] ? "active" : "idle"}
                    lastRun={
                      agentOutputs?.[a.key]?.created_at
                        ? new Date(agentOutputs[a.key].created_at).toLocaleTimeString()
                        : "\u2014"
                    }
                  />
                ))
              : (
                <>
                  <AgentStatus name="The Quant" status={agentOutputs?.quant ? "active" : "idle"} lastRun={agentOutputs?.quant ? new Date(agentOutputs.quant.created_at).toLocaleTimeString() : "\u2014"} />
                  <AgentStatus name="The Snoop" status="idle" lastRun="\u2014" />
                  <AgentStatus name="The Sage" status="idle" lastRun="\u2014" />
                  <AgentStatus name="The Brief" status="idle" lastRun="\u2014" />
                </>
              )}
          </div>
          {agentOutputs?.quant?.summary && (
            <div className="mt-4 pt-3 border-t border-[var(--border)]">
              <p className="text-xs text-gray-400 line-clamp-3">{agentOutputs.quant.summary}</p>
            </div>
          )}
        </div>

        {/* Pending Recommendations */}
        <div className="bg-surface-elevated border border-[var(--border)] rounded-lg p-6">
          <h2 className="text-lg font-semibold text-white mb-4">
            Trade Recommendations
          </h2>
          {recommendations && recommendations.length > 0 ? (
            <div className="space-y-3">
              {recommendations.slice(0, 5).map((rec: Record<string, unknown>) => (
                <div
                  key={rec.id as string}
                  className="flex items-center justify-between py-2 border-b border-[var(--border)] last:border-0"
                >
                  <div className="flex items-center gap-3">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                        rec.direction === "long"
                          ? "bg-[var(--wolf-emerald)]/20 text-[var(--wolf-emerald)]"
                          : "bg-[var(--wolf-red)]/20 text-[var(--wolf-red)]"
                      }`}
                    >
                      {rec.direction as string}
                    </span>
                    <span className="text-sm text-white font-mono">{rec.symbol as string}</span>
                  </div>
                  <span className="text-xs text-gray-400">
                    {rec.conviction as number}% conviction
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500 text-sm">
              No pending recommendations. Run intelligence to generate signals.
            </div>
          )}
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
  status: string;
  lastRun: string;
}) {
  const statusColors: Record<string, string> = {
    active: "bg-[var(--wolf-emerald)]",
    idle: "bg-gray-600",
    error: "bg-[var(--wolf-red)]",
  };

  return (
    <div className="flex items-center justify-between py-2 border-b border-[var(--border)] last:border-0">
      <div className="flex items-center gap-3">
        <div className={`w-2 h-2 rounded-full ${statusColors[status] ?? "bg-gray-600"}`} />
        <span className="text-sm text-gray-300">{name}</span>
      </div>
      <span className="text-xs text-gray-500">{lastRun}</span>
    </div>
  );
}
