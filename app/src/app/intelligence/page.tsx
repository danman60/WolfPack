"use client";

import { useExchange } from "@/lib/exchange";
import {
  useAgentOutputs,
  useModuleOutputs,
  useRunIntelligence,
  useAgentStatus,
} from "@/lib/hooks/useIntelligence";
import { WolfHead } from "@/components/WolfHead";
import { SentimentGauge } from "@/components/charts/SentimentGauge";
import { PredictionAccuracy } from "@/components/charts/PredictionAccuracy";
import { PredictionOverlay } from "@/components/charts/PredictionOverlay";
import { SignalFeed } from "@/components/charts/SignalFeed";
import { IntelProgress } from "@/components/IntelProgress";

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
  { key: "social_sentiment", name: "Social Sentiment", icon: "\u{1F4E2}" },
  { key: "whale_tracker", name: "Whale Tracker", icon: "\u{1F40B}" },
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

  // Compute sentiment value from Brief agent output
  const briefOutput = agentOutputs?.brief;
  const sentimentValue = (() => {
    if (!briefOutput) return 0;
    const confidence = briefOutput.confidence ?? 0;
    const signals = briefOutput.signals ?? [];
    const rec = signals.find((s: Record<string, unknown>) => s.type === "recommendation" || s.direction);
    const direction = rec?.direction ?? (briefOutput.raw_data as Record<string, unknown>)?.direction ?? "neutral";
    const multiplier = direction === "long" ? 1 : direction === "short" ? -1 : 0;
    return Math.round(confidence * 100 * multiplier);
  })();

  return (
    <div className="space-y-7">
      <div className="page-header flex items-center justify-between">
        <div>
          <h1 className="page-title">Intelligence Brief</h1>
          <p className="page-subtitle">
            Multi-agent AI analysis for {config.name}
          </p>
        </div>
        <button
          onClick={() => runIntel.mutate({ exchange: activeExchange, symbol: "BTC" })}
          disabled={runIntel.isPending}
          className="px-5 py-2.5 bg-[var(--wolf-emerald)] text-black text-[13px] font-semibold rounded-lg hover:brightness-110 transition-all disabled:opacity-50 shadow-lg shadow-[var(--wolf-emerald)]/10"
        >
          {runIntel.isPending ? "Running..." : "Run Intelligence"}
        </button>
      </div>

      {/* Market Intelligence Overview */}
      <div className="wolf-card p-6">
        <div className="flex items-center gap-2 mb-5">
          <div className="w-1 h-4 rounded-full bg-[var(--wolf-amber)]" />
          <h2 className="section-title">Market Intelligence</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-center justify-items-center">
          <SentimentGauge value={sentimentValue} />
          <PredictionAccuracy />
        </div>
      </div>

      {/* Intelligence Progress */}
      <IntelProgress running={runIntel.isPending} />

      {/* Agent Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {AGENTS.map((agent) => {
          const output = agentOutputs?.[agent.key];
          const svc = statusMap.get(agent.key);
          const status = svc?.status === "running" ? "active" : output ? "completed" : "idle";

          return (
            <AgentCard
              key={agent.key}
              agentKey={agent.key}
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

      {/* Prediction vs Reality */}
      <PredictionOverlay />

      {/* Signal Feed */}
      <div className="wolf-card p-5">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-1 h-4 rounded-full bg-[var(--wolf-purple)]" />
          <h2 className="section-title">Snoop Signal Feed</h2>
        </div>
        <SignalFeed />
      </div>

      {/* Quantitative Modules */}
      <div>
        <div className="flex items-center gap-2 mb-4">
          <div className="w-1 h-4 rounded-full bg-[var(--wolf-purple)]" />
          <h2 className="section-title">Quantitative Modules</h2>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {MODULES.map((mod) => {
            const output = moduleOutputs?.[mod.key];
            return (
              <div
                key={mod.key}
                className="wolf-card wolf-card-interactive p-3.5 text-center"
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
      <div className="wolf-card p-6">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-1 h-4 rounded-full bg-[var(--wolf-emerald)]" />
          <h2 className="section-title">Latest Analysis</h2>
        </div>
        {agentsLoading ? (
          <div className="text-center py-8 text-gray-500 text-sm">Loading...</div>
        ) : agentOutputs && Object.keys(agentOutputs).length > 0 ? (
          <div className="space-y-5">
            {AGENTS.map((agent) => {
              const output = agentOutputs[agent.key];
              if (!output) return null;
              const agentColors: Record<string, string> = {
                quant: "var(--wolf-cyan)",
                snoop: "var(--wolf-purple)",
                sage: "var(--wolf-blue)",
                brief: "var(--wolf-amber)",
              };
              const color = agentColors[agent.key] || "var(--wolf-cyan)";
              return (
                <div key={agent.key} className="border-b border-[var(--border)] last:border-0 pb-4 last:pb-0">
                  <h3 className="text-sm font-semibold mb-1" style={{ color }}>{agent.name}</h3>
                  <p className="text-sm text-gray-300">{output.summary}</p>
                  {output.confidence > 0 && (
                    <div className="mt-2 flex items-center gap-2">
                      <span className="text-xs text-gray-500">Confidence:</span>
                      <div className="flex-1 max-w-[200px] h-2 bg-[var(--surface)] rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all"
                          style={{ width: `${output.confidence * 100}%`, backgroundColor: color }}
                        />
                      </div>
                      <span className="text-xs text-gray-400">
                        {(output.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                  )}
                  {output.signals?.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {output.signals
                        .filter((s: Record<string, unknown>) => s.type === "trend" || s.type === "risk" || s.type === "recommendation" || s.type === "outlook" || s.type === "sentiment" || s.indicator)
                        .slice(0, 6)
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
                              : s.type === "recommendation"
                              ? `${s.direction} ${s.symbol} (${s.conviction}%)`
                              : s.type === "outlook"
                              ? `Outlook: ${s.direction}`
                              : s.type === "sentiment"
                              ? `Sentiment: ${s.score}`
                              : JSON.stringify(s)}
                          </span>
                        ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ) : (
          <div className="text-center py-12 text-gray-500 text-sm">
            No intelligence data yet. Click &quot;Run Intelligence&quot; to start.
          </div>
        )}
      </div>
    </div>
  );
}

function AgentCard({
  agentKey,
  name,
  role,
  description,
  status,
  summary,
  confidence,
  lastRun,
}: {
  agentKey: string;
  name: string;
  role: string;
  description: string;
  status: "active" | "completed" | "idle" | "error";
  summary?: string;
  confidence?: number;
  lastRun?: string;
}) {
  return (
    <div className="wolf-card wolf-card-interactive p-5">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <WolfHead agent={agentKey as "quant" | "snoop" | "sage" | "brief"} size={40} />
          <div>
            <h3 className="font-semibold text-white text-[15px] tracking-tight">{name}</h3>
            <p className="text-[11px] text-[var(--wolf-cyan)] font-medium">{role}</p>
          </div>
        </div>
        <span
          className={`px-2 py-0.5 rounded text-[10px] font-semibold uppercase ${
            status === "active"
              ? "bg-[var(--wolf-amber)]/20 text-[var(--wolf-amber)]"
              : status === "completed"
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
