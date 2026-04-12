"use client";

import { useMemo, useState } from "react";
import {
  usePortfolioHistory,
  useWalletsSummary,
  type WalletSummary,
} from "@/lib/hooks/useIntelligence";
import { WalletCard } from "@/components/WalletCard";
import { CreateWalletDialog } from "@/components/CreateWalletDialog";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type Snapshot = { created_at: string; equity: number };

type HistoryPayload = { snapshots?: Snapshot[] } | null | undefined;

function normalizeSeries(
  history: HistoryPayload,
  startingEquity: number,
  resetAt: string | null
): Array<{ t: number; pct: number; equity: number }> {
  const snaps = history?.snapshots ?? [];
  if (!snaps.length || startingEquity <= 0) return [];
  const cutoff = resetAt ? Date.parse(resetAt) : 0;
  const filtered = snaps
    .map((s) => ({ t: Date.parse(s.created_at), equity: Number(s.equity) }))
    .filter((p) => Number.isFinite(p.t) && Number.isFinite(p.equity))
    .filter((p) => (cutoff ? p.t >= cutoff : true))
    .sort((a, b) => a.t - b.t);
  return filtered.map((p) => ({
    t: p.t,
    equity: p.equity,
    pct: ((p.equity - startingEquity) / startingEquity) * 100,
  }));
}

