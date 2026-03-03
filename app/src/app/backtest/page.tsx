"use client";

import { useState, useMemo } from "react";
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
} from "recharts";

const INTERVALS = ["1m", "5m", "15m", "1h", "4h", "1d"];
const DEFAULT_SYMBOLS = ["BTC", "ETH", "SOL", "DOGE", "ARB", "OP"];

export default function BacktestPage() {
  const { config } = useExchange();
  const { data: strategiesData } = useStrategies();
  const { data: runsData } = useBacktestRuns();
  const startMutation = useStartBacktest();
  const deleteMutation = useDeleteBacktest();

  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const { data: resultData } = useBacktestResult(selectedRunId);
  const { data: statusData } = useBacktestStatus(
    selectedRunId &&
      runsData?.runs?.find((r: BacktestRun) => r.id === selectedRunId)
        ?.status === "running"
      ? selectedRunId
      : null
  );

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
  const [strategyParams, setStrategyParams] = useState<Record<string, number>>(
    {}
  );

  const strategies = strategiesData?.strategies ?? [];
  const runs = runsData?.runs ?? [];
  const selectedRun = resultData?.run;
  const trades: BacktestTrade[] = resultData?.trades ?? [];
  const metrics = selectedRun?.metrics;
  const equityCurve = selectedRun?.equity_curve ?? [];
  const monthlyReturns = selectedRun?.monthly_returns ?? [];

  // Get current strategy param definitions
  const currentStrategy = strategies.find((s) => s.key === strategy);

  const handleRun = () => {
    const now = Date.now();
    const startTime = now - daysBack * 86_400_000;

    startMutation.mutate({
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
    });
  };

  // Chart data
  const equityChartData = useMemo(
    () =>
      equityCurve.map((p: { time: number; equity: number }) => ({
        time: new Date(p.time).toLocaleDateString([], {
          month: "short",
          day: "numeric",
        }),
        equity: p.equity,
      })),
    [equityCurve]
  );

  const drawdownChartData = useMemo(
    () =>
      equityCurve.map((p: { time: number; drawdown_pct: number }) => ({
        time: new Date(p.time).toLocaleDateString([], {
          month: "short",
          day: "numeric",
        }),
        drawdown: -p.drawdown_pct,
      })),
    [equityCurve]
  );

  return (
    <div className="space-y-7">
      <div className="page-header">
        <h1 className="page-title">Backtest</h1>
        <p className="page-subtitle">
          Test strategies against historical data on {config.name}
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Config Panel */}
        <div className="wolf-card p-6 lg:col-span-1">
          <div className="flex items-center gap-2 mb-5">
            <div className="w-1 h-4 rounded-full bg-[var(--wolf-blue)]" />
            <h2 className="section-title">Configuration</h2>
          </div>

          <div className="space-y-4">
            <FormField label="Symbol">
              <select
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
                className="w-full bg-[var(--surface)] border border-[var(--border)] rounded-md px-3 py-2 text-white text-sm"
              >
                {DEFAULT_SYMBOLS.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </FormField>

            <FormField label="Interval">
              <select
                value={interval}
                onChange={(e) => setInterval(e.target.value)}
                className="w-full bg-[var(--surface)] border border-[var(--border)] rounded-md px-3 py-2 text-white text-sm"
              >
                {INTERVALS.map((i) => (
                  <option key={i} value={i}>
                    {i}
                  </option>
                ))}
              </select>
            </FormField>

            <FormField label="Strategy">
              <select
                value={strategy}
                onChange={(e) => {
                  setStrategy(e.target.value);
                  setStrategyParams({});
                }}
                className="w-full bg-[var(--surface)] border border-[var(--border)] rounded-md px-3 py-2 text-white text-sm"
              >
                {strategies.map((s) => (
                  <option key={s.key} value={s.key}>
                    {s.name}
                  </option>
                ))}
              </select>
              {currentStrategy && (
                <p className="text-xs text-gray-500 mt-1">
                  {currentStrategy.description}
                </p>
              )}
            </FormField>

            {/* Dynamic strategy params */}
            {currentStrategy &&
              Object.entries(currentStrategy.parameters).map(
                ([key, param]) => (
                  <FormField key={key} label={key.replace(/_/g, " ")}>
                    <input
                      type="number"
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
                      className="w-full bg-[var(--surface)] border border-[var(--border)] rounded-md px-3 py-2 text-white text-sm"
                    />
                    <p className="text-[10px] text-gray-600 mt-0.5">
                      {param.desc}
                    </p>
                  </FormField>
                )
              )}

            <FormField label="Days Back">
              <input
                type="number"
                value={daysBack}
                onChange={(e) => setDaysBack(parseInt(e.target.value) || 30)}
                min={1}
                max={365}
                className="w-full bg-[var(--surface)] border border-[var(--border)] rounded-md px-3 py-2 text-white text-sm"
              />
            </FormField>

            <FormField label="Starting Equity ($)">
              <input
                type="number"
                value={startingEquity}
                onChange={(e) =>
                  setStartingEquity(parseInt(e.target.value) || 10000)
                }
                min={100}
                className="w-full bg-[var(--surface)] border border-[var(--border)] rounded-md px-3 py-2 text-white text-sm"
              />
            </FormField>

            <div className="grid grid-cols-2 gap-3">
              <FormField label="Commission (bps)">
                <input
                  type="number"
                  value={commissionBps}
                  onChange={(e) =>
                    setCommissionBps(parseFloat(e.target.value) || 0)
                  }
                  min={0}
                  className="w-full bg-[var(--surface)] border border-[var(--border)] rounded-md px-3 py-2 text-white text-sm"
                />
              </FormField>
              <FormField label="Slippage (bps)">
                <input
                  type="number"
                  value={slippageBps}
                  onChange={(e) =>
                    setSlippageBps(parseFloat(e.target.value) || 0)
                  }
                  min={0}
                  className="w-full bg-[var(--surface)] border border-[var(--border)] rounded-md px-3 py-2 text-white text-sm"
                />
              </FormField>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <FormField label="Stop Loss %">
                <input
                  type="number"
                  value={stopLossPct}
                  onChange={(e) => setStopLossPct(e.target.value)}
                  placeholder="None"
                  min={0.1}
                  step={0.5}
                  className="w-full bg-[var(--surface)] border border-[var(--border)] rounded-md px-3 py-2 text-white text-sm"
                />
              </FormField>
              <FormField label="Take Profit %">
                <input
                  type="number"
                  value={takeProfitPct}
                  onChange={(e) => setTakeProfitPct(e.target.value)}
                  placeholder="None"
                  min={0.1}
                  step={0.5}
                  className="w-full bg-[var(--surface)] border border-[var(--border)] rounded-md px-3 py-2 text-white text-sm"
                />
              </FormField>
            </div>

            <button
              onClick={handleRun}
              disabled={startMutation.isPending}
              className="w-full mt-2 py-2.5 bg-[var(--wolf-emerald)]/20 text-[var(--wolf-emerald)] border border-[var(--wolf-emerald)]/30 rounded-lg text-sm font-semibold hover:bg-[var(--wolf-emerald)]/30 transition disabled:opacity-50"
            >
              {startMutation.isPending ? "Starting..." : "Run Backtest"}
            </button>
          </div>
        </div>

        {/* Results Panel */}
        <div className="lg:col-span-2 space-y-6">
          {/* Status indicator for running test */}
          {statusData?.status === "running" && (
            <div className="wolf-card p-4 border-[var(--wolf-amber)]/30">
              <div className="flex items-center gap-3">
                <div className="w-2 h-2 rounded-full bg-[var(--wolf-amber)] animate-pulse" />
                <span className="text-sm text-[var(--wolf-amber)]">
                  Running...{" "}
                  {statusData.progress_pct?.toFixed(0) ?? 0}%
                </span>
              </div>
              <div className="mt-2 h-1.5 bg-[var(--surface)] rounded-full overflow-hidden">
                <div
                  className="h-full bg-[var(--wolf-amber)] rounded-full transition-all"
                  style={{
                    width: `${statusData.progress_pct ?? 0}%`,
                  }}
                />
              </div>
            </div>
          )}

          {/* Metrics Grid */}
          {metrics && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <StatCard
                label="Total Return"
                value={`${metrics.total_return_pct >= 0 ? "+" : ""}${metrics.total_return_pct.toFixed(2)}%`}
                color={metrics.total_return_pct >= 0 ? "emerald" : "red"}
              />
              <StatCard
                label="Sharpe Ratio"
                value={metrics.sharpe_ratio.toFixed(2)}
                color="blue"
              />
              <StatCard
                label="Sortino Ratio"
                value={metrics.sortino_ratio.toFixed(2)}
                color="blue"
              />
              <StatCard
                label="Max Drawdown"
                value={`-${metrics.max_drawdown_pct.toFixed(2)}%`}
                color="red"
              />
              <StatCard
                label="Win Rate"
                value={`${(metrics.win_rate * 100).toFixed(1)}%`}
                color="emerald"
              />
              <StatCard
                label="Profit Factor"
                value={metrics.profit_factor.toFixed(2)}
                color="purple"
              />
              <StatCard
                label="Total Trades"
                value={metrics.total_trades.toString()}
                color="blue"
              />
              <StatCard
                label="Calmar Ratio"
                value={metrics.calmar_ratio.toFixed(2)}
                color="purple"
              />
            </div>
          )}

          {/* Equity Curve */}
          {equityChartData.length > 1 && (
            <div className="wolf-card p-6">
              <div className="flex items-center gap-2 mb-5">
                <div className="w-1 h-4 rounded-full bg-[var(--wolf-emerald)]" />
                <h2 className="section-title">Equity Curve</h2>
              </div>
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={equityChartData}>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="rgba(255,255,255,0.05)"
                  />
                  <XAxis
                    dataKey="time"
                    tick={{ fill: "#6b7280", fontSize: 11 }}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fill: "#6b7280", fontSize: 11 }}
                    tickLine={false}
                    domain={["auto", "auto"]}
                    tickFormatter={(v: number) =>
                      `$${v.toLocaleString()}`
                    }
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "var(--surface-elevated)",
                      border: "1px solid var(--border)",
                      borderRadius: "0.5rem",
                      color: "white",
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="equity"
                    stroke="var(--wolf-emerald)"
                    strokeWidth={2}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Drawdown Chart */}
          {drawdownChartData.length > 1 && (
            <div className="wolf-card p-6">
              <div className="flex items-center gap-2 mb-5">
                <div className="w-1 h-4 rounded-full bg-[var(--wolf-red)]" />
                <h2 className="section-title">Drawdown</h2>
              </div>
              <ResponsiveContainer width="100%" height={180}>
                <AreaChart data={drawdownChartData}>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="rgba(255,255,255,0.05)"
                  />
                  <XAxis
                    dataKey="time"
                    tick={{ fill: "#6b7280", fontSize: 11 }}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fill: "#6b7280", fontSize: 11 }}
                    tickLine={false}
                    tickFormatter={(v: number) => `${v.toFixed(1)}%`}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "var(--surface-elevated)",
                      border: "1px solid var(--border)",
                      borderRadius: "0.5rem",
                      color: "white",
                    }}
                    formatter={(v: number | string | undefined) => [`${Number(v ?? 0).toFixed(2)}%`, "Drawdown"]}
                  />
                  <Area
                    type="monotone"
                    dataKey="drawdown"
                    stroke="var(--wolf-red)"
                    fill="rgba(248, 113, 113, 0.15)"
                    strokeWidth={1.5}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Monthly Returns */}
          {monthlyReturns.length > 0 && (
            <div className="wolf-card p-6">
              <div className="flex items-center gap-2 mb-5">
                <div className="w-1 h-4 rounded-full bg-[var(--wolf-purple)]" />
                <h2 className="section-title">Monthly Returns</h2>
              </div>
              <div className="flex flex-wrap gap-2">
                {monthlyReturns.map(
                  (m: { month: string; return_pct: number }) => (
                    <div
                      key={m.month}
                      className={`px-3 py-2 rounded-lg text-center min-w-[80px] ${
                        m.return_pct >= 0
                          ? "bg-[var(--wolf-emerald)]/10 text-[var(--wolf-emerald)]"
                          : "bg-[var(--wolf-red)]/10 text-[var(--wolf-red)]"
                      }`}
                    >
                      <div className="text-[10px] text-gray-500">
                        {m.month}
                      </div>
                      <div className="text-sm font-bold">
                        {m.return_pct >= 0 ? "+" : ""}
                        {m.return_pct.toFixed(2)}%
                      </div>
                    </div>
                  )
                )}
              </div>
            </div>
          )}

          {/* Trade Log */}
          {trades.length > 0 && (
            <div className="wolf-card p-6">
              <div className="flex items-center gap-2 mb-5">
                <div className="w-1 h-4 rounded-full bg-[var(--wolf-cyan)]" />
                <h2 className="section-title">
                  Trade Log ({trades.length})
                </h2>
              </div>
              <div className="overflow-x-auto">
                <div className="space-y-1.5">
                  {/* Header */}
                  <div className="grid grid-cols-8 gap-2 text-[10px] text-gray-500 uppercase tracking-wider px-2 pb-2 border-b border-[var(--border)]">
                    <span>Direction</span>
                    <span>Entry</span>
                    <span>Exit</span>
                    <span>Size</span>
                    <span>P&L $</span>
                    <span>P&L %</span>
                    <span>Bars</span>
                    <span>Reason</span>
                  </div>
                  {trades.slice(0, 100).map((t, i) => (
                    <div
                      key={i}
                      className="grid grid-cols-8 gap-2 text-xs px-2 py-1.5 hover:bg-[var(--surface-hover)] rounded transition"
                    >
                      <span
                        className={`font-bold uppercase ${
                          t.direction === "long"
                            ? "text-[var(--wolf-emerald)]"
                            : "text-[var(--wolf-red)]"
                        }`}
                      >
                        {t.direction}
                      </span>
                      <span className="font-mono text-gray-300">
                        ${t.entry_price.toLocaleString()}
                      </span>
                      <span className="font-mono text-gray-300">
                        ${t.exit_price.toLocaleString()}
                      </span>
                      <span className="text-gray-400">
                        ${t.size_usd.toFixed(0)}
                      </span>
                      <span
                        className={
                          t.pnl_usd >= 0
                            ? "text-[var(--wolf-emerald)]"
                            : "text-[var(--wolf-red)]"
                        }
                      >
                        {t.pnl_usd >= 0 ? "+" : ""}
                        ${t.pnl_usd.toFixed(2)}
                      </span>
                      <span
                        className={
                          t.pnl_pct >= 0
                            ? "text-[var(--wolf-emerald)]"
                            : "text-[var(--wolf-red)]"
                        }
                      >
                        {t.pnl_pct >= 0 ? "+" : ""}
                        {t.pnl_pct.toFixed(2)}%
                      </span>
                      <span className="text-gray-400">{t.holding_bars}</span>
                      <span className="text-gray-500">{t.exit_reason}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Empty state */}
          {!metrics && !statusData?.status && (
            <div className="wolf-card p-12 text-center">
              <p className="text-gray-500 text-sm">
                Configure and run a backtest to see results here.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Run History */}
      {runs.length > 0 && (
        <div className="wolf-card p-6">
          <div className="flex items-center gap-2 mb-5">
            <div className="w-1 h-4 rounded-full bg-[var(--wolf-amber)]" />
            <h2 className="section-title">Run History</h2>
          </div>
          <div className="space-y-2">
            {runs.map((run: BacktestRun) => {
              const cfg = run.config as Record<string, unknown>;
              const isSelected = run.id === selectedRunId;

              return (
                <div
                  key={run.id}
                  onClick={() => setSelectedRunId(run.id)}
                  className={`flex items-center justify-between p-3 rounded-lg cursor-pointer transition ${
                    isSelected
                      ? "bg-[var(--surface-active)] border border-[var(--wolf-emerald)]/30"
                      : "hover:bg-[var(--surface-hover)]"
                  }`}
                >
                  <div className="flex items-center gap-4">
                    <StatusBadge status={run.status} />
                    <div>
                      <span className="text-sm text-white font-mono">
                        {(cfg.symbol as string) ?? "?"} /{" "}
                        {(cfg.strategy as string) ?? "?"} /{" "}
                        {(cfg.interval as string) ?? "1h"}
                      </span>
                      <p className="text-xs text-gray-500 mt-0.5">
                        {new Date(run.created_at).toLocaleString()} |{" "}
                        {run.trade_count} trades
                        {run.duration_seconds
                          ? ` | ${run.duration_seconds.toFixed(1)}s`
                          : ""}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    {run.metrics && (
                      <span
                        className={`text-sm font-bold ${
                          (run.metrics.total_return_pct ?? 0) >= 0
                            ? "text-[var(--wolf-emerald)]"
                            : "text-[var(--wolf-red)]"
                        }`}
                      >
                        {(run.metrics.total_return_pct ?? 0) >= 0 ? "+" : ""}
                        {(run.metrics.total_return_pct ?? 0).toFixed(2)}%
                      </span>
                    )}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteMutation.mutate(run.id);
                        if (isSelected) setSelectedRunId(null);
                      }}
                      className="text-gray-600 hover:text-[var(--wolf-red)] transition text-xs"
                    >
                      Delete
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

function StatCard({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color: string;
}) {
  const colorMap: Record<string, string> = {
    emerald: "text-[var(--wolf-emerald)]",
    blue: "text-[var(--wolf-blue)]",
    red: "text-[var(--wolf-red)]",
    purple: "text-[var(--wolf-purple)]",
    amber: "text-[var(--wolf-amber)]",
  };

  return (
    <div className={`wolf-card stat-card stat-card-${color} p-3`}>
      <p className="text-[10px] text-gray-500 uppercase tracking-wider font-medium">
        {label}
      </p>
      <p
        className={`text-lg font-bold mt-1 tracking-tight ${colorMap[color] ?? "text-white"}`}
      >
        {value}
      </p>
    </div>
  );
}

function FormField({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-[11px] text-gray-500 uppercase tracking-wider font-medium mb-1.5">
        {label}
      </label>
      {children}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    completed:
      "bg-[var(--wolf-emerald)]/20 text-[var(--wolf-emerald)]",
    running: "bg-[var(--wolf-amber)]/20 text-[var(--wolf-amber)]",
    failed: "bg-[var(--wolf-red)]/20 text-[var(--wolf-red)]",
  };

  return (
    <span
      className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${styles[status] ?? "text-gray-500"}`}
    >
      {status}
    </span>
  );
}
