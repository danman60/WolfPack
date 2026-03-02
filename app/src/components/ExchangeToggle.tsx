"use client";

import { useExchange } from "@/lib/exchange";
import type { ExchangeId } from "@/lib/exchange";

export function ExchangeToggle() {
  const { activeExchange, switchExchange, availableExchanges } = useExchange();

  return (
    <div className="flex items-center gap-1 bg-surface rounded-lg p-1 border border-[var(--border)]">
      {availableExchanges.map((ex) => (
        <button
          key={ex.id}
          onClick={() => switchExchange(ex.id as ExchangeId)}
          className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
            activeExchange === ex.id
              ? "bg-[var(--primary-blue)] text-black shadow-sm"
              : "text-[var(--neutral-500)] hover:text-[var(--neutral-700)] hover:bg-[var(--surface-hover)]"
          }`}
        >
          {ex.name}
        </button>
      ))}
    </div>
  );
}