export default function EvolutionPage() {
  const { data: wallets, isLoading } = useWalletsSummary();
  const [createOpen, setCreateOpen] = useState(false);
  const [cloneFrom, setCloneFrom] = useState<string | undefined>();

  const summaries = (wallets ?? []) as WalletSummary[];
  const activeWallets = summaries.filter((w) => w.status === "active");
  // Up to two wallets drive the normalized equity chart. Any additional wallets
  // can be added later — we only need v1/v2 for the current live test.
  const chartWallets = summaries.slice(0, 2);
  const totalEquity = summaries.reduce((s, w) => s + w.equity, 0);
  const totalPnl = summaries.reduce((s, w) => s + w.total_pnl, 0);
  const bestWallet = summaries.length
    ? summaries.reduce((best, w) =>
        w.total_pnl > best.total_pnl ? w : best
      )
    : null;

  return (
    <div className="space-y-5 md:space-y-7">
      {/* Header */}
      <div className="page-header flex items-start justify-between">
        <div>
          <h1 className="page-title">Wallet Evolution</h1>
          <p className="page-subtitle">
            Compare wallet configurations and track which strategies produce the
            best returns
          </p>
        </div>
        <button
          onClick={() => {
            setCloneFrom(undefined);
            setCreateOpen(true);
          }}
          className="px-4 py-2 text-sm font-semibold bg-[var(--wolf-blue)] text-white rounded-lg hover:opacity-90 transition-opacity shrink-0"
        >
          + New Wallet
        </button>
      </div>

      {/* Aggregate Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4">
        <AggregateStat
          label="Total Wallets"
          value={String(summaries.length)}
          sub={`${activeWallets.length} active`}
        />
        <AggregateStat
          label="Combined Equity"
          value={`$${totalEquity.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`}
        />
        <AggregateStat
          label="Combined P&L"
          value={`${totalPnl >= 0 ? "+" : ""}$${totalPnl.toFixed(2)}`}
          color={totalPnl >= 0 ? "text-[var(--wolf-emerald)]" : "text-[var(--wolf-red)]"}
        />
        <AggregateStat
          label="Best Performer"
          value={bestWallet?.display_name ?? "--"}
          sub={
            bestWallet
              ? `${bestWallet.total_pnl >= 0 ? "+" : ""}$${bestWallet.total_pnl.toFixed(2)}`
              : undefined
          }
          color={
            bestWallet && bestWallet.total_pnl >= 0
              ? "text-[var(--wolf-emerald)]"
              : bestWallet
                ? "text-[var(--wolf-red)]"
                : undefined
          }
        />
      </div>

      {/* Normalized Equity Chart */}
      {chartWallets.length > 0 && (
        <NormalizedEquityChart wallets={chartWallets} />
      )}

      {/* Wallet Grid */}
      {isLoading ? (
        <div className="text-center py-16 text-gray-500 text-sm">
          Loading wallet data...
        </div>
      ) : summaries.length === 0 ? (
        <div className="wolf-card p-8 text-center">
          <p className="text-gray-500 text-sm">
            No wallet summaries available. The intel service may be offline or no
            wallets have been configured yet.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {summaries.map((w) => (
            <WalletCard
              key={w.name}
              wallet={w}
              onClone={(name) => {
                setCloneFrom(name);
                setCreateOpen(true);
              }}
            />
          ))}
        </div>
      )}

      {/* Create Wallet Dialog */}
      <CreateWalletDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        wallets={summaries}
        cloneFrom={cloneFrom}
      />

      {/* Comparison Table */}
      {summaries.length === 1 && (
        <div className="wolf-card p-6 text-center text-gray-500 text-sm">
          Create a second wallet to enable side-by-side comparison
        </div>
      )}
      {summaries.length > 1 && (
        <div className="wolf-card p-4 md:p-6">
          <div className="flex items-center gap-2 mb-5">
            <div className="w-1 h-4 rounded-full bg-[var(--wolf-blue)]" />
            <h2 className="section-title">Comparison</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[11px] text-gray-500 uppercase tracking-wider border-b border-[var(--border)]">
                  <th className="text-left py-2 pr-4 font-medium">Wallet</th>
                  <th className="text-right py-2 px-3 font-medium">YOLO</th>
                  <th className="text-right py-2 px-3 font-medium">Equity</th>
                  <th className="text-right py-2 px-3 font-medium">Return %</th>
                  <th className="text-right py-2 px-3 font-medium">Total P&L</th>
                  <th className="text-right py-2 px-3 font-medium">Win Rate</th>
                  <th className="text-right py-2 px-3 font-medium">Trades</th>
                  <th className="text-right py-2 pl-3 font-medium">Open</th>
                </tr>
              </thead>
              <tbody>
                {summaries.map((w) => {
                  const ret =
                    w.starting_equity > 0
                      ? ((w.equity - w.starting_equity) / w.starting_equity) *
                        100
                      : 0;
                  return (
                    <tr
                      key={w.name}
                      className="border-b border-[var(--border)] last:border-0 hover:bg-white/[0.02] transition"
                    >
                      <td className="py-3 pr-4 text-white font-semibold">
                        {w.display_name}
                        <span className="ml-1.5 text-[10px] text-gray-500 font-mono">
                          v{w.version}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-right font-mono text-[var(--wolf-amber)]">
                        {w.yolo_level}
                      </td>
                      <td className="py-3 px-3 text-right font-mono text-white">
                        ${w.equity.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                      </td>
                      <td
                        className={`py-3 px-3 text-right font-mono font-bold ${
                          ret >= 0
                            ? "text-[var(--wolf-emerald)]"
                            : "text-[var(--wolf-red)]"
                        }`}
                      >
                        {ret >= 0 ? "+" : ""}
                        {ret.toFixed(2)}%
                      </td>
                      <td
                        className={`py-3 px-3 text-right font-mono font-bold ${
                          w.total_pnl >= 0
                            ? "text-[var(--wolf-emerald)]"
                            : "text-[var(--wolf-red)]"
                        }`}
                      >
                        {w.total_pnl >= 0 ? "+" : ""}${w.total_pnl.toFixed(2)}
                      </td>
                      <td className="py-3 px-3 text-right font-mono text-[var(--wolf-blue)]">
                        {w.win_rate.toFixed(1)}%
                      </td>
                      <td className="py-3 px-3 text-right font-mono text-gray-300">
                        {w.trade_count}
                      </td>
                      <td className="py-3 pl-3 text-right font-mono text-gray-300">
                        {w.open_positions}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

const CHART_COLORS = [
  "#10b981", // emerald — v1 Full Send
  "#f59e0b", // amber — v2 Conservative
] as const;

function NormalizedEquityChart({ wallets }: { wallets: WalletSummary[] }) {
  // Two stable hook slots — always called in the same order. Extra wallets are
  // clipped; if only one wallet exists we still query a placeholder name.
  const w0 = wallets[0];
  const w1 = wallets[1];
  const history0 = usePortfolioHistory(w0?.name ?? "paper_perp", 500);
  const history1 = usePortfolioHistory(w1?.name ?? "paper_perp", 500);

  const series = useMemo(() => {
    const out: Array<{
      wallet: WalletSummary;
      color: string;
      points: Array<{ t: number; pct: number; equity: number }>;
    }> = [];
    if (w0) {
      const resetAt =
        (w0.config?.reset_at as string | undefined) ?? null;
      out.push({
        wallet: w0,
        color: CHART_COLORS[0],
        points: normalizeSeries(
          history0.data as HistoryPayload,
          w0.starting_equity,
          resetAt
        ),
      });
    }
    if (w1) {
      const resetAt =
        (w1.config?.reset_at as string | undefined) ?? null;
      out.push({
        wallet: w1,
        color: CHART_COLORS[1],
        points: normalizeSeries(
          history1.data as HistoryPayload,
          w1.starting_equity,
          resetAt
        ),
      });
    }
    return out;
  }, [w0, w1, history0.data, history1.data]);

  // Merge into one data array keyed by timestamp, with per-wallet pct columns.
  const chartData = useMemo(() => {
    const byTime = new Map<number, Record<string, number>>();
    series.forEach((s) => {
      s.points.forEach((p) => {
        const row = byTime.get(p.t) ?? { t: p.t };
        row[`pct_${s.wallet.name}`] = p.pct;
        row[`eq_${s.wallet.name}`] = p.equity;
        byTime.set(p.t, row);
      });
    });
    return Array.from(byTime.values()).sort(
      (a, b) => (a.t as number) - (b.t as number)
    );
  }, [series]);

  const enoughData = series.every((s) => s.points.length >= 2);

  return (
    <div className="wolf-card p-4 md:p-6">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-1 h-4 rounded-full bg-[var(--wolf-emerald)]" />
        <h2 className="section-title">Normalized Equity (% Return Since Reset)</h2>
      </div>
      {!enoughData ? (
        <div className="h-56 flex items-center justify-center text-gray-500 text-sm">
          Waiting for cycle data…
        </div>
      ) : (
        <div style={{ height: 260 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={chartData}
              margin={{ top: 10, right: 16, left: 0, bottom: 0 }}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="rgba(255,255,255,0.05)"
              />
              <XAxis
                dataKey="t"
                type="number"
                domain={["dataMin", "dataMax"]}
                scale="time"
                tickFormatter={(v: number) =>
                  new Date(v).toLocaleTimeString(undefined, {
                    hour: "2-digit",
                    minute: "2-digit",
                  })
                }
                stroke="rgba(255,255,255,0.35)"
                fontSize={11}
              />
              <YAxis
                tickFormatter={(v: number) => `${v.toFixed(1)}%`}
                stroke="rgba(255,255,255,0.35)"
                fontSize={11}
                width={56}
              />
              <Tooltip
                contentStyle={{
                  background: "rgba(15,15,20,0.95)",
                  border: "1px solid rgba(255,255,255,0.12)",
                  borderRadius: 8,
                  fontSize: 12,
                }}
                labelFormatter={(label) => {
                  const v = typeof label === "number" ? label : Number(label);
                  if (!Number.isFinite(v)) return "";
                  return new Date(v).toLocaleString(undefined, {
                    month: "short",
                    day: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                  });
                }}
                formatter={(val, name) => {
                  const nameStr = typeof name === "string" ? name : String(name);
                  if (!nameStr.startsWith("pct_")) return [val, nameStr];
                  const walletName = nameStr.slice(4);
                  const walletLabel =
                    series.find((s) => s.wallet.name === walletName)?.wallet
                      .display_name ?? walletName;
                  const row = chartData.find(
                    (r) => r[`pct_${walletName}`] === val
                  );
                  const equity = row?.[`eq_${walletName}`];
                  const pctStr =
                    typeof val === "number" ? `${val.toFixed(2)}%` : String(val);
                  const eqStr =
                    typeof equity === "number"
                      ? ` ($${equity.toLocaleString(undefined, {
                          maximumFractionDigits: 0,
                        })})`
                      : "";
                  return [`${pctStr}${eqStr}`, walletLabel];
                }}
              />
              <Legend
                formatter={(value: string) => {
                  if (typeof value !== "string" || !value.startsWith("pct_"))
                    return value;
                  const walletName = value.slice(4);
                  return (
                    series.find((s) => s.wallet.name === walletName)?.wallet
                      .display_name ?? walletName
                  );
                }}
                wrapperStyle={{ fontSize: 11, color: "rgba(255,255,255,0.7)" }}
              />
              {series.map((s) => (
                <Line
                  key={s.wallet.name}
                  type="monotone"
                  dataKey={`pct_${s.wallet.name}`}
                  stroke={s.color}
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={false}
                  connectNulls
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

function AggregateStat({
  label,
  value,
  sub,
  color,
}: {
  label: string;
  value: string;
  sub?: string;
  color?: string;
}) {
  return (
    <div className="wolf-card p-4">
      <p className="text-[11px] text-gray-500 uppercase tracking-wider font-medium">
        {label}
      </p>
      <p
        className={`text-xl font-bold mt-1.5 tracking-tight ${color ?? "text-white"}`}
      >
        {value}
      </p>
      {sub && (
        <p className={`text-xs mt-0.5 ${color ?? "text-gray-400"}`}>{sub}</p>
      )}
    </div>
  );
}
