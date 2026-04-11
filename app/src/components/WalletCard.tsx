"use client";

import { useState } from "react";
import {
  usePauseResumeWallet,
  type WalletSummary,
} from "@/lib/hooks/useIntelligence";
import { WalletConfigEditor } from "@/components/WalletConfigEditor";
import { toast } from "sonner";

interface WalletCardProps {
  wallet: WalletSummary;
  onClone?: (walletName: string) => void;
}

export function WalletCard({ wallet, onClone }: WalletCardProps) {
  const [editOpen, setEditOpen] = useState(false);
  const pauseResume = usePauseResumeWallet();

  const profitable = wallet.total_pnl > 0;
  const returnPct =
    wallet.starting_equity > 0
      ? ((wallet.equity - wallet.starting_equity) / wallet.starting_equity) *
        100
      : 0;

  const borderColor = profitable
    ? "border-[var(--wolf-emerald)]/40"
    : "border-[var(--wolf-red)]/40";
  const accentColor = profitable
    ? "text-[var(--wolf-emerald)]"
    : "text-[var(--wolf-red)]";

  return (
    <div
      className={`wolf-card p-5 border ${borderColor} transition-colors hover:border-opacity-60`}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2.5">
          {/* Status dot */}
          <span
            className={`w-2 h-2 rounded-full ${
              wallet.status === "active" ? "bg-green-500" : "bg-gray-500"
            }`}
            title={wallet.status}
          />
          <h3 className="text-white font-semibold text-sm tracking-tight">
            {wallet.display_name}
          </h3>
          {/* Version badge */}
          <span className="px-1.5 py-0.5 rounded text-[10px] font-mono font-bold bg-[var(--surface)] text-gray-400 border border-[var(--border)]">
            v{wallet.version}
          </span>
        </div>
        {/* YOLO badge */}
        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-[var(--wolf-amber)]/15 text-[var(--wolf-amber)]">
          YOLO {wallet.yolo_level}
        </span>
      </div>

      {/* 2x2 Metrics Grid */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        <MetricCell
          label="Equity"
          value={`$${wallet.equity.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
          color="text-white"
        />
        <MetricCell
          label="Return"
          value={`${returnPct >= 0 ? "+" : ""}${returnPct.toFixed(2)}%`}
          color={accentColor}
        />
        <MetricCell
          label="Trades"
          value={String(wallet.trade_count)}
          color="text-gray-300"
        />
        <MetricCell
          label="Win Rate"
          value={`${wallet.win_rate.toFixed(1)}%`}
          color="text-[var(--wolf-blue)]"
        />
      </div>

      {/* P&L Row */}
      <div className="flex items-center justify-between py-3 border-t border-[var(--border)]">
        <div>
          <span className="text-[10px] text-gray-500 uppercase tracking-wider">
            Realized
          </span>
          <p
            className={`text-sm font-bold font-mono ${
              wallet.realized_pnl >= 0
                ? "text-[var(--wolf-emerald)]"
                : "text-[var(--wolf-red)]"
            }`}
          >
            {wallet.realized_pnl >= 0 ? "+" : ""}$
            {wallet.realized_pnl.toFixed(2)}
          </p>
        </div>
        <div className="text-right">
          <span className="text-[10px] text-gray-500 uppercase tracking-wider">
            Unrealized
          </span>
          <p
            className={`text-sm font-bold font-mono ${
              wallet.unrealized_pnl >= 0
                ? "text-[var(--wolf-emerald)]"
                : "text-[var(--wolf-red)]"
            }`}
          >
            {wallet.unrealized_pnl >= 0 ? "+" : ""}$
            {wallet.unrealized_pnl.toFixed(2)}
          </p>
        </div>
        <div className="text-right">
          <span className="text-[10px] text-gray-500 uppercase tracking-wider">
            Positions
          </span>
          <p className="text-sm font-bold text-white font-mono">
            {wallet.open_positions}
          </p>
        </div>
      </div>

      {/* Description */}
      {wallet.description && (
        <p className="text-[11px] text-gray-500 mt-2 line-clamp-2">
          {wallet.description}
        </p>
      )}

      {/* Action Buttons */}
      <div className="flex items-center gap-2 mt-3 pt-3 border-t border-[var(--border)]">
        <button
          onClick={() => setEditOpen(true)}
          className="px-3 py-1.5 text-[11px] font-semibold text-gray-300 bg-white/5 border border-white/10 rounded-lg hover:bg-white/10 transition-colors"
        >
          Edit
        </button>
        <button
          onClick={() => onClone?.(wallet.name)}
          className="px-3 py-1.5 text-[11px] font-semibold text-gray-300 bg-white/5 border border-white/10 rounded-lg hover:bg-white/10 transition-colors"
        >
          Clone
        </button>
        <button
          onClick={async () => {
            const action = wallet.status === "active" ? "pause" : "resume";
            try {
              await pauseResume.mutateAsync({ name: wallet.name, action });
              toast.success(`Wallet ${action}d`);
            } catch (err) {
              toast.error(
                `Failed to ${action}: ${err instanceof Error ? err.message : "Unknown error"}`
              );
            }
          }}
          disabled={pauseResume.isPending}
          className={`px-3 py-1.5 text-[11px] font-semibold rounded-lg border transition-colors disabled:opacity-50 ${
            wallet.status === "active"
              ? "text-[var(--wolf-amber)] border-[var(--wolf-amber)]/30 hover:bg-[var(--wolf-amber)]/10"
              : "text-[var(--wolf-emerald)] border-[var(--wolf-emerald)]/30 hover:bg-[var(--wolf-emerald)]/10"
          }`}
        >
          {pauseResume.isPending
            ? "..."
            : wallet.status === "active"
              ? "Pause"
              : "Resume"}
        </button>
      </div>

      {/* Config Editor Modal */}
      <WalletConfigEditor
        open={editOpen}
        onClose={() => setEditOpen(false)}
        wallet={wallet}
      />
    </div>
  );
}

function MetricCell({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color: string;
}) {
  return (
    <div className="bg-[var(--surface)] rounded-lg p-2.5">
      <p className="text-[10px] text-gray-500 uppercase tracking-wider font-medium">
        {label}
      </p>
      <p className={`text-lg font-bold mt-0.5 tracking-tight font-mono ${color}`}>
        {value}
      </p>
    </div>
  );
}
