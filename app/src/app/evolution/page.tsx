"use client";

import { useState } from "react";
import {
  useWalletsSummary,
  type WalletSummary,
} from "@/lib/hooks/useIntelligence";
import { WalletCard } from "@/components/WalletCard";
import { CreateWalletDialog } from "@/components/CreateWalletDialog";

export default function EvolutionPage() {
  const { data: wallets, isLoading } = useWalletsSummary();
  const [createOpen, setCreateOpen] = useState(false);
  const [cloneFrom, setCloneFrom] = useState<string | undefined>();

  const summaries = (wallets ?? []) as WalletSummary[];
  const activeWallets = summaries.filter((w) => w.status === "active");
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
