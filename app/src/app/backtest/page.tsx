"use client";

import { useState, useMemo, useCallback } from "react";
import { useExchange } from "@/lib/exchange";
import {
  useStrategies,
  useBacktestRuns,
  useBacktestResult,
  useBacktestStatus,
  useStartBacktest,
  useDeleteBacktest,
  type BacktestRun,
  type BacktestTrade,
} from "@/lib/hooks/useBacktest";
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  ReferenceLine,
} from "recharts";

const INTERVALS = ["1m", "5m", "15m", "1h", "4h", "1d"];
const DEFAULT_SYMBOLS = ["BTC", "ETH", "SOL", "DOGE", "ARB", "OP"];
const DAYS_PRESETS = [7, 14, 30, 60, 90, 180];

export default function BacktestPage() {
  const { config } = useExchange();
  const { data: strategiesData } = useStrategies();
  const { data: runsData } = useBacktestRuns();
  const startMutation = useStartBacktest();
  const deleteMutation = useDeleteBacktest();

  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const { data: resultData } = useBacktestResult(selectedRunId);

  const runningId =
    selectedRunId &&
    runsData?.runs?.find((r: BacktestRun) => r.id === selectedRunId)?.status ===
      "running"
      ? selectedRunId
      : null;
  const { data: statusData } = useBacktestStatus(runningId);

  // Config form state
  const [symbol, setSymbol] = useState("BTC");
  const [interval, setInterval] = useState("1h");
  const [strategy, setStrategy] = useState("regime_momentum");
  const [startingEquity, setStartingEquity] = useState(10000);
  const [commissionBps, setCommissionBps] = useState(5);
  const [slippageBps, setSlippageBps] = useState(5);
  const [stopLossPct, setStopLossPct] = useState<string>("");
  const [takeProfitPct, setTakeProfitPct] = useState<string>("");
  const [daysBack, setDaysBack] = useState(30);
  const [strategyParams, setStrategyParams] = useState<
    Record<string, number>
  >({});

  // Tab state for results
  const [resultTab, setResultTab] = useState<
    "overview" | "trades" | "monthly"
  >("overview");

  const strategies = strategiesData?.strategies ?? [];
  const runs = runsData?.runs ?? [];
  const selectedRun = resultData?.run;
  const trades: BacktestTrade[] = resultData?.trades ?? [];
  const metrics = selectedRun?.metrics;
  const equityCurve = selectedRun?.equity_curve ?? [];
  const monthlyReturns = selectedRun?.monthly_returns ?? [];
  const currentStrategy = strategies.find((s) => s.key === strategy);

  const handleRun = useCallback(() => {
    const now = Date.now();
    const startTime = now - daysBack * 86_400_000;
    startMutation.mutate(
      {
        symbol,
        exchange: config.id,
        interval,
        start_time: startTime,
        end_time: now,
        starting_equity: startingEquity,
        commission_bps: commissionBps,
        slippage_bps: slippageBps,
        strategy,
        strategy_params: strategyParams,
        max_position_pct: 25,
        stop_loss_pct: stopLossPct ? parseFloat(stopLossPct) : null,
        take_profit_pct: takeProfitPct ? parseFloat(takeProfitPct) : null,
      },
      {
        onSuccess: (data) => {
          if (data?.run_id) setSelectedRunId(data.run_id);
        },
      }
    );
  }, [
    symbol,
    config.id,
    interval,
    daysBack,
    startingEquity,
    commissionBps,
    slippageBps,
    strategy,
    strategyParams,
    stopLossPct,
    takeProfitPct,
    startMutation,
  ]);

  // Chart data
  const equityChartData = useMemo(() => {
    if (!equityCurve.length) return [];
    // Downsample if too many points
    const step = equityCurve.length > 500 ? Math.floor(equityCurve.length / 500) : 1;
    return equityCurve
      .filter((_: unknown, i: number) => i % step === 0)
      .map((p: { time: number; equity: number; drawdown_pct: number }) => ({
        time: new Date(p.time).toLocaleDateString([], {
          month: "short",
          day: "numeric",
        }),
        equity: p.equity,
        drawdown: -p.drawdown_pct,
      }));
  }, [equityCurve]);

  const isRunning = statusData?.status === "running";
  const hasResults = !!metrics;
  const totalWins = trades.filter((t) => t.pnl_usd > 0).length;
  const totalLosses = trades.filter((t) => t.pnl_usd <= 0).length;

  return (
    <div className="space-y-5 md:space-y-7">
      {/* Header */}
      <div className="page-header animate-in animate-in-1">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h1 className="page-title">Backtest</h1>
            <p className="page-subtitle">
              Strategy simulation engine &mdash; {config.name}
            </p>
          </div>
          {hasResults && (
            <div className="hidden md:flex items-center gap-3">
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[var(--surface)]  border border-[var(--border)]">
                <div
                  className={`w-1.5 h-1.5 rounded-full ${metrics.total_return_pct >= 0 ? "bg-[var(--wolf-emerald)]" : "bg-[var(--wolf-red)]"}`}
                  style={{
                    boxShadow: `0 0 6px ${metrics.total_return_pct >= 0 ? "var(--wolf-emerald)" : "var(--wolf-red)"}`,
                  }}
                />
                <span className="text-[11px] text-gray-400 font-mono">
                  Last run:{" "}
                  <span
                    className={
                      metrics.total_return_pct >= 0
                        ? "text-[var(--wolf-emerald)]"
                        : "text-[var(--wolf-red)]"
                    }
                  >
                    {metrics.total_return_pct >= 0 ? "+" : ""}
                    {metrics.total_return_pct.toFixed(2)}%
                  </span>
                </span>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 md:gap-6">
        {/* ═══ CONFIG PANEL ═══ */}
        <div className="lg:col-span-4 xl:col-span-3 space-y-4 md:space-y-5">
          {/* Symbol + Interval Selector */}
          <div className="wolf-card p-4 md:p-5 animate-in animate-in-2">
            <SectionHeader color="blue" title="Market" />

            {/* Symbol Pills */}
            <div className="mt-4">
              <label className="text-[10px] text-gray-600 uppercase tracking-wider font-semibold">
                Asset
              </label>
              <div className="flex flex-wrap gap-1.5 mt-2">
                {DEFAULT_SYMBOLS.map((s) => (
                  <button
                    key={s}
                    onClick={() => setSymbol(s)}
                    className={`px-3 py-1.5 rounded-md text-xs font-mono font-semibold transition-all ${
                      symbol === s
                        ? "bg-[var(--wolf-blue)]/20 text-[var(--wolf-blue)] border border-[var(--wolf-blue)]/30 shadow-[0_0_12px_-4px_rgba(96,165,250,0.3)]"
                        : "bg-[var(--surface)] text-gray-500 border border-[var(--border)] hover:text-gray-300 hover:border-[var(--border-strong)]"
                    }`}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>

            {/* Interval Pills */}
            <div className="mt-4">
              <label className="text-[10px] text-gray-600 uppercase tracking-wider font-semibold">
                Interval
              </label>
              <div className="flex gap-1 mt-2">
                {INTERVALS.map((i) => (
                  <button
                    key={i}
                    onClick={() => setInterval(i)}
                    className={`flex-1 py-1.5 rounded-md text-[11px] font-mono font-semibold transition-all ${
                      interval === i
                        ? "bg-[var(--wolf-blue)]/20 text-[var(--wolf-blue)] border border-[var(--wolf-blue)]/30"
                        : "bg-[var(--surface)] text-gray-600 border border-transparent hover:text-gray-400"
                    }`}
                  >
                    {i}
                  </button>
                ))}
              </div>
            </div>

            {/* Lookback Period */}
            <div className="mt-4">
              <label className="text-[10px] text-gray-600 uppercase tracking-wider font-semibold">
                Lookback
              </label>
              <div className="flex flex-wrap gap-1.5 mt-2">
                {DAYS_PRESETS.map((d) => (
                  <button
                    key={d}
                    onClick={() => setDaysBack(d)}
                    className={`px-2.5 py-1.5 rounded-md text-[11px] font-mono transition-all ${
                      daysBack === d
                        ? "bg-[var(--wolf-blue)]/20 text-[var(--wolf-blue)] border border-[var(--wolf-blue)]/30"
                        : "bg-[var(--surface)] text-gray-600 border border-transparent hover:text-gray-400"
                    }`}
                  >
                    {d}d
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Strategy Config */}
          <div className="wolf-card p-4 md:p-5 animate-in animate-in-3">
            <SectionHeader color="purple" title="Strategy" />

            <div className="mt-4 space-y-3">
              {strategies.map((s) => (
                <button
                  key={s.key}
                  onClick={() => {
                    setStrategy(s.key);
                    setStrategyParams({});
                  }}
                  className={`w-full text-left p-3 rounded-lg transition-all ${
                    strategy === s.key
                      ? "bg-[var(--wolf-purple)]/10 border border-[var(--wolf-purple)]/25 shadow-[0_0_16px_-4px_rgba(167,139,250,0.2)]"
                      : "bg-[var(--surface)] border border-[var(--border)] hover:border-[var(--border-strong)]"
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <div
                      className={`w-1.5 h-1.5 rounded-full transition-all ${
                        strategy === s.key
                          ? "bg-[var(--wolf-purple)]"
                          : "bg-gray-700"
                      }`}
                      style={
                        strategy === s.key
                          ? {
                              boxShadow: "0 0 6px var(--wolf-purple)",
                            }
                          : undefined
                      }
                    />
                    <span
                      className={`text-[13px] font-medium ${strategy === s.key ? "text-white" : "text-gray-400"}`}
                    >
                      {s.name.replace(/_/g, " ")}
                    </span>
                  </div>
                  <p className="text-[10px] text-gray-600 mt-1 ml-4 leading-relaxed">
                    {s.description}
                  </p>
                </button>
              ))}

              {/* Dynamic strategy params */}
              {currentStrategy &&
                Object.keys(currentStrategy.parameters).length > 0 && (
                  <div className="pt-3 mt-1 border-t border-[var(--border)] space-y-3">
                    {Object.entries(currentStrategy.parameters).map(
                      ([key, param]) => (
                        <div key={key}>
                          <div className="flex items-center justify-between">
                            <label className="text-[10px] text-gray-600 uppercase tracking-wider font-semibold">
                              {key.replace(/_/g, " ")}
                            </label>
                            <span className="text-[11px] text-gray-400 font-mono">
                              {strategyParams[key] ?? param.default}
                            </span>
                          </div>
                          <input
                            type="range"
                            value={strategyParams[key] ?? param.default}
                            onChange={(e) =>
                              setStrategyParams((p) => ({
                                ...p,
                                [key]: parseFloat(e.target.value),
                              }))
                            }
                            min={param.min}
                            max={param.max}
                            step={param.type === "int" ? 1 : 0.1}
                            className="w-full mt-1.5"
                          />
                          <p className="text-[9px] text-gray-700 mt-0.5">
                            {param.desc}
                          </p>
                        </div>
                      )
                    )}
                  </div>
                )}
            </div>
          </div>

          {/* Execution Params */}
          <div className="wolf-card p-4 md:p-5 animate-in animate-in-4">
            <SectionHeader color="amber" title="Execution" />

            <div className="mt-4 space-y-3">
              <div>
                <label className="text-[10px] text-gray-600 uppercase tracking-wider font-semibold">
                  Starting equity
                </label>
                <div className="relative mt-1.5">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-600 text-sm">
                    $
                  </span>
                  <input
                    type="number"
                    value={startingEquity}
                    onChange={(e) =>
                      setStartingEquity(parseInt(e.target.value) || 10000)
                    }
                    min={100}
                    className="w-full bg-[var(--surface)] border border-[var(--border)] rounded-md pl-7 pr-3 py-2 text-white text-sm font-mono"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] text-gray-600 uppercase tracking-wider font-semibold">
                    Fees (bps)
                  </label>
                  <input
                    type="number"
                    value={commissionBps}
                    onChange={(e) =>
                      setCommissionBps(parseFloat(e.target.value) || 0)
                    }
                    min={0}
                    className="w-full mt-1.5 bg-[var(--surface)] border border-[var(--border)] rounded-md px-3 py-2 text-white text-sm font-mono"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-gray-600 uppercase tracking-wider font-semibold">
                    Slippage (bps)
                  </label>
                  <input
                    type="number"
                    value={slippageBps}
                    onChange={(e) =>
                      setSlippageBps(parseFloat(e.target.value) || 0)
                    }
                    min={0}
                    className="w-full mt-1.5 bg-[var(--surface)] border border-[var(--border)] rounded-md px-3 py-2 text-white text-sm font-mono"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] text-gray-600 uppercase tracking-wider font-semibold">
                    Stop Loss %
                  </label>
                  <input
                    type="number"
                    value={stopLossPct}
                    onChange={(e) => setStopLossPct(e.target.value)}
                    placeholder="&mdash;"
                    min={0.1}
                    step={0.5}
                    className="w-full mt-1.5 bg-[var(--surface)] border border-[var(--border)] rounded-md px-3 py-2 text-white text-sm font-mono"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-gray-600 uppercase tracking-wider font-semibold">
                    Take Profit %
                  </label>
                  <input
                    type="number"
                    value={takeProfitPct}
                    onChange={(e) => setTakeProfitPct(e.target.value)}
                    placeholder="&mdash;"
                    min={0.1}
                    step={0.5}
                    className="w-full mt-1.5 bg-[var(--surface)] border border-[var(--border)] rounded-md px-3 py-2 text-white text-sm font-mono"
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Run Button */}
          <button
            onClick={handleRun}
            disabled={startMutation.isPending || isRunning}
            className="animate-in animate-in-5 group relative w-full py-3.5 rounded-xl text-sm font-semibold transition-all disabled:opacity-40 bg-gradient-to-r from-[var(--wolf-emerald)]/20 via-[var(--wolf-emerald)]/15 to-[var(--wolf-blue)]/20 text-[var(--wolf-emerald)] border border-[var(--wolf-emerald)]/25 hover:border-[var(--wolf-emerald)]/50 hover:shadow-[0_0_32px_-8px_rgba(52,211,153,0.3)] active:scale-[0.98]"
          >
            <span className="relative z-10 flex items-center justify-center gap-2">
              {isRunning ? (
                <>
                  <span className="w-3 h-3 border-2 border-[var(--wolf-emerald)]/30 border-t-[var(--wolf-emerald)] rounded-full animate-spin" />
                  Running&hellip;{" "}
                  {statusData?.progress_pct
                    ? `${statusData.progress_pct.toFixed(0)}%`
                    : ""}
                </>
              ) : startMutation.isPending ? (
                "Starting&hellip;"
              ) : (
                <>
                  <svg
                    width="14"
                    height="14"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <polygon points="5 3 19 12 5 21 5 3" />
                  </svg>
                  Run Backtest
                </>
              )}
            </span>
          </button>

          {/* Progress Bar */}
          {isRunning && (
            <div className="animate-in">
              <div className="h-1 bg-[var(--surface)] rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-500 ease-out"
                  style={{
                    width: `${statusData?.progress_pct ?? 0}%`,
                    background:
                      "linear-gradient(90deg, var(--wolf-emerald), var(--wolf-blue))",
                    boxShadow:
                      "0 0 8px rgba(52, 211, 153, 0.4), 0 0 16px rgba(52, 211, 153, 0.2)",
                  }}
                />
              </div>
            </div>
          )}
        </div>

        {/* ═══ RESULTS PANEL ═══ */}
        <div className="lg:col-span-8 xl:col-span-9 space-y-5">
          {/* Hero Metrics */}
          {hasResults && (
            <div className="animate-in animate-in-2">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="md:col-span-2">
                  <div
                    className={`wolf-card stat-card ${metrics.total_return_pct >= 0 ? "stat-card-emerald" : "stat-card-red"} p-5`}
                  >
                    <p className="text-[10px] text-gray-500 uppercase tracking-wider font-semibold">
                      Total Return
                    </p>
                    <div className="flex items-baseline gap-3 mt-2">
                      <p
                        className={`text-3xl font-bold tracking-tight font-mono ${
                          metrics.total_return_pct >= 0
                            ? "text-[var(--wolf-emerald)]"
                            : "text-[var(--wolf-red)]"
                        }`}
                      >
                        {metrics.total_return_pct >= 0 ? "+" : ""}
                        {metrics.total_return_pct.toFixed(2)}%
                      </p>
                      <div className="flex items-center gap-2 text-[11px] text-gray-500">
                        <span>
                          {totalWins}W / {totalLosses}L
                        </span>
                        <span className="text-gray-700">&middot;</span>
                        <span>{metrics.total_trades} trades</span>
                      </div>
                    </div>
                  </div>
                </div>
                <MetricCard
                  label="Sharpe"
                  value={metrics.sharpe_ratio.toFixed(2)}
                  color={metrics.sharpe_ratio >= 1 ? "emerald" : metrics.sharpe_ratio >= 0 ? "blue" : "red"}
                />
                <MetricCard
                  label="Max Drawdown"
                  value={`-${metrics.max_drawdown_pct.toFixed(2)}%`}
                  color="red"
                />
              </div>

              <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mt-3">
                <MetricCard
                  label="Win Rate"
                  value={`${(metrics.win_rate * 100).toFixed(1)}%`}
                  color="emerald"
                />
                <MetricCard
                  label="Profit Factor"
                  value={metrics.profit_factor.toFixed(2)}
                  color="purple"
                />
                <MetricCard
                  label="Sortino"
                  value={metrics.sortino_ratio.toFixed(2)}
                  color="blue"
                />
                <MetricCard
                  label="Calmar"
                  value={metrics.calmar_ratio.toFixed(2)}
                  color="purple"
                />
                <MetricCard
                  label="Expectancy"
                  value={`${metrics.expectancy_pct >= 0 ? "+" : ""}${metrics.expectancy_pct.toFixed(2)}%`}
                  color={metrics.expectancy_pct >= 0 ? "emerald" : "red"}
                />
              </div>
            </div>
          )}

          {/* Equity Curve */}
          {equityChartData.length > 1 && (
            <div className="wolf-card p-4 md:p-6 animate-in animate-in-3">
              <div className="flex items-center justify-between mb-5">
                <SectionHeader color="emerald" title="Equity Curve" />
                <span className="text-[11px] text-gray-600 font-mono">
                  ${equityChartData[equityChartData.length - 1]?.equity?.toLocaleString()}
                </span>
              </div>
              <ResponsiveContainer width="100%" height={300}>
                <AreaChart data={equityChartData}>
                  <defs>
                    <linearGradient
                      id="equityGrad"
                      x1="0"
                      y1="0"
                      x2="0"
                      y2="1"
                    >
                      <stop
                        offset="5%"
                        stopColor="var(--wolf-emerald)"
                        stopOpacity={0.25}
                      />
                      <stop
                        offset="95%"
                        stopColor="var(--wolf-emerald)"
                        stopOpacity={0}
                      />
                    </linearGradient>
                  </defs>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="rgba(255,255,255,0.04)"
                  />
                  <XAxis
                    dataKey="time"
                    tick={{ fill: "#4b5563", fontSize: 10 }}
                    tickLine={false}
                    axisLine={{ stroke: "rgba(255,255,255,0.06)" }}
                    interval="preserveStartEnd"
                  />
                  <YAxis
                    tick={{ fill: "#4b5563", fontSize: 10 }}
                    tickLine={false}
                    axisLine={false}
                    domain={["auto", "auto"]}
                    tickFormatter={(v: number) =>
                      `$${(v / 1000).toFixed(1)}k`
                    }
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#111a2e",
                      border: "1px solid rgba(255,255,255,0.08)",
                      borderRadius: "8px",
                      color: "white",
                      fontSize: "12px",
                      boxShadow: "0 8px 32px rgba(0,0,0,0.5)",
                    }}
                    formatter={(val: number | string | undefined) => [
                      `$${Number(val ?? 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}`,
                      "Equity",
                    ]}
                  />
                  <ReferenceLine
                    y={startingEquity}
                    stroke="rgba(255,255,255,0.08)"
                    strokeDasharray="4 4"
                  />
                  <Area
                    type="monotone"
                    dataKey="equity"
                    stroke="var(--wolf-emerald)"
                    strokeWidth={2}
                    fill="url(#equityGrad)"
                    dot={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Drawdown Chart */}
          {equityChartData.length > 1 && (
            <div className="wolf-card p-4 md:p-6 animate-in animate-in-4">
              <div className="flex items-center justify-between mb-5">
                <SectionHeader color="red" title="Drawdown" />
                {metrics && (
                  <span className="text-[11px] text-[var(--wolf-red)]/70 font-mono">
                    max: -{metrics.max_drawdown_pct.toFixed(2)}%
                  </span>
                )}
              </div>
              <ResponsiveContainer width="100%" height={160}>
                <AreaChart data={equityChartData}>
                  <defs>
                    <linearGradient
                      id="ddGrad"
                      x1="0"
                      y1="0"
                      x2="0"
                      y2="1"
                    >
                      <stop
                        offset="5%"
                        stopColor="#f87171"
                        stopOpacity={0.2}
                      />
                      <stop
                        offset="95%"
                        stopColor="#f87171"
                        stopOpacity={0}
                      />
                    </linearGradient>
                  </defs>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="rgba(255,255,255,0.04)"
                  />
                  <XAxis
                    dataKey="time"
                    tick={{ fill: "#4b5563", fontSize: 10 }}
                    tickLine={false}
                    axisLine={{ stroke: "rgba(255,255,255,0.06)" }}
                    interval="preserveStartEnd"
                  />
                  <YAxis
                    tick={{ fill: "#4b5563", fontSize: 10 }}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(v: number) => `${v.toFixed(1)}%`}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#111a2e",
                      border: "1px solid rgba(255,255,255,0.08)",
                      borderRadius: "8px",
                      color: "white",
                      fontSize: "12px",
                      boxShadow: "0 8px 32px rgba(0,0,0,0.5)",
                    }}
                    formatter={(v: number | string | undefined) => [
                      `${Number(v ?? 0).toFixed(2)}%`,
                      "Drawdown",
                    ]}
                  />
                  <Area
                    type="monotone"
                    dataKey="drawdown"
                    stroke="#f87171"
                    fill="url(#ddGrad)"
                    strokeWidth={1.5}
                    dot={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Result Tabs: Trades / Monthly */}
          {hasResults && (
            <div className="animate-in animate-in-5">
              {/* Tab Bar */}
              <div className="flex items-center gap-1 mb-4">
                {(
                  [
                    ["overview", "Overview"],
                    ["trades", `Trades (${trades.length})`],
                    ["monthly", "Monthly"],
                  ] as const
                ).map(([key, label]) => (
                  <button
                    key={key}
                    onClick={() => setResultTab(key)}
                    className={`px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
                      resultTab === key
                        ? "bg-[var(--surface-elevated)] text-white border border-[var(--border-strong)]"
                        : "text-gray-600 hover:text-gray-400"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>

              {/* Overview Tab */}
              {resultTab === "overview" && metrics && (
                <div className="wolf-card p-4 md:p-5">
                  <div className="grid grid-cols-2 gap-x-8 gap-y-3">
                    <DetailRow label="Avg Win" value={`+${metrics.avg_winning_pct.toFixed(2)}%`} color="emerald" />
                    <DetailRow label="Avg Loss" value={`${metrics.avg_losing_pct.toFixed(2)}%`} color="red" />
                    <DetailRow label="Avg Holding" value={`${metrics.avg_holding_bars.toFixed(0)} bars`} />
                    <DetailRow label="DD Duration" value={`${metrics.max_drawdown_duration_bars} bars`} />
                    <DetailRow label="Max Consec Wins" value={metrics.max_consecutive_wins.toString()} color="emerald" />
                    <DetailRow label="Max Consec Losses" value={metrics.max_consecutive_losses.toString()} color="red" />
                    <DetailRow label="Avg Trade" value={`${metrics.avg_trade_pnl_pct >= 0 ? "+" : ""}${metrics.avg_trade_pnl_pct.toFixed(2)}%`} color={metrics.avg_trade_pnl_pct >= 0 ? "emerald" : "red"} />
                    <DetailRow label="Expectancy" value={`${metrics.expectancy_pct >= 0 ? "+" : ""}${metrics.expectancy_pct.toFixed(2)}%`} color={metrics.expectancy_pct >= 0 ? "emerald" : "red"} />
                  </div>
                </div>
              )}

              {/* Trades Tab */}
              {resultTab === "trades" && trades.length > 0 && (
                <div className="wolf-card overflow-hidden">
                  <div className="overflow-x-auto">
                    {/* Header */}
                    <div className="grid grid-cols-[60px_1fr_1fr_80px_90px_70px_60px_90px] gap-2 text-[10px] text-gray-600 uppercase tracking-wider px-5 py-3 border-b border-[var(--border)] bg-[var(--surface)]/50">
                      <span>Side</span>
                      <span>Entry</span>
                      <span>Exit</span>
                      <span>Size</span>
                      <span>P&L</span>
                      <span>Return</span>
                      <span>Bars</span>
                      <span>Exit Reason</span>
                    </div>
                    <div className="max-h-[400px] overflow-y-auto">
                      {trades.slice(0, 200).map((t, i) => (
                        <div
                          key={i}
                          className="grid grid-cols-[60px_1fr_1fr_80px_90px_70px_60px_90px] gap-2 items-center text-xs px-5 py-2.5 border-b border-[var(--border)]/50 hover:bg-[var(--surface-hover)]/30 transition-colors"
                        >
                          <span>
                            <span
                              className={`badge ${
                                t.direction === "long"
                                  ? "bg-[var(--wolf-emerald)]/15 text-[var(--wolf-emerald)]"
                                  : "bg-[var(--wolf-red)]/15 text-[var(--wolf-red)]"
                              }`}
                            >
                              {t.direction}
                            </span>
                          </span>
                          <span className="font-mono text-gray-400">
                            ${t.entry_price.toLocaleString()}
                          </span>
                          <span className="font-mono text-gray-400">
                            ${t.exit_price.toLocaleString()}
                          </span>
                          <span className="font-mono text-gray-500">
                            ${t.size_usd.toFixed(0)}
                          </span>
                          <span
                            className={`font-mono font-semibold ${
                              t.pnl_usd >= 0
                                ? "text-[var(--wolf-emerald)]"
                                : "text-[var(--wolf-red)]"
                            }`}
                          >
                            {t.pnl_usd >= 0 ? "+" : ""}$
                            {t.pnl_usd.toFixed(2)}
                          </span>
                          <span
                            className={`font-mono ${
                              t.pnl_pct >= 0
                                ? "text-[var(--wolf-emerald)]/80"
                                : "text-[var(--wolf-red)]/80"
                            }`}
                          >
                            {t.pnl_pct >= 0 ? "+" : ""}
                            {t.pnl_pct.toFixed(2)}%
                          </span>
                          <span className="font-mono text-gray-600">
                            {t.holding_bars}
                          </span>
                          <span className="text-gray-600 text-[10px] uppercase tracking-wide">
                            {t.exit_reason.replace(/_/g, " ")}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* Monthly Tab */}
              {resultTab === "monthly" && monthlyReturns.length > 0 && (
                <div className="wolf-card p-4 md:p-5">
                  <div className="grid grid-cols-4 md:grid-cols-6 gap-2">
                    {monthlyReturns.map(
                      (m: { month: string; return_pct: number }) => {
                        const intensity = Math.min(
                          Math.abs(m.return_pct) / 10,
                          1
                        );
                        const bg =
                          m.return_pct >= 0
                            ? `rgba(52, 211, 153, ${0.05 + intensity * 0.2})`
                            : `rgba(248, 113, 113, ${0.05 + intensity * 0.2})`;
                        const border =
                          m.return_pct >= 0
                            ? `rgba(52, 211, 153, ${0.1 + intensity * 0.2})`
                            : `rgba(248, 113, 113, ${0.1 + intensity * 0.2})`;

                        return (
                          <div
                            key={m.month}
                            className="text-center py-3 px-2 rounded-lg transition-all hover:scale-105"
                            style={{
                              background: bg,
                              border: `1px solid ${border}`,
                            }}
                          >
                            <div className="text-[10px] text-gray-500 font-mono">
                              {m.month}
                            </div>
                            <div
                              className={`text-sm font-bold font-mono mt-0.5 ${
                                m.return_pct >= 0
                                  ? "text-[var(--wolf-emerald)]"
                                  : "text-[var(--wolf-red)]"
                              }`}
                            >
                              {m.return_pct >= 0 ? "+" : ""}
                              {m.return_pct.toFixed(1)}%
                            </div>
                          </div>
                        );
                      }
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Empty State */}
          {!hasResults && !isRunning && (
            <div className="wolf-card p-16 text-center animate-in animate-in-3">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-[var(--surface)] border border-[var(--border)] mb-5">
                <svg
                  width="28"
                  height="28"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="var(--wolf-emerald)"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  style={{ opacity: 0.5 }}
                >
                  <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
                </svg>
              </div>
              <p className="text-[15px] text-gray-400 font-medium">
                No results yet
              </p>
              <p className="text-[12px] text-gray-600 mt-1.5 max-w-sm mx-auto leading-relaxed">
                Configure your strategy parameters and run a backtest to see
                equity curves, drawdowns, and trade-level analysis.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* ═══ RUN HISTORY ═══ */}
      {runs.length > 0 && (
        <div className="wolf-card p-4 md:p-6 animate-in animate-in-6">
          <div className="flex items-center justify-between mb-5">
            <SectionHeader color="amber" title="Run History" />
            <span className="text-[11px] text-gray-600 font-mono">
              {runs.length} run{runs.length !== 1 && "s"}
            </span>
          </div>
          <div className="space-y-1.5">
            {runs.map((run: BacktestRun) => {
              const cfg = run.config as Record<string, unknown>;
              const isSelected = run.id === selectedRunId;
              const returnPct = run.metrics?.total_return_pct ?? null;

              return (
                <div
                  key={run.id}
                  onClick={() => setSelectedRunId(run.id)}
                  className={`group flex items-center justify-between py-3 px-4 -mx-1 rounded-lg cursor-pointer transition-all ${
                    isSelected
                      ? "bg-[var(--surface-active)] border border-[var(--wolf-emerald)]/20 shadow-[0_0_20px_-8px_rgba(52,211,153,0.15)]"
                      : "hover:bg-[var(--surface-hover)]/50 border border-transparent"
                  }`}
                >
                  <div className="flex items-center gap-4">
                    <div
                      className={`w-1.5 h-1.5 rounded-full ${
                        run.status === "completed"
                          ? "bg-[var(--wolf-emerald)]"
                          : run.status === "running"
                            ? "bg-[var(--wolf-amber)] animate-pulse"
                            : "bg-[var(--wolf-red)]"
                      }`}
                      style={
                        run.status === "completed"
                          ? {
                              boxShadow:
                                "0 0 4px var(--wolf-emerald)",
                            }
                          : run.status === "running"
                            ? {
                                boxShadow:
                                  "0 0 4px var(--wolf-amber)",
                              }
                            : undefined
                      }
                    />
                    <div>
                      <span className="text-[13px] text-white font-mono font-medium">
                        {(cfg.symbol as string) ?? "?"}{" "}
                        <span className="text-gray-500">/</span>{" "}
                        <span className="text-gray-400">
                          {(cfg.strategy as string)?.replace(/_/g, " ") ?? "?"}
                        </span>{" "}
                        <span className="text-gray-500">/</span>{" "}
                        <span className="text-gray-600">
                          {(cfg.interval as string) ?? "1h"}
                        </span>
                      </span>
                      <p className="text-[11px] text-gray-600 mt-0.5 font-mono">
                        {new Date(run.created_at).toLocaleString([], {
                          month: "short",
                          day: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}{" "}
                        &middot; {run.trade_count} trades
                        {run.duration_seconds
                          ? ` \u00b7 ${run.duration_seconds.toFixed(1)}s`
                          : ""}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-5">
                    {returnPct !== null && (
                      <span
                        className={`text-sm font-bold font-mono ${
                          returnPct >= 0
                            ? "text-[var(--wolf-emerald)]"
                            : "text-[var(--wolf-red)]"
                        }`}
                      >
                        {returnPct >= 0 ? "+" : ""}
                        {returnPct.toFixed(2)}%
                      </span>
                    )}
                    {run.status === "running" && (
                      <span className="text-[10px] text-[var(--wolf-amber)] font-mono uppercase tracking-wider">
                        running
                      </span>
                    )}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteMutation.mutate(run.id);
                        if (isSelected) setSelectedRunId(null);
                      }}
                      className="text-gray-700 hover:text-[var(--wolf-red)] transition text-[11px] opacity-0 group-hover:opacity-100"
                      title="Delete run"
                    >
                      <svg
                        width="14"
                        height="14"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <path d="M3 6h18" />
                        <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
                        <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
                      </svg>
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

/* ─── Subcomponents ─── */

function SectionHeader({ color, title }: { color: string; title: string }) {
  return (
    <div className="flex items-center gap-2">
      <div
        className={`w-1 h-4 rounded-full`}
        style={{
          backgroundColor: `var(--wolf-${color})`,
          boxShadow: `0 0 8px color-mix(in srgb, var(--wolf-${color}) 30%, transparent)`,
        }}
      />
      <h2 className="section-title">{title}</h2>
    </div>
  );
}

function MetricCard({
  label,
  value,
  color = "blue",
}: {
  label: string;
  value: string;
  color?: string;
}) {
  const colorMap: Record<string, string> = {
    emerald: "text-[var(--wolf-emerald)]",
    blue: "text-[var(--wolf-blue)]",
    red: "text-[var(--wolf-red)]",
    purple: "text-[var(--wolf-purple)]",
    amber: "text-[var(--wolf-amber)]",
  };

  return (
    <div className={`wolf-card stat-card stat-card-${color} p-4`}>
      <p className="text-[10px] text-gray-600 uppercase tracking-wider font-semibold">
        {label}
      </p>
      <p
        className={`text-xl font-bold mt-1.5 tracking-tight font-mono ${colorMap[color] ?? "text-white"}`}
      >
        {value}
      </p>
    </div>
  );
}

function DetailRow({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color?: string;
}) {
  const colorMap: Record<string, string> = {
    emerald: "text-[var(--wolf-emerald)]",
    red: "text-[var(--wolf-red)]",
    blue: "text-[var(--wolf-blue)]",
  };

  return (
    <div className="flex items-center justify-between py-1.5">
      <span className="text-[11px] text-gray-600">{label}</span>
      <span
        className={`text-[13px] font-mono font-semibold ${colorMap[color ?? ""] ?? "text-gray-300"}`}
      >
        {value}
      </span>
    </div>
  );
}
