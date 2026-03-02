"use client";

import { useExchange } from "@/lib/exchange";
import {
  useAgentOutputs,
  useModuleOutputs,
  useRunIntelligence,
  useAgentStatus,
} from "@/lib/hooks/useIntelligence";

const AGENTS = [
  { key: "quant", name: "The Quant", role: "Technical Analysis", description: "Regime detection, technical indicators, quantitative signals, chart patterns" },
  { key: "snoop", name: "The Snoop", role: "Social Intelligence", description: "Social media sentiment, news analysis, narrative tracking, community signals" },
  { key: "sage", name: "The Sage", role: "Forecasting", description: "Cross-asset correlation, weekly outlook, macro analysis, trend prediction" },
  { key: "brief", name: "The Brief", role: "Decision Synthesis", description: "Aggregates all agents, generates trade recommendations with conviction scores" },
];

const MODULES = [
  { key: "regime_detection", name: "Regime Detection", icon: "\u{1F4CA}" },
  { key: "liquidity_intel", name: "Liquidity Intel", icon: "\u{1F4A7}" },
  { key: "funding_carry", name: "Funding & Carry", icon: "\u{1F4B0}" },
  { key: "correlation", name: "Correlation", icon: "\u{1F517}" },
  { key: "volatility", name: "Volatility", icon: "\u{1F4C8}" },
  { key: "circuit_breakers", name: "Circuit Breakers", icon: "\u{1F6E1}" },
  { key: "execution_timing", name: "Execution Timing", icon: "\u{23F1}" },
  { key: "backtest", name: "Backtest", icon: "\u{1F52C}" },
];

