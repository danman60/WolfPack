"use client";

import { useExchange } from "@/lib/exchange";
import { useRecommendations } from "@/lib/hooks/useIntelligence";

export default function TradingPage() {
  const { config } = useExchange();
  const { data: recommendations } = useRecommendations("pending");

  return (
    <div className="space-y-6">
      <div className="border-b border-[var(--border)] pb-4">
        <h1 className="text-2xl font-bold text-white">Trading</h1>
        <p className="text-gray-400 text-sm mt-1">
          Manual &amp; AI-assisted trading on {config.name}
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Order Entry */}
        <div className="bg-surface-elevated border border-[var(--border)] rounded-lg p-6">
          <h2 className="text-lg font-semibold text-white mb-4">Place Order</h2>
          <div className="space-y-4">
            <div>
              <label className="text-xs text-gray-500 uppercase">Asset</label>
              <select className="w-full mt-1 bg-[var(--surface)] border border-[var(--border)] rounded-md px-3 py-2 text-white text-sm">
                <option>ETH-USD</option>
                <option>BTC-USD</option>
                <option>SOL-USD</option>
                <option>LINK-USD</option>
              </select>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <button className="bg-[var(--wolf-emerald)] text-white py-2 rounded-md text-sm font-semibold hover:brightness-110 transition">
                Long
              </button>
              <button className="bg-[var(--wolf-red)] text-white py-2 rounded-md text-sm font-semibold hover:brightness-110 transition">
                Short
              </button>
            </div>
            <div>
              <label className="text-xs text-gray-500 uppercase">Size (USD)</label>
              <input
                type="number"
                placeholder="0.00"
                className="w-full mt-1 bg-[var(--surface)] border border-[var(--border)] rounded-md px-3 py-2 text-white text-sm"
              />
            </div>
            <div>
              <label className="text-xs text-gray-500 uppercase">Leverage</label>
              <input
                type="range"
                min="1"
                max="50"
                defaultValue="5"
                className="w-full mt-1"
              />
              <div className="flex justify-between text-xs text-gray-500">
                <span>1x</span>
                <span>50x</span>
              </div>
            </div>
            <button className="w-full bg-[var(--wolf-blue)] text-white py-3 rounded-md font-semibold hover:brightness-110 transition disabled:opacity-50" disabled>
              Connect Wallet to Trade
            </button>
          </div>
        </div>

        {/* Chart Area */}
        <div className="lg:col-span-2 bg-surface-elevated border border-[var(--border)] rounded-lg p-6">
          <h2 className="text-lg font-semibold text-white mb-4">Price Chart</h2>
          <div className="h-80 flex items-center justify-center text-gray-500 text-sm border border-dashed border-[var(--border)] rounded-md">
            Chart component — will integrate TradingView or recharts
          </div>
        </div>
      </div>

      {/* AI Recommendations */}
      <div className="bg-surface-elevated border border-[var(--border)] rounded-lg p-6">
        <h2 className="text-lg font-semibold text-white mb-4">AI Recommendations</h2>
        {recommendations && recommendations.length > 0 ? (
          <div className="space-y-3">
            {recommendations.map((rec: Record<string, unknown>) => (
              <div
                key={rec.id as string}
                className="border border-[var(--border)] rounded-lg p-4 flex items-center justify-between"
              >
                <div className="flex items-center gap-4">
                  <span
                    className={`px-3 py-1 rounded text-xs font-bold uppercase ${
                      rec.direction === "long"
                        ? "bg-[var(--wolf-emerald)]/20 text-[var(--wolf-emerald)]"
                        : "bg-[var(--wolf-red)]/20 text-[var(--wolf-red)]"
                    }`}
                  >
                    {rec.direction as string}
                  </span>
                  <div>
                    <span className="text-white font-mono font-semibold">{rec.symbol as string}</span>
                    <p className="text-xs text-gray-400 mt-0.5 max-w-md line-clamp-1">
                      {rec.rationale as string}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <div className="text-right">
                    <div className="text-xs text-gray-500">Conviction</div>
                    <div className="text-sm font-bold text-white">{rec.conviction as number}%</div>
                  </div>
                  <div className="flex gap-2">
                    <button className="px-3 py-1.5 bg-[var(--wolf-emerald)]/20 text-[var(--wolf-emerald)] rounded text-xs font-semibold hover:bg-[var(--wolf-emerald)]/30 transition">
                      Approve
                    </button>
                    <button className="px-3 py-1.5 bg-[var(--wolf-red)]/20 text-[var(--wolf-red)] rounded text-xs font-semibold hover:bg-[var(--wolf-red)]/30 transition">
                      Reject
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8 text-gray-500 text-sm">
            No pending recommendations. Run intelligence to generate trade signals.
          </div>
        )}
      </div>
    </div>
  );
}
