"use client";

import { useWalletContext } from "@/lib/wallet/context";
import { useWallets } from "@/lib/hooks/useIntelligence";

type WalletInfo = {
  id: number;
  name: string;
  mode: string;
  type: string;
  starting_equity: number;
  current_equity: number;
  status: string;
  config: Record<string, unknown>;
  display_name?: string;
};

type WalletsResponse = {
  wallets: WalletInfo[];
};

export function WalletSelector({ type }: { type: "perp" | "lp" }) {
  const { perpWallet, lpWallet, setPerpWallet, setLpWallet } =
    useWalletContext();
  const { data } = useWallets();

  const current = type === "perp" ? perpWallet : lpWallet;
  const setCurrent = type === "perp" ? setPerpWallet : setLpWallet;

  const wallets = (data as WalletsResponse | undefined)?.wallets ?? [];
  const filtered = wallets.filter((w) => w.type === type);

  const fmt = (n: number | undefined) =>
    typeof n === "number"
      ? n >= 1000
        ? `$${(n / 1000).toFixed(1)}k`
        : `$${n.toFixed(0)}`
      : "--";

  // Fallback: if no wallets loaded yet, show static paper/prod toggle
  if (filtered.length === 0) {
    const paperName = type === "perp" ? "paper_perp" : "paper_lp";
    const prodName = type === "perp" ? "prod_perp" : "prod_lp";
    const isPaper = current === paperName;

    return (
      <div className="inline-flex items-center gap-1 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-1">
        <button
          onClick={() => setCurrent(paperName)}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-semibold transition-colors ${
            isPaper
              ? "bg-[var(--wolf-blue)]/25 text-[var(--wolf-blue)]"
              : "text-gray-400 hover:text-white"
          }`}
        >
          <span className="uppercase tracking-wider">Paper</span>
        </button>
        <button
          onClick={() => setCurrent(prodName)}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-semibold transition-colors ${
            !isPaper
              ? "bg-[var(--wolf-emerald)]/25 text-[var(--wolf-emerald)]"
              : "text-gray-400 hover:text-white"
          }`}
        >
          <span className="uppercase tracking-wider">Production</span>
        </button>
      </div>
    );
  }

  const currentWallet = filtered.find((w) => w.name === current);

  return (
    <div className="inline-flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-1 px-2">
      <select
        value={current}
        onChange={(e) => setCurrent(e.target.value)}
        className="bg-transparent text-xs font-semibold text-white border-none outline-none cursor-pointer appearance-none pr-4"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%239ca3af' stroke-width='2'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E")`,
          backgroundRepeat: "no-repeat",
          backgroundPosition: "right 0 center",
        }}
      >
        {filtered.map((w) => (
          <option key={w.name} value={w.name} className="bg-[#1a1a2e] text-white">
            {w.display_name || w.name}
          </option>
        ))}
      </select>
      {currentWallet && (
        <span className="font-mono text-[10px] text-gray-400">
          {fmt(currentWallet.current_equity)}
        </span>
      )}
    </div>
  );
}