export default function IntelligencePage() {
  const { config, activeExchange } = useExchange();
  const { data: agentOutputs, isLoading: agentsLoading } = useAgentOutputs();
  const { data: moduleOutputs } = useModuleOutputs();
  const { data: agentStatus } = useAgentStatus();
  const runIntel = useRunIntelligence();

  const statusMap = new Map<string, { status: string; last_run: string | null }>();
  if (agentStatus?.agents) {
    for (const a of agentStatus.agents) {
      statusMap.set(a.key, { status: a.status, last_run: a.last_run });
    }
  }

  return (
    <div className="space-y-6">
      <div className="border-b border-[var(--border)] pb-4 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Intelligence Brief</h1>
          <p className="text-gray-400 text-sm mt-1">
            Multi-agent AI analysis for {config.name}
          </p>
        </div>
        <button
          onClick={() => runIntel.mutate({ exchange: activeExchange, symbol: "BTC" })}
          disabled={runIntel.isPending}
          className="px-4 py-2 bg-[var(--wolf-emerald)] text-black text-sm font-semibold rounded-lg hover:brightness-110 transition disabled:opacity-50"
        >
          {runIntel.isPending ? "Running..." : "Run Intelligence"}
        </button>
      </div>

      {/* Agent Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {AGENTS.map((agent) => {
          const output = agentOutputs?.[agent.key];
          const svc = statusMap.get(agent.key);
          const status = svc?.status === "running" ? "active" : output ? "idle" : "idle";

          return (
            <AgentCard
              key={agent.key}
              name={agent.name}
              role={agent.role}
              description={agent.description}
              status={status as "active" | "idle" | "error"}
              summary={output?.summary}
              confidence={output?.confidence}
              lastRun={output?.created_at}
            />
          );
        })}
      </div>

      {/* Quantitative Modules */}
      <div>
        <h2 className="text-lg font-semibold text-white mb-4">Quantitative Modules</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {MODULES.map((mod) => {
            const output = moduleOutputs?.[mod.key];
            return (
              <div
                key={mod.key}
                className="bg-surface-elevated border border-[var(--border)] rounded-lg p-3 text-center"
              >
                <div className="text-xl mb-1">{mod.icon}</div>
                <div className="text-xs text-gray-400">{mod.name}</div>
                {output ? (
                  <div className="text-[10px] text-[var(--wolf-emerald)] mt-1">
                    {new Date(output.created_at).toLocaleTimeString()}
                  </div>
                ) : (
                  <div className="text-[10px] text-gray-600 mt-1">No data</div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Latest Analysis */}
      <div className="bg-surface-elevated border border-[var(--border)] rounded-lg p-6">
        <h2 className="text-lg font-semibold text-white mb-3">Latest Analysis</h2>
        {agentsLoading ? (
          <div className="text-center py-8 text-gray-500 text-sm">Loading...</div>
        ) : agentOutputs?.quant ? (
          <div className="space-y-4">
            <div>
              <h3 className="text-sm font-semibold text-[var(--wolf-cyan)] mb-1">The Quant</h3>
              <p className="text-sm text-gray-300">{agentOutputs.quant.summary}</p>
              {agentOutputs.quant.confidence > 0 && (
                <div className="mt-2 flex items-center gap-2">
                  <span className="text-xs text-gray-500">Confidence:</span>
                  <div className="flex-1 max-w-[200px] h-2 bg-[var(--surface)] rounded-full overflow-hidden">
                    <div
                      className="h-full bg-[var(--wolf-emerald)] rounded-full transition-all"
                      style={{ width: `${agentOutputs.quant.confidence * 100}%` }}
                    />
                  </div>
                  <span className="text-xs text-gray-400">
                    {(agentOutputs.quant.confidence * 100).toFixed(0)}%
                  </span>
                </div>
              )}
              {agentOutputs.quant.signals?.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {agentOutputs.quant.signals
                    .filter((s: Record<string, unknown>) => s.type === "trend" || s.type === "risk" || s.indicator)
                    .slice(0, 8)
                    .map((s: Record<string, unknown>, i: number) => (
                      <span
                        key={i}
                        className="px-2 py-1 bg-[var(--surface)] rounded text-[10px] text-gray-400 font-mono"
                      >
                        {s.indicator
                          ? `${s.indicator}: ${typeof s.value === "number" ? (s.value as number).toFixed(2) : s.value}`
                          : s.type === "trend"
                          ? `${s.direction} (${s.strength})`
                          : s.type === "risk"
                          ? `Risk: ${s.level}`
                          : JSON.stringify(s)}
                      </span>
                    ))}
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="text-center py-12 text-gray-500 text-sm">
            No intelligence data yet. Click &quot;Run Intelligence&quot; or start the intel service.
            <br />
            <code className="text-xs text-gray-600 mt-2 block">
              cd intel &amp;&amp; source .venv/bin/activate &amp;&amp; uvicorn wolfpack.api:app --reload
            </code>
          </div>
        )}
      </div>
    </div>
  );
}

function AgentCard({
  name,
  role,
  description,
  status,
  summary,
  confidence,
  lastRun,
}: {
  name: string;
  role: string;
  description: string;
  status: "active" | "idle" | "error";
  summary?: string;
  confidence?: number;
  lastRun?: string;
}) {
  return (
    <div className="bg-surface-elevated border border-[var(--border)] rounded-lg p-5">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="font-semibold text-white">{name}</h3>
          <p className="text-xs text-[var(--wolf-cyan)]">{role}</p>
        </div>
        <span
          className={`px-2 py-0.5 rounded text-[10px] font-semibold uppercase ${
            status === "active"
              ? "bg-[var(--wolf-emerald)]/20 text-[var(--wolf-emerald)]"
              : status === "error"
              ? "bg-[var(--wolf-red)]/20 text-[var(--wolf-red)]"
              : "bg-gray-700 text-gray-400"
          }`}
        >
          {status}
        </span>
      </div>
      {summary ? (
        <div>
          <p className="text-sm text-gray-300 line-clamp-3">{summary}</p>
          {confidence !== undefined && confidence > 0 && (
            <div className="mt-2 text-xs text-gray-500">
              Confidence: {(confidence * 100).toFixed(0)}%
            </div>
          )}
          {lastRun && (
            <div className="mt-1 text-[10px] text-gray-600">
              {new Date(lastRun).toLocaleString()}
            </div>
          )}
        </div>
      ) : (
        <p className="text-sm text-gray-400">{description}</p>
      )}
    </div>
  );
}
