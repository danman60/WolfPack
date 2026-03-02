"use client";

import { useExchange } from "@/lib/exchange";

export default function IntelligencePage() {
  const { config } = useExchange();

  return (
    <div className="space-y-6">
      <div className="border-b border-[var(--border)] pb-4">
        <h1 className="text-2xl font-bold text-white">Intelligence Brief</h1>
        <p className="text-gray-400 text-sm mt-1">
          Multi-agent AI analysis for {config.name}
        </p>
      </div>

      {/* Agent Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <AgentCard
          name="The Quant"
          role="Technical Analysis"
          description="Regime detection, technical indicators, quantitative signals, chart patterns"
          status="idle"
        />
        <AgentCard
          name="The Snoop"
          role="Social Intelligence"
          description="Social media sentiment, news analysis, narrative tracking, community signals"
          status="idle"
        />
        <AgentCard
          name="The Sage"
          role="Forecasting"
          description="Cross-asset correlation, weekly outlook, macro analysis, trend prediction"
          status="idle"
        />
        <AgentCard
          name="The Brief"
          role="Decision Synthesis"
          description="Aggregates all agents, generates trade recommendations with conviction scores"
          status="idle"
        />
      </div>

      {/* Quantitative Modules */}
      <div>
        <h2 className="text-lg font-semibold text-white mb-4">Quantitative Modules</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { name: "Regime Detection", icon: "📊" },
            { name: "Liquidity Intel", icon: "💧" },
            { name: "Funding & Carry", icon: "💰" },
            { name: "Correlation", icon: "🔗" },
            { name: "Volatility", icon: "📈" },
            { name: "Circuit Breakers", icon: "🛡️" },
            { name: "Execution Timing", icon: "⏱️" },
            { name: "Backtest", icon: "🔬" },
          ].map((mod) => (
            <div
              key={mod.name}
              className="bg-surface-elevated border border-[var(--border)] rounded-lg p-3 text-center"
            >
              <div className="text-xl mb-1">{mod.icon}</div>
              <div className="text-xs text-gray-400">{mod.name}</div>
              <div className="text-[10px] text-gray-600 mt-1">Not connected</div>
            </div>
          ))}
        </div>
      </div>

      {/* Latest Analysis Placeholder */}
      <div className="bg-surface-elevated border border-[var(--border)] rounded-lg p-6">
        <h2 className="text-lg font-semibold text-white mb-3">Latest Analysis</h2>
        <div className="text-center py-12 text-gray-500 text-sm">
          Start the intelligence service to receive analysis.
          <br />
          <code className="text-xs text-gray-600 mt-2 block">
            cd intel && uvicorn wolfpack.api:app --reload
          </code>
        </div>
      </div>
    </div>
  );
}

function AgentCard({
  name,
  role,
  description,
  status,
}: {
  name: string;
  role: string;
  description: string;
  status: "active" | "idle" | "error";
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
      <p className="text-sm text-gray-400">{description}</p>
    </div>
  );
}
