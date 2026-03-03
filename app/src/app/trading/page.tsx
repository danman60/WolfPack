"use client";

import { useState, useMemo } from "react";
import { useExchange } from "@/lib/exchange";
import {
  useRecommendations,
  useApproveRecommendation,
  useRejectRecommendation,
  usePortfolio,
} from "@/lib/hooks/useIntelligence";
import { useCandles, useMarkets, type Candle } from "@/lib/hooks/useMarketData";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Area,
  AreaChart,
} from "recharts";

const DEFAULT_SYMBOLS = ["BTC", "ETH", "SOL", "LINK", "DOGE", "ARB"];

export default function TradingPage() {
  const { config, activeExchange } = useExchange();
  const { data: recommendations } = useRecommendations("pending");
  const { data: portfolio } = usePortfolio();
  const approveMutation = useApproveRecommendation();
  const rejectMutation = useRejectRecommendation();

  // Order form state
  const [selectedSymbol, setSelectedSymbol] = useState("BTC");
  const [direction, setDirection] = useState<"long" | "short">("long");
  const [sizeUsd, setSizeUsd] = useState("");
  const [leverage, setLeverage] = useState(5);
  const [orderSubmitting, setOrderSubmitting] = useState(false);
  const [orderResult, setOrderResult] = useState<string | null>(null);

  // Market data
  const { data: candles, isLoading: candlesLoading } = useCandles(selectedSymbol, "1h", 168);
  const { data: markets } = useMarkets();

  const isActive = portfolio?.status === "active";

  // Available symbols: merge exchange markets + defaults
  const symbolOptions = useMemo(() => {
    if (markets && markets.length > 0) {
      const syms = markets.map((m) => m.symbol).slice(0, 20);
      return [...new Set([...DEFAULT_SYMBOLS, ...syms])];
    }
    return DEFAULT_SYMBOLS;
  }, [markets]);

  // Current price from latest candle
  const latestPrice = candles && candles.length > 0 ? candles[candles.length - 1].close : null;
  const prevPrice = candles && candles.length > 1 ? candles[candles.length - 2].close : null;
  const priceChange = latestPrice && prevPrice ? ((latestPrice - prevPrice) / prevPrice) * 100 : 0;

  // Chart data
  const chartData = useMemo(() => {
    if (!candles) return [];
    return candles.map((c: Candle) => ({
      time: new Date(c.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      price: c.close,
      volume: c.volume,
    }));
  }, [candles]);

  // Submit paper order
  const handleOrder = async () => {
    if (!sizeUsd || !latestPrice) return;
    setOrderSubmitting(true);
    setOrderResult(null);

    try {
      const res = await fetch(
        `/intel/recommendations/paper-order`,
        { method: "POST" }
      );
      // For now, paper orders go through the recommendation flow
      // Create an "instant" paper trade via the approve flow
      if (!res.ok) {
        // Fallback: place via trades/execute endpoint
        const execRes = await fetch(
          `/intel/trades/execute?symbol=${selectedSymbol}&direction=${direction}&size=${sizeUsd}&price=${latestPrice}&order_type=market`,
          { method: "POST" }
        );
        const result = await execRes.json();
        setOrderResult(result.status === "submitted" ? "Order submitted" : result.message || "Paper trade: no live key configured");
      }
    } catch {
      setOrderResult("Intel service unavailable — start the backend to trade");
    } finally {
      setOrderSubmitting(false);
    }
  };

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
              <select
                value={selectedSymbol}
                onChange={(e) => setSelectedSymbol(e.target.value)}
                className="w-full mt-1 bg-[var(--surface)] border border-[var(--border)] rounded-md px-3 py-2 text-white text-sm"
              >
                {symbolOptions.map((s) => (
                  <option key={s} value={s}>
                    {s}-USD
                  </option>
                ))}
              </select>
            </div>

            {/* Live price display */}
            {latestPrice && (
              <div className="flex items-center justify-between p-3 bg-[var(--surface)] rounded-md border border-[var(--border)]">
                <span className="text-sm text-gray-400">Live Price</span>
                <div className="text-right">
                  <span className="text-lg font-bold text-white font-mono">
                    ${latestPrice.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                  </span>
                  <span
                    className={`ml-2 text-xs font-semibold ${
                      priceChange >= 0 ? "text-[var(--wolf-emerald)]" : "text-[var(--wolf-red)]"
                    }`}
                  >
                    {priceChange >= 0 ? "+" : ""}{priceChange.toFixed(2)}%
                  </span>
                </div>
              </div>
            )}

            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => setDirection("long")}
                className={`py-2 rounded-md text-sm font-semibold transition ${
                  direction === "long"
                    ? "bg-[var(--wolf-emerald)] text-white"
                    : "bg-[var(--surface)] text-gray-400 border border-[var(--border)] hover:text-white"
                }`}
              >
                Long
              </button>
              <button
                onClick={() => setDirection("short")}
                className={`py-2 rounded-md text-sm font-semibold transition ${
                  direction === "short"
                    ? "bg-[var(--wolf-red)] text-white"
                    : "bg-[var(--surface)] text-gray-400 border border-[var(--border)] hover:text-white"
                }`}
              >
                Short
              </button>
            </div>
            <div>
              <label className="text-xs text-gray-500 uppercase">Size (USD)</label>
              <input
                type="number"
                placeholder="0.00"
                value={sizeUsd}
                onChange={(e) => setSizeUsd(e.target.value)}
                className="w-full mt-1 bg-[var(--surface)] border border-[var(--border)] rounded-md px-3 py-2 text-white text-sm"
              />
            </div>
            <div>
              <div className="flex items-center justify-between">
                <label className="text-xs text-gray-500 uppercase">Leverage</label>
                <span className="text-sm font-semibold text-white">{leverage}x</span>
              </div>
              <input
                type="range"
                min="1"
                max="50"
                value={leverage}
                onChange={(e) => setLeverage(Number(e.target.value))}
                className="w-full mt-1"
              />
              <div className="flex justify-between text-xs text-gray-500">
                <span>1x</span>
                <span>50x</span>
              </div>
            </div>

            {/* Order size info */}
            {sizeUsd && latestPrice && (
              <div className="text-xs text-gray-500 space-y-1 p-2 bg-[var(--surface)] rounded border border-[var(--border)]">
                <div className="flex justify-between">
                  <span>Notional</span>
                  <span className="text-gray-300">${(Number(sizeUsd) * leverage).toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                  <span>Size ({selectedSymbol})</span>
                  <span className="text-gray-300 font-mono">
                    {((Number(sizeUsd) * leverage) / latestPrice).toFixed(4)}
                  </span>
                </div>
              </div>
            )}

            <button
              onClick={handleOrder}
              disabled={!sizeUsd || !latestPrice || orderSubmitting}
              className={`w-full py-3 rounded-md font-semibold transition disabled:opacity-50 ${
                direction === "long"
                  ? "bg-[var(--wolf-emerald)] text-white hover:brightness-110"
                  : "bg-[var(--wolf-red)] text-white hover:brightness-110"
              }`}
            >
              {orderSubmitting
                ? "Submitting..."
                : `${direction === "long" ? "Long" : "Short"} ${selectedSymbol}`}
            </button>

            {orderResult && (
              <p className="text-xs text-center text-gray-400">{orderResult}</p>
            )}
          </div>
        </div>

        {/* Chart Area + Portfolio Summary */}
        <div className="lg:col-span-2 space-y-6">
          {/* Price Chart */}
          <div className="bg-surface-elevated border border-[var(--border)] rounded-lg p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-white">
                {selectedSymbol}-USD
                {latestPrice && (
                  <span className="ml-3 text-base font-mono text-gray-300">
                    ${latestPrice.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                  </span>
                )}
              </h2>
              <span className="text-xs text-gray-500">1H candles, 7 days</span>
            </div>
            {candlesLoading ? (
              <div className="h-80 flex items-center justify-center text-gray-500 text-sm">
                Loading chart data...
              </div>
            ) : chartData.length > 1 ? (
              <ResponsiveContainer width="100%" height={320}>
                <AreaChart data={chartData}>
                  <defs>
                    <linearGradient id="priceGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="var(--wolf-emerald)" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="var(--wolf-emerald)" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis
                    dataKey="time"
                    tick={{ fill: "#6b7280", fontSize: 10 }}
                    tickLine={false}
                    interval="preserveStartEnd"
                  />
                  <YAxis
                    tick={{ fill: "#6b7280", fontSize: 10 }}
                    tickLine={false}
                    domain={["auto", "auto"]}
                    tickFormatter={(v: number) => `$${v.toLocaleString()}`}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "var(--surface-elevated)",
                      border: "1px solid var(--border)",
                      borderRadius: "0.5rem",
                      color: "white",
                      fontSize: "12px",
                    }}
                    formatter={(val: number | undefined) => [`$${(val ?? 0).toLocaleString()}`, "Price"]}
                  />
                  <Area
                    type="monotone"
                    dataKey="price"
                    stroke="var(--wolf-emerald)"
                    strokeWidth={2}
                    fill="url(#priceGrad)"
                    dot={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-80 flex items-center justify-center text-gray-500 text-sm border border-dashed border-[var(--border)] rounded-md">
                No chart data — start the intel service to fetch market data
                <br />
                <code className="text-xs text-gray-600 mt-2 block">
                  cd intel &amp;&amp; source .venv/bin/activate &amp;&amp; uvicorn wolfpack.api:app --reload
                </code>
              </div>
            )}
          </div>

          {/* Paper Portfolio Summary */}
          {isActive && (
            <div className="bg-surface-elevated border border-[var(--border)] rounded-lg p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-2 h-2 bg-[var(--wolf-emerald)] rounded-full" />
                  <span className="text-sm text-gray-400">
                    Paper Portfolio: <span className="text-white font-semibold">${portfolio.equity.toLocaleString()}</span>
                  </span>
                </div>
                <div className="flex items-center gap-4 text-xs">
                  <span className={portfolio.unrealized_pnl >= 0 ? "text-[var(--wolf-emerald)]" : "text-[var(--wolf-red)]"}>
                    Unrealized: {portfolio.unrealized_pnl >= 0 ? "+" : ""}${portfolio.unrealized_pnl.toFixed(2)}
                  </span>
                  <span className={portfolio.realized_pnl >= 0 ? "text-[var(--wolf-emerald)]" : "text-[var(--wolf-red)]"}>
                    Realized: {portfolio.realized_pnl >= 0 ? "+" : ""}${portfolio.realized_pnl.toFixed(2)}
                  </span>
                  <span className="text-gray-500">
                    {portfolio.positions?.length ?? 0} positions
                  </span>
                </div>
              </div>
            </div>
          )}
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
                    {Boolean(rec.entry_price || rec.stop_loss || rec.take_profit) && (
                      <p className="text-xs text-gray-500 mt-0.5 font-mono">
                        {rec.entry_price ? `Entry: $${Number(rec.entry_price).toLocaleString()}` : ""}
                        {rec.stop_loss ? ` | SL: $${Number(rec.stop_loss).toLocaleString()}` : ""}
                        {rec.take_profit ? ` | TP: $${Number(rec.take_profit).toLocaleString()}` : ""}
                      </p>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <div className="text-right">
                    <div className="text-xs text-gray-500">Conviction</div>
                    <div className="text-sm font-bold text-white">{rec.conviction as number}%</div>
                  </div>
                  {Boolean(rec.size_pct) && (
                    <div className="text-right">
                      <div className="text-xs text-gray-500">Size</div>
                      <div className="text-sm text-gray-300">{rec.size_pct as number}%</div>
                    </div>
                  )}
                  <div className="flex gap-2">
                    <button
                      onClick={() =>
                        approveMutation.mutate({
                          id: rec.id as string,
                          exchange: config.id,
                        })
                      }
                      disabled={approveMutation.isPending}
                      className="px-3 py-1.5 bg-[var(--wolf-emerald)]/20 text-[var(--wolf-emerald)] rounded text-xs font-semibold hover:bg-[var(--wolf-emerald)]/30 transition disabled:opacity-50"
                    >
                      {approveMutation.isPending ? "..." : "Approve"}
                    </button>
                    <button
                      onClick={() => rejectMutation.mutate(rec.id as string)}
                      disabled={rejectMutation.isPending}
                      className="px-3 py-1.5 bg-[var(--wolf-red)]/20 text-[var(--wolf-red)] rounded text-xs font-semibold hover:bg-[var(--wolf-red)]/30 transition disabled:opacity-50"
                    >
                      {rejectMutation.isPending ? "..." : "Reject"}
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
