"use client";

import { useState, useMemo, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useExchange } from "@/lib/exchange";
import { intelFetch } from "@/lib/intel";
import {
  useRecommendations,
  useApproveRecommendation,
  useRejectRecommendation,
  usePortfolio,
  useWatchlist,
  useAddToWatchlist,
  useRemoveFromWatchlist,
  useSymbolSearch,
  useRunAllIntelligence,
} from "@/lib/hooks/useIntelligence";
import { useCandles, useMarkets, use24hChange } from "@/lib/hooks/useMarketData";
import { TradingChart } from "@/components/TradingChart";

const DEFAULT_SYMBOLS = ["BTC", "ETH", "SOL", "LINK", "DOGE", "ARB"];

export default function TradingPage() {
  const { config, activeExchange } = useExchange();
  const queryClient = useQueryClient();
  const { data: recommendations } = useRecommendations("pending");
  const { data: portfolio } = usePortfolio();
  const approveMutation = useApproveRecommendation();
  const rejectMutation = useRejectRecommendation();

  // Order form state
  const [selectedSymbol, setSelectedSymbol] = useState("BTC");
  const [direction, setDirection] = useState<"long" | "short">("long");
  const [sizeUsd, setSizeUsd] = useState("");
  const [leverage, setLeverage] = useState(5);
  const [stopLoss, setStopLoss] = useState("");
  const [takeProfit, setTakeProfit] = useState("");
  const [orderSubmitting, setOrderSubmitting] = useState(false);
  const [orderResult, setOrderResult] = useState<string | null>(null);

  // Market data
  const [chartInterval, setChartInterval] = useState("1h");
  const [chartLimit, setChartLimit] = useState(168);
  const { data: candles, isLoading: candlesLoading } = useCandles(selectedSymbol, chartInterval, chartLimit);
  const { data: markets } = useMarkets();

  // Watchlist
  const { data: watchlist } = useWatchlist(activeExchange);
  const addWatchlist = useAddToWatchlist();
  const removeWatchlist = useRemoveFromWatchlist();
  const runAllMutation = useRunAllIntelligence();
  const [searchQuery, setSearchQuery] = useState("");
  const { data: searchResults } = useSymbolSearch(searchQuery, activeExchange);
  const [showSearch, setShowSearch] = useState(false);

  const handleAddSymbol = useCallback((sym: string) => {
    addWatchlist.mutate({ symbol: sym, exchangeId: activeExchange });
    setSearchQuery("");
    setShowSearch(false);
  }, [addWatchlist, activeExchange]);

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
  const change24h = use24hChange(selectedSymbol);
  const priceChange = change24h ?? 0;

  // Submit paper order — uses intelFetch for auth, sends leveraged size
  const handleOrder = async () => {
    if (!sizeUsd || !latestPrice) return;
    setOrderSubmitting(true);
    setOrderResult(null);

    const leveragedSize = Number(sizeUsd) * leverage;
    const params = new URLSearchParams({
      symbol: selectedSymbol,
      direction,
      size_usd: String(leveragedSize),
      exchange: activeExchange,
    });
    if (stopLoss) params.set("stop_loss", stopLoss);
    if (takeProfit) params.set("take_profit", takeProfit);

    try {
      const res = await intelFetch(`/intel/paper/order?${params}`, { method: "POST" });
      const result = await res.json();
      if (result.status === "executed") {
        setOrderResult(result.message || `Paper ${direction} ${selectedSymbol} placed`);
        setSizeUsd("");
        setStopLoss("");
        setTakeProfit("");
        queryClient.invalidateQueries({ queryKey: ["portfolio"] });
        queryClient.invalidateQueries({ queryKey: ["portfolio-history"] });
      } else {
        setOrderResult(result.message || "Order failed");
      }
    } catch {
      setOrderResult("Intel service unavailable — start the backend to trade");
    } finally {
      setOrderSubmitting(false);
    }
  };

  return (
    <div className="space-y-7">
      <div className="page-header">
        <h1 className="page-title">Trading</h1>
        <p className="page-subtitle">
          Manual &amp; AI-assisted trading on {config.name}
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Order Entry */}
        <div className="wolf-card p-6">
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

            {/* SL / TP */}
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-xs text-gray-500 uppercase">Stop Loss</label>
                <input
                  type="number"
                  placeholder="Optional"
                  value={stopLoss}
                  onChange={(e) => setStopLoss(e.target.value)}
                  className="w-full mt-1 bg-[var(--surface)] border border-[var(--border)] rounded-md px-3 py-2 text-white text-sm"
                />
              </div>
              <div>
                <label className="text-xs text-gray-500 uppercase">Take Profit</label>
                <input
                  type="number"
                  placeholder="Optional"
                  value={takeProfit}
                  onChange={(e) => setTakeProfit(e.target.value)}
                  className="w-full mt-1 bg-[var(--surface)] border border-[var(--border)] rounded-md px-3 py-2 text-white text-sm"
                />
              </div>
            </div>

            {/* Order size info */}
            {sizeUsd && latestPrice && (
              <div className="text-xs text-gray-500 space-y-1 p-2 bg-[var(--surface)] rounded border border-[var(--border)]">
                <div className="flex justify-between">
                  <span>Margin</span>
                  <span className="text-gray-300">${Number(sizeUsd).toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                  <span>Notional ({leverage}x)</span>
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
          <TradingChart
            symbol={selectedSymbol}
            candles={candles}
            isLoading={candlesLoading}
            onTimeframeChange={(tf, limit) => {
              setChartInterval(tf);
              setChartLimit(limit);
            }}
          />

          {/* Paper Portfolio Summary */}
          {isActive && (
            <div className="wolf-card p-4">
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

      {/* Watchlist */}
      <div className="wolf-card p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <div className="w-1 h-4 rounded-full bg-[var(--wolf-cyan)]" />
            <h2 className="text-lg font-semibold text-white">Watchlist</h2>
            <span className="text-xs text-gray-500 ml-1">{watchlist?.length ?? 0} symbols</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => runAllMutation.mutate({ exchange: activeExchange })}
              disabled={runAllMutation.isPending || !watchlist?.length}
              className="px-3 py-1.5 bg-[var(--wolf-cyan)]/20 text-[var(--wolf-cyan)] rounded text-xs font-semibold hover:bg-[var(--wolf-cyan)]/30 transition disabled:opacity-50"
            >
              {runAllMutation.isPending ? "Running..." : "Run All Intel"}
            </button>
            <button
              onClick={() => setShowSearch(!showSearch)}
              className="px-3 py-1.5 bg-[var(--surface)] border border-[var(--border)] text-gray-300 rounded text-xs font-semibold hover:text-white transition"
            >
              + Add
            </button>
          </div>
        </div>

        {/* Search input */}
        {showSearch && (
          <div className="mb-4 relative">
            <input
              type="text"
              placeholder="Search symbols (BTC, ETH, SOL...)"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-[var(--surface)] border border-[var(--border)] rounded-md px-3 py-2 text-white text-sm focus:border-[var(--wolf-cyan)] focus:outline-none"
              autoFocus
            />
            {searchResults && searchResults.length > 0 && (
              <div className="absolute z-10 mt-1 w-full bg-[var(--surface-elevated)] border border-[var(--border)] rounded-md max-h-48 overflow-y-auto">
                {searchResults.map((r) => (
                  <button
                    key={r.symbol}
                    onClick={() => handleAddSymbol(r.symbol)}
                    className="w-full text-left px-3 py-2 text-sm hover:bg-[var(--surface-hover)] transition flex items-center justify-between"
                  >
                    <span className="text-white font-mono">{r.symbol}-USD</span>
                    <span className="text-xs text-gray-500 font-mono">
                      ${r.last_price.toLocaleString()} | Vol: ${(r.volume_24h / 1e6).toFixed(1)}M
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Watchlist chips */}
        {watchlist && watchlist.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {watchlist.map((item) => (
              <div
                key={item.id}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-[var(--surface)] border border-[var(--border)] rounded-full group hover:border-[var(--wolf-cyan)]/50 transition"
              >
                <button
                  onClick={() => setSelectedSymbol(item.symbol)}
                  className="text-sm font-mono text-gray-300 hover:text-white transition"
                >
                  {item.symbol}
                </button>
                <button
                  onClick={() => removeWatchlist.mutate({ symbol: item.symbol, exchangeId: activeExchange })}
                  className="text-gray-600 hover:text-[var(--wolf-red)] transition text-xs opacity-0 group-hover:opacity-100"
                >
                  x
                </button>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-gray-500">No symbols on watchlist. Add symbols to track and run bulk intelligence.</p>
        )}
      </div>

      {/* AI Recommendations */}
      <div className="wolf-card p-6">
        <div className="flex items-center gap-2 mb-5">
          <div className="w-1 h-4 rounded-full bg-[var(--wolf-amber)]" />
          <h2 className="section-title">AI Recommendations</h2>
        </div>
        {recommendations && recommendations.length > 0 ? (
          <div className="space-y-3">
            {recommendations.map((rec) => (
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
