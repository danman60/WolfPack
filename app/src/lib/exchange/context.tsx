"use client";

import { createContext, useContext, useState, useCallback, ReactNode } from "react";
import type { ExchangeId, ExchangeConfig } from "./types";
import { EXCHANGE_CONFIGS } from "./types";

interface ExchangeContextValue {
  activeExchange: ExchangeId;
  config: ExchangeConfig;
  switchExchange: (id: ExchangeId) => void;
  availableExchanges: ExchangeConfig[];
}

const ExchangeContext = createContext<ExchangeContextValue | null>(null);

export function ExchangeProvider({ children }: { children: ReactNode }) {
  const [activeExchange, setActiveExchange] = useState<ExchangeId>("hyperliquid");

  const switchExchange = useCallback((id: ExchangeId) => {
    setActiveExchange(id);
  }, []);

  const value: ExchangeContextValue = {
    activeExchange,
    config: EXCHANGE_CONFIGS[activeExchange],
    switchExchange,
    availableExchanges: Object.values(EXCHANGE_CONFIGS),
  };

  return (
    <ExchangeContext.Provider value={value}>
      {children}
    </ExchangeContext.Provider>
  );
}

export function useExchange() {
  const ctx = useContext(ExchangeContext);
  if (!ctx) throw new Error("useExchange must be used within ExchangeProvider");
  return ctx;
}
