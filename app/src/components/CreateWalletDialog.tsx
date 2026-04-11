"use client";

import { useState, useEffect } from "react";
import { Modal } from "@/components/Modal";
import { useCreateWallet, type WalletSummary } from "@/lib/hooks/useIntelligence";
import { toast } from "sonner";

interface CreateWalletDialogProps {
  open: boolean;
  onClose: () => void;
  wallets: WalletSummary[];
  cloneFrom?: string;
}

const YOLO_LABELS: Record<number, string> = {
  1: "Cautious",
  2: "Balanced",
  3: "Aggressive",
  4: "YOLO",
  5: "Full Send",
};

function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

export function CreateWalletDialog({
  open,
  onClose,
  wallets,
  cloneFrom,
}: CreateWalletDialogProps) {
  const createWallet = useCreateWallet();

  const [displayName, setDisplayName] = useState("");
  const [name, setName] = useState("");
  const [nameEdited, setNameEdited] = useState(false);
  const [description, setDescription] = useState("");
  const [startingEquity, setStartingEquity] = useState(10000);
  const [selectedClone, setSelectedClone] = useState(cloneFrom ?? "");
  const [yoloLevel, setYoloLevel] = useState(3);

  // Reset form when dialog opens
  useEffect(() => {
    if (open) {
      setDisplayName("");
      setName("");
      setNameEdited(false);
      setDescription("");
      setStartingEquity(10000);
      setSelectedClone(cloneFrom ?? "");
      setYoloLevel(3);
    }
  }, [open, cloneFrom]);

  // Auto-generate slug from display name
  useEffect(() => {
    if (!nameEdited) {
      setName(slugify(displayName));
    }
  }, [displayName, nameEdited]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!displayName.trim() || !name.trim()) {
      toast.error("Display name and slug are required");
      return;
    }

    try {
      await createWallet.mutateAsync({
        name: name.trim(),
        display_name: displayName.trim(),
        description: description.trim() || undefined,
        starting_equity: startingEquity,
        config: { yolo_level: yoloLevel },
        clone_from: selectedClone || undefined,
      });
      toast.success(`Wallet "${displayName}" created`);
      onClose();
    } catch (err) {
      toast.error(
        `Failed to create wallet: ${err instanceof Error ? err.message : "Unknown error"}`
      );
    }
  }

  const inputClass =
    "bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white w-full focus:outline-none focus:border-white/25 transition-colors";
  const labelClass = "text-sm text-gray-400 block mb-1";

  return (
    <Modal open={open} onClose={onClose} title="Create New Wallet">
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Display Name */}
        <div>
          <label className={labelClass}>Display Name *</label>
          <input
            type="text"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            className={inputClass}
            placeholder="e.g. Aggressive BTC"
            required
          />
        </div>

        {/* Slug */}
        <div>
          <label className={labelClass}>Name / Slug</label>
          <input
            type="text"
            value={name}
            onChange={(e) => {
              setName(e.target.value);
              setNameEdited(true);
            }}
            className={inputClass}
            placeholder="auto-generated"
          />
        </div>

        {/* Description */}
        <div>
          <label className={labelClass}>Description</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className={`${inputClass} resize-none`}
            rows={2}
            placeholder="Optional description..."
          />
        </div>

        {/* Starting Equity */}
        <div>
          <label className={labelClass}>Starting Equity ($)</label>
          <input
            type="number"
            value={startingEquity}
            onChange={(e) => setStartingEquity(Number(e.target.value))}
            className={inputClass}
            min={100}
            step={100}
          />
        </div>

        {/* Clone From */}
        <div>
          <label className={labelClass}>Clone From (optional)</label>
          <select
            value={selectedClone}
            onChange={(e) => setSelectedClone(e.target.value)}
            className={inputClass}
          >
            <option value="">None — start fresh</option>
            {wallets.map((w) => (
              <option key={w.name} value={w.name}>
                {w.display_name} (v{w.version})
              </option>
            ))}
          </select>
        </div>

        {/* YOLO Level */}
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

        {/* Submit */}
        <div className="flex justify-end gap-3 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={createWallet.isPending}
            className="px-4 py-2 text-sm font-semibold bg-[var(--wolf-blue)] text-white rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {createWallet.isPending ? "Creating..." : "Create Wallet"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
