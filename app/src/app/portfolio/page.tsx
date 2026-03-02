"use client";

import { useExchange } from "@/lib/exchange";
import {
  usePortfolio,
  usePortfolioHistory,
  useClosePosition,
} from "@/lib/hooks/useIntelligence";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";

export default function PortfolioPage() {
  const { config } = useExchange();
  const { data: portfolio } = usePortfolio();
  const { data: history } = usePortfolioHistory(200);
  const closeMutation = useClosePosition();

  const isActive = portfolio?.status === "active";
  const positions = portfolio?.positions ?? [];
  const snapshots = history?.snapshots ?? [];

  // Format chart data
  const chartData = snapshots.map(
    (s: { created_at: string; equity: number; unrealized_pnl: number }) => ({
      time: new Date(s.created_at).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      }),
      equity: s.equity,
      pnl: s.unrealized_pnl,
    })
  );

  const totalReturn = isActive
    ? ((portfolio.equity - portfolio.starting_equity) /
        portfolio.starting_equity) *
      100
    : 0;

  return (
    <div className="space-y-6">
      <div className="border-b border-[var(--border)] pb-4">
        <h1 className="text-2xl font-bold text-white">Portfolio</h1>
        <p className="text-gray-400 text-sm mt-1">
          Paper trading performance on {config.name}
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <StatCard
          label="Equity"
          value={isActive ? `$${portfolio.equity.toLocaleString()}` : "--"}
          color="emerald"
        />
        <StatCard
          label="Unrealized P&L"
          value={
            isActive
              ? `${portfolio.unrealized_pnl >= 0 ? "+" : ""}$${portfolio.unrealized_pnl.toFixed(2)}`
              : "--"
          }
          color={
            isActive && portfolio.unrealized_pnl >= 0 ? "emerald" : "red"
          }
        />
        <StatCard
          label="Realized P&L"
          value={
            isActive
              ? `${portfolio.realized_pnl >= 0 ? "+" : ""}$${portfolio.realized_pnl.toFixed(2)}`
              : "--"
          }
          color={isActive && portfolio.realized_pnl >= 0 ? "emerald" : "red"}
        />
        <StatCard
          label="Win Rate"
          value={
            isActive && portfolio.closed_trades > 0
              ? `${(portfolio.win_rate * 100).toFixed(1)}%`
              : "--"
          }
          color="blue"
        />
        <StatCard
          label="Return"
          value={isActive ? `${totalReturn >= 0 ? "+" : ""}${totalReturn.toFixed(2)}%` : "--"}
          color={totalReturn >= 0 ? "emerald" : "red"}
        />
      </div>

      {/* Equity Curve */}
      <div className="bg-surface-elevated border border-[var(--border)] rounded-lg p-6">
        <h2 className="text-lg font-semibold text-white mb-4">Equity Curve</h2>
        {chartData.length > 1 ? (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis
                dataKey="time"
                tick={{ fill: "#6b7280", fontSize: 11 }}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: "#6b7280", fontSize: 11 }}
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
        ) : (
          <div className="h-64 flex items-center justify-center text-gray-500 text-sm border border-dashed border-[var(--border)] rounded-md">
            {isActive
              ? "Waiting for portfolio snapshots..."
              : "Start paper trading to see equity curve"}
          </div>
        )}
      </div>

      {/* Open Positions */}
      <div className="bg-surface-elevated border border-[var(--border)] rounded-lg p-6">
        <h2 className="text-lg font-semibold text-white mb-4">
          Open Positions ({positions.length})
        </h2>
        {positions.length > 0 ? (
          <div className="space-y-3">
            {positions.map(
              (pos: {
                symbol: string;
                direction: string;
                entry_price: number;
                current_price: number;
                size_usd: number;
                unrealized_pnl: number;
                opened_at: string;
              }) => (
                <div
                  key={pos.symbol}
                  className="flex items-center justify-between py-3 border-b border-[var(--border)] last:border-0"
                >
                  <div className="flex items-center gap-4">
                    <span
                      className={`px-3 py-1 rounded text-xs font-bold uppercase ${
                        pos.direction === "long"
                          ? "bg-[var(--wolf-emerald)]/20 text-[var(--wolf-emerald)]"
                          : "bg-[var(--wolf-red)]/20 text-[var(--wolf-red)]"
                      }`}
                    >
                      {pos.direction}
                    </span>
                    <div>
                      <span className="text-white font-mono font-semibold">
                        {pos.symbol}
                      </span>
                      <p className="text-xs text-gray-400 mt-0.5">
                        Entry: ${pos.entry_price.toLocaleString()} | Size: $
                        {pos.size_usd.toFixed(2)}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-6">
                    <div className="text-right">
                      <div className="text-xs text-gray-500">Unrealized P&L</div>
                      <div
                        className={`text-sm font-bold ${
                          pos.unrealized_pnl >= 0
                            ? "text-[var(--wolf-emerald)]"
                            : "text-[var(--wolf-red)]"
                        }`}
                      >
                        {pos.unrealized_pnl >= 0 ? "+" : ""}$
                        {pos.unrealized_pnl.toFixed(2)}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-xs text-gray-500">Current</div>
                      <div className="text-sm text-white font-mono">
                        ${pos.current_price.toLocaleString()}
                      </div>
                    </div>
                    <button
                      onClick={() =>
                        closeMutation.mutate({
                          symbol: pos.symbol,
                          exchange: config.id,
                        })
                      }
                      disabled={closeMutation.isPending}
                      className="px-3 py-1.5 bg-[var(--wolf-red)]/20 text-[var(--wolf-red)] rounded text-xs font-semibold hover:bg-[var(--wolf-red)]/30 transition disabled:opacity-50"
                    >
                      Close
                    </button>
                  </div>
                </div>
              )
            )}
          </div>
        ) : (
          <div className="text-center py-8 text-gray-500 text-sm">
            {isActive
              ? "No open positions. Approve a recommendation to start paper trading."
              : "Paper trading engine not active. Run intelligence first."}
          </div>
        )}
      </div>
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
    <div className="bg-surface-elevated border border-[var(--border)] rounded-lg p-4">
      <p className="text-xs text-gray-500 uppercase tracking-wider">{label}</p>
      <p
        className={`text-xl font-bold mt-1 ${colorMap[color] ?? "text-white"}`}
      >
        {value}
      </p>
    </div>
  );
}
