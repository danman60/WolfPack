"use client";

import { useState } from "react";
import { Modal } from "@/components/Modal";
import {
  useUpdateWalletConfig,
  type WalletSummary,
} from "@/lib/hooks/useIntelligence";
import { toast } from "sonner";

interface WalletConfigEditorProps {
  open: boolean;
  onClose: () => void;
  wallet: WalletSummary;
}

const YOLO_LABELS: Record<number, string> = {
  1: "Cautious",
  2: "Balanced",
  3: "Aggressive",
  4: "YOLO",
  5: "Full Send",
};

function getNum(config: Record<string, unknown>, key: string, fallback: number): number {
  const v = config[key];
  return typeof v === "number" ? v : fallback;
}

function getBool(config: Record<string, unknown>, key: string, fallback: boolean): boolean {
  const v = config[key];
  return typeof v === "boolean" ? v : fallback;
}

export function WalletConfigEditor({
  open,
  onClose,
  wallet,
}: WalletConfigEditorProps) {
  const updateConfig = useUpdateWalletConfig();
  const c = wallet.config;

  // Risk Profile
  const [yoloLevel, setYoloLevel] = useState(getNum(c, "yolo_level", 3));
  const [convictionFloor, setConvictionFloor] = useState(getNum(c, "conviction_floor", 50));
  const [maxPositions, setMaxPositions] = useState(getNum(c, "max_positions", 5));
  const [maxPositionsPerSymbol, setMaxPositionsPerSymbol] = useState(getNum(c, "max_positions_per_symbol", 1));
  const [requireStopLoss, setRequireStopLoss] = useState(getBool(c, "require_stop_loss", true));

  // Sizing
  const [basePct, setBasePct] = useState(getNum(c, "base_pct", 5));
  const [briefOnlyMultiplier, setBriefOnlyMultiplier] = useState(getNum(c, "brief_only_multiplier", 0.5));
  const [minPerfMultiplier, setMinPerfMultiplier] = useState(getNum(c, "min_performance_multiplier", 0.5));
  const [minPositionUsd, setMinPositionUsd] = useState(getNum(c, "min_position_usd", 50));
  const [tradeSpacing, setTradeSpacing] = useState(getNum(c, "trade_spacing_seconds", 300));

  // Limits
  const [maxTradesPerDay, setMaxTradesPerDay] = useState(getNum(c, "max_trades_per_day", 10));

  async function handleSave() {
    const patch: Record<string, unknown> = {};

    // Only send changed values
    if (yoloLevel !== getNum(c, "yolo_level", 3)) patch.yolo_level = yoloLevel;
    if (convictionFloor !== getNum(c, "conviction_floor", 50)) patch.conviction_floor = convictionFloor;
    if (maxPositions !== getNum(c, "max_positions", 5)) patch.max_positions = maxPositions;
    if (maxPositionsPerSymbol !== getNum(c, "max_positions_per_symbol", 1)) patch.max_positions_per_symbol = maxPositionsPerSymbol;
    if (requireStopLoss !== getBool(c, "require_stop_loss", true)) patch.require_stop_loss = requireStopLoss;
    if (basePct !== getNum(c, "base_pct", 5)) patch.base_pct = basePct;
    if (briefOnlyMultiplier !== getNum(c, "brief_only_multiplier", 0.5)) patch.brief_only_multiplier = briefOnlyMultiplier;
    if (minPerfMultiplier !== getNum(c, "min_performance_multiplier", 0.5)) patch.min_performance_multiplier = minPerfMultiplier;
    if (minPositionUsd !== getNum(c, "min_position_usd", 50)) patch.min_position_usd = minPositionUsd;
    if (tradeSpacing !== getNum(c, "trade_spacing_seconds", 300)) patch.trade_spacing_seconds = tradeSpacing;
    if (maxTradesPerDay !== getNum(c, "max_trades_per_day", 10)) patch.max_trades_per_day = maxTradesPerDay;

    if (Object.keys(patch).length === 0) {
      toast.info("No changes to save");
      return;
    }

    try {
      await updateConfig.mutateAsync({ name: wallet.name, config: patch });
      toast.success(`Config updated for "${wallet.display_name}"`);
      onClose();
    } catch (err) {
      toast.error(
        `Failed to update config: ${err instanceof Error ? err.message : "Unknown error"}`
      );
    }
  }

  const inputClass =
    "bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white w-full focus:outline-none focus:border-white/25 transition-colors";
  const labelClass = "text-sm text-gray-400 block mb-1";
  const sectionClass = "space-y-3";
  const sectionTitleClass =
    "text-xs font-semibold uppercase tracking-wider text-gray-500 border-b border-white/10 pb-2";

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`Edit Config — ${wallet.display_name}`}
    >
      <div className="space-y-5">
        {/* Risk Profile */}
        <div className={sectionClass}>
          <h3 className={sectionTitleClass}>Risk Profile</h3>

          <div>
            <label className={labelClass}>
              YOLO Level: {yoloLevel} — {YOLO_LABELS[yoloLevel]}
            </label>
            <input
              type="range"
              min={1}
              max={5}
              step={1}
              value={yoloLevel}
              onChange={(e) => setYoloLevel(Number(e.target.value))}
              className="w-full accent-[var(--wolf-amber)]"
            />
            <div className="flex justify-between text-[10px] text-gray-500 mt-1">
              <span>Cautious</span>
              <span>Full Send</span>
            </div>
          </div>

          <div>
            <label className={labelClass}>Conviction Floor ({convictionFloor})</label>
            <input
              type="number"
              min={10}
              max={90}
              value={convictionFloor}
              onChange={(e) => setConvictionFloor(Number(e.target.value))}
              className={inputClass}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelClass}>Max Positions</label>
              <input
                type="number"
                min={1}
                max={20}
                value={maxPositions}
                onChange={(e) => setMaxPositions(Number(e.target.value))}
                className={inputClass}
              />
            </div>
            <div>
              <label className={labelClass}>Max Per Symbol</label>
              <input
                type="number"
                min={1}
                max={5}
                value={maxPositionsPerSymbol}
                onChange={(e) => setMaxPositionsPerSymbol(Number(e.target.value))}
                className={inputClass}
              />
            </div>
          </div>

          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={requireStopLoss}
              onChange={(e) => setRequireStopLoss(e.target.checked)}
              className="w-4 h-4 rounded border-white/10 bg-white/5 accent-[var(--wolf-blue)]"
            />
            <span className="text-sm text-gray-300">Require Stop Loss</span>
          </label>
        </div>

        {/* Sizing */}
        <div className={sectionClass}>
          <h3 className={sectionTitleClass}>Sizing</h3>

          <div>
            <label className={labelClass}>Base % ({basePct})</label>
            <input
              type="number"
              min={1}
              max={30}
              value={basePct}
              onChange={(e) => setBasePct(Number(e.target.value))}
              className={inputClass}
            />
          </div>

          <div>
            <label className={labelClass}>
              Brief-Only Multiplier ({briefOnlyMultiplier.toFixed(2)})
            </label>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={briefOnlyMultiplier}
              onChange={(e) => setBriefOnlyMultiplier(Number(e.target.value))}
              className="w-full accent-[var(--wolf-blue)]"
            />
          </div>

          <div>
            <label className={labelClass}>
              Min Performance Multiplier ({minPerfMultiplier.toFixed(2)})
            </label>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={minPerfMultiplier}
              onChange={(e) => setMinPerfMultiplier(Number(e.target.value))}
              className="w-full accent-[var(--wolf-blue)]"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelClass}>Min Position USD</label>
              <input
                type="number"
                min={1}
                value={minPositionUsd}
                onChange={(e) => setMinPositionUsd(Number(e.target.value))}
                className={inputClass}
              />
            </div>
            <div>
              <label className={labelClass}>Trade Spacing (sec)</label>
              <input
                type="number"
                min={0}
                value={tradeSpacing}
                onChange={(e) => setTradeSpacing(Number(e.target.value))}
                className={inputClass}
              />
            </div>
          </div>
        </div>

        {/* Limits */}
        <div className={sectionClass}>
          <h3 className={sectionTitleClass}>Limits</h3>
          <div>
            <label className={labelClass}>Max Trades Per Day</label>
            <input
              type="number"
              min={1}
              value={maxTradesPerDay}
              onChange={(e) => setMaxTradesPerDay(Number(e.target.value))}
              className={inputClass}
            />
          </div>
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-3 pt-2 border-t border-white/10">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={updateConfig.isPending}
            className="px-4 py-2 text-sm font-semibold bg-[var(--wolf-blue)] text-white rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {updateConfig.isPending ? "Saving..." : "Save Changes"}
          </button>
        </div>
      </div>
    </Modal>
  );
}
