"use client";

import { useExchange } from "@/lib/exchange";

export default function TradingPage() {
  const { config } = useExchange();

  return (
    <div className="space-y-6">
      <div className="border-b border-[var(--border)] pb-4">
        <h1 className="text-2xl font-bold text-white">Trading</h1>
        <p className="text-gray-400 text-sm mt-1">
          Manual & AI-assisted trading on {config.name}
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
        <div className="text-center py-8 text-gray-500 text-sm">
          Intelligence service will surface trade recommendations here.
          <br />
          Each recommendation can be approved or rejected before execution.
        </div>
      </div>
    </div>
  );
}
