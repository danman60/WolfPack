"use client";

import { useExchange } from "@/lib/exchange";
import type { ExchangeId } from "@/lib/exchange";

export function ExchangeToggle() {
  const { activeExchange, switchExchange, availableExchanges } = useExchange();

  return (
    <div className="flex items-center gap-0.5 bg-[var(--surface)] rounded-lg p-1 border border-[var(--border)]">
      {availableExchanges.map((ex) => (
        <button
          key={ex.id}
          onClick={() => switchExchange(ex.id as ExchangeId)}
          className={`px-3.5 py-1.5 rounded-md text-xs font-semibold transition-all duration-150 ${
            activeExchange === ex.id
              ? "bg-[var(--wolf-emerald)]/15 text-[var(--wolf-emerald)] shadow-sm border border-[var(--wolf-emerald)]/20"
              : "text-gray-500 hover:text-gray-300 border border-transparent"
          }`}
        >
          {ex.name}
        </button>
      ))}
    </div>
  );
}
