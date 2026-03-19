"use client";

import { useAgentOutputs } from "@/lib/hooks/useIntelligence";

/**
 * Signal Feed — scrollable list of Snoop agent's intelligence signals.
 */
export function SignalFeed() {
  const { data: agentOutputs } = useAgentOutputs();
  const snoopOutput = agentOutputs?.snoop;

  const signals: Array<{
    source: string;
    headline: string;
    sentiment: string;
    timestamp: string;
  }> = [];

  if (snoopOutput?.raw_data) {
    const rawSignals =
      (snoopOutput.raw_data as Record<string, unknown>).signals ??
      (snoopOutput.raw_data as Record<string, unknown>).news ??
      (snoopOutput.raw_data as Record<string, unknown>).social_signals ??
      [];

    for (const s of rawSignals as Array<Record<string, unknown>>) {
      signals.push({
        source: (s.source ?? s.platform ?? "Unknown") as string,
        headline: (s.headline ?? s.text ?? s.content ?? s.summary ?? "") as string,
        sentiment: (s.sentiment ?? s.score ?? "neutral") as string,
        timestamp: (s.timestamp ?? s.time ?? snoopOutput.created_at ?? "") as string,
      });
    }
  }

  // Also add from signals array
  if (snoopOutput?.signals) {
    for (const s of snoopOutput.signals) {
      if (s.type === "sentiment" || s.source) {
        signals.push({
          source: (s.source ?? s.platform ?? "Snoop") as string,
          headline: (s.headline ?? s.text ?? s.summary ?? JSON.stringify(s)) as string,
          sentiment: (s.sentiment ?? s.score ?? "neutral") as string,
          timestamp: (s.timestamp ?? snoopOutput.created_at ?? "") as string,
        });
      }
    }
  }

  if (signals.length === 0) {
    return (
      <div className="text-center py-4 text-gray-500 text-xs">
        No signals yet. Run intelligence to populate the Snoop feed.
      </div>
    );
  }

  const sentimentColor = (s: string) => {
    const lower = String(s).toLowerCase();
    if (lower === "bullish" || lower === "positive" || Number(s) > 0.3) return "var(--wolf-emerald)";
    if (lower === "bearish" || lower === "negative" || Number(s) < -0.3) return "var(--wolf-red)";
    return "var(--wolf-amber)";
  };

  const sentimentLabel = (s: string) => {
    const lower = String(s).toLowerCase();
    if (lower === "bullish" || lower === "positive" || Number(s) > 0.3) return "Bullish";
    if (lower === "bearish" || lower === "negative" || Number(s) < -0.3) return "Bearish";
    return "Neutral";
  };

  return (
    <div className="max-h-[300px] overflow-y-auto space-y-2 pr-1">
      {signals.slice(0, 20).map((s, i) => (
        <div
          key={i}
          className="flex items-start gap-3 p-2.5 rounded-lg bg-[var(--surface)] hover:bg-[var(--surface-hover)] transition-colors"
        >
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-0.5">
              <span className="text-[10px] text-gray-500 font-mono uppercase">
                {s.source}
              </span>
              {s.timestamp && (
                <span className="text-[10px] text-gray-600">
                  {new Date(s.timestamp).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </span>
              )}
            </div>
            <p className="text-xs text-gray-300 line-clamp-2">{s.headline}</p>
          </div>
          <span
            className="px-1.5 py-0.5 rounded text-[9px] font-semibold whitespace-nowrap"
            style={{
              color: sentimentColor(s.sentiment),
              backgroundColor: `color-mix(in srgb, ${sentimentColor(s.sentiment)} 15%, transparent)`,
            }}
          >
            {sentimentLabel(s.sentiment)}
          </span>
        </div>
      ))}
    </div>
  );
}
