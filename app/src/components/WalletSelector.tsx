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

  const paperName = type === "perp" ? "paper_perp" : "paper_lp";
  const prodName = type === "perp" ? "prod_perp" : "prod_lp";

  const wallets = (data as WalletsResponse | undefined)?.wallets ?? [];
  const paperWallet = wallets.find((w) => w.name === paperName);
  const prodWallet = wallets.find((w) => w.name === prodName);

  const fmt = (n: number | undefined) =>
    typeof n === "number"
      ? n >= 1000
        ? `$${(n / 1000).toFixed(1)}k`
        : `$${n.toFixed(0)}`
      : "--";

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
        title={`Paper ${type.toUpperCase()} wallet`}
      >
        <span className="uppercase tracking-wider">Paper</span>
        {paperWallet && (
          <span className="font-mono text-[10px] opacity-80">
            {fmt(paperWallet.current_equity)}
          </span>
        )}
      </button>
      <button
        onClick={() => setCurrent(prodName)}
        className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-semibold transition-colors ${
          !isPaper
            ? "bg-[var(--wolf-emerald)]/25 text-[var(--wolf-emerald)]"
            : "text-gray-400 hover:text-white"
        }`}
        title={`Production ${type.toUpperCase()} wallet`}
      >
        <span className="uppercase tracking-wider">Production</span>
        {prodWallet && (
          <span className="font-mono text-[10px] opacity-80">
            {fmt(prodWallet.current_equity)}
          </span>
        )}
      </button>
    </div>
  );
}
