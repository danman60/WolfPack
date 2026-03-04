"use client";

import { useExchange } from "@/lib/exchange";
import { useStrategyMode } from "@/lib/hooks/useIntelligence";

const LLM_PROVIDERS = [
  { name: "Anthropic (Claude)", env: "ANTHROPIC_API_KEY", role: "Primary analysis, The Brief synthesis" },
  { name: "DeepSeek", env: "DEEPSEEK_API_KEY", role: "Quantitative analysis, The Quant" },
  { name: "OpenRouter", env: "OPENROUTER_API_KEY", role: "Fallback routing, multi-model access" },
];

export default function SettingsPage() {
  const { config, availableExchanges } = useExchange();
  const { data: strategyMode } = useStrategyMode();

  const checklist = strategyMode?.checklist ?? [];

  return (
    <div className="space-y-7">
      <div className="page-header">
        <h1 className="page-title">Settings</h1>
        <p className="page-subtitle">
          Platform configuration &mdash; read-only display, configure via .env files
        </p>
      </div>

      {/* Exchange Configuration */}
      <div className="wolf-card p-6">
        <h2 className="section-title mb-4">Exchange Configuration</h2>
        <div className="space-y-3">
          {availableExchanges.map((ex) => (
            <div
              key={ex.id}
              className={`flex items-center justify-between p-4 rounded-lg border ${
                ex.id === config.id
                  ? "border-[var(--wolf-emerald)] bg-[var(--wolf-emerald-glow)]"
                  : "border-[var(--border)] bg-[var(--surface)]"
              }`}
            >
              <div className="flex items-center gap-3">
                <div
                  className={`w-2.5 h-2.5 rounded-full ${
                    ex.id === config.id ? "bg-[var(--wolf-emerald)]" : "bg-gray-600"
                  }`}
                />
                <div>
                  <span className="text-white font-medium">{ex.name}</span>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {ex.id === "hyperliquid"
                      ? "On-chain perpetual futures (L1)"
                      : "Decentralized perpetual exchange (Cosmos)"}
                  </p>
                </div>
              </div>
              {ex.id === config.id && (
                <span className="px-2 py-0.5 rounded text-[10px] font-semibold uppercase bg-[var(--wolf-emerald)]/20 text-[var(--wolf-emerald)]">
                  Active
                </span>
              )}
            </div>
          ))}
          <p className="text-xs text-gray-600 mt-2">
            Switch exchanges using the toggle in the navigation bar.
          </p>
        </div>
      </div>

      {/* Strategy Mode */}
      <div className="wolf-card p-6">
        <h2 className="section-title mb-4">Strategy Mode</h2>
        <div className="flex gap-3">
          <div className="flex-1 p-4 rounded-lg border border-[var(--wolf-emerald)] bg-[var(--wolf-emerald-glow)]">
            <div className="flex items-center gap-2 mb-1">
              <div className="w-2.5 h-2.5 rounded-full bg-[var(--wolf-emerald)]" />
              <span className="text-white font-medium">Paper Trading</span>
            </div>
            <p className="text-xs text-gray-400">
              Simulated execution with virtual portfolio. No real funds at risk.
            </p>
          </div>
          <div className="flex-1 p-4 rounded-lg border border-[var(--border)] bg-[var(--surface)] opacity-50">
            <div className="flex items-center gap-2 mb-1">
              <div className="w-2.5 h-2.5 rounded-full bg-gray-600" />
              <span className="text-gray-400 font-medium">Live Trading</span>
            </div>
            <p className="text-xs text-gray-500">
              Requires all safety checks to pass. Disabled until safety checklist is complete.
            </p>
          </div>
        </div>
        <p className="text-xs text-gray-600 mt-3">
          Set <code className="text-gray-400">TRADING_MODE=live</code> in .env to enable live trading (requires safety checklist).
        </p>
      </div>

      {/* LLM Providers */}
      <div className="wolf-card p-6">
        <h2 className="section-title mb-4">LLM Providers</h2>
        <div className="space-y-3">
          {LLM_PROVIDERS.map((provider) => (
            <div
              key={provider.name}
              className="flex items-center justify-between p-4 rounded-lg border border-[var(--border)] bg-[var(--surface)]"
            >
              <div>
                <span className="text-white font-medium">{provider.name}</span>
                <p className="text-xs text-gray-500 mt-0.5">{provider.role}</p>
              </div>
              <div className="text-right">
                <code className="text-xs text-gray-500 font-mono">{provider.env}</code>
                <p className="text-[10px] text-gray-600 mt-0.5">Configure in .env</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Telegram Notifications */}
      <div className="wolf-card p-6">
        <h2 className="section-title mb-4">Telegram Notifications</h2>
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <SettingRow
              label="Bot Token"
              envVar="TELEGRAM_BOT_TOKEN"
              description="Telegram bot API token for sending alerts"
            />
            <SettingRow
              label="Chat ID"
              envVar="TELEGRAM_CHAT_ID"
              description="Target chat/channel for trade notifications"
            />
          </div>
          <div className="border-t border-[var(--border)] pt-3">
            <p className="text-xs text-gray-500 font-medium mb-2">Notification Events</p>
            <div className="flex flex-wrap gap-2">
              {[
                "Trade Recommendations",
                "Position Opened",
                "Position Closed",
                "Circuit Breaker Triggered",
                "Daily Summary",
              ].map((event) => (
                <span
                  key={event}
                  className="px-2.5 py-1 bg-[var(--surface)] rounded text-xs text-gray-400 border border-[var(--border)]"
                >
                  {event}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Safety Checklist — live from backend */}
      <div className="bg-surface-elevated border border-[var(--border)] rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="section-title">Live Trading Safety Checklist</h2>
          <span className="text-xs text-gray-500">
            {checklist.length > 0
              ? `${checklist.filter((s: { passed: boolean }) => s.passed).length}/${checklist.length} passed`
              : "Loading..."}
          </span>
        </div>
        <div className="space-y-3">
          {checklist.length > 0 ? checklist.map((item: { name: string; passed: boolean; description: string }) => (
            <div
              key={item.name}
              className="flex items-start gap-3 p-3 rounded-lg border border-[var(--border)] bg-[var(--surface)]"
            >
              <div
                className={`mt-0.5 w-5 h-5 rounded flex items-center justify-center flex-shrink-0 ${
                  item.passed
                    ? "bg-[var(--wolf-emerald)]/20 text-[var(--wolf-emerald)]"
                    : "bg-[var(--wolf-red)]/20 text-[var(--wolf-red)]"
                }`}
              >
                <span className="text-xs font-bold">{item.passed ? "\u2713" : "\u2717"}</span>
              </div>
              <div>
                <span className={`text-sm font-medium ${item.passed ? "text-white" : "text-gray-400"}`}>
                  {item.name}
                </span>
                <p className="text-xs text-gray-500 mt-0.5">{item.description}</p>
              </div>
            </div>
          )) : (
            <div className="text-center py-4 text-gray-500 text-sm">
              Start the intel service to load safety checklist
            </div>
          )}
        </div>
        {strategyMode?.can_go_live === false && checklist.length > 0 && (
          <div className="mt-4 p-3 rounded-lg bg-[var(--wolf-amber)]/10 border border-[var(--wolf-amber)]/20">
            <p className="text-xs text-[var(--wolf-amber)]">
              All safety checks must pass before live trading can be enabled.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

function SettingRow({
  label,
  envVar,
  description,
}: {
  label: string;
  envVar: string;
  description: string;
}) {
  return (
    <div className="p-4 rounded-lg border border-[var(--border)] bg-[var(--surface)]">
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm text-white font-medium">{label}</span>
        <code className="text-[10px] text-gray-500 font-mono">{envVar}</code>
      </div>
      <p className="text-xs text-gray-500">{description}</p>
    </div>
  );
}
