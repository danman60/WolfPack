"use client";

import { useQuery } from "@tanstack/react-query";
import { useExchange } from "@/lib/exchange";

export interface Candle {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface MarketInfo {
  symbol: string;
  base_asset: string;
  last_price: number;
  volume_24h: number;
  open_interest: number;
  funding_rate: number;
  max_leverage: number;
}

/** Fetch candle data for a symbol from the intel service. */
export function useCandles(
  symbol: string,
  interval: string = "1h",
  limit: number = 100
) {
  const { activeExchange } = useExchange();

  return useQuery({
    queryKey: ["candles", activeExchange, symbol, interval, limit],
    queryFn: async (): Promise<Candle[]> => {
      const params = new URLSearchParams({
        symbol,
        interval,
        limit: String(limit),
        exchange: activeExchange,
      });
      const res = await fetch(`/intel/market/candles?${params}`);
      if (!res.ok) return [];
      const data = await res.json();
      return data.candles ?? [];
    },
    refetchInterval: interval === "1m" ? 15_000 : 60_000,
    retry: false,
  });
}

/** Fetch latest price for a symbol. */
export function usePrice(symbol: string) {
  const { activeExchange } = useExchange();

  return useQuery({
    queryKey: ["price", activeExchange, symbol],
    queryFn: async () => {
      const res = await fetch(
        `/intel/market/price?symbol=${symbol}&exchange=${activeExchange}`
      );
      if (!res.ok) return null;
      return res.json();
    },
    refetchInterval: 10_000,
    retry: false,
  });
}

/** Fetch available markets from exchange. */
export function useMarkets() {
  const { activeExchange } = useExchange();

  return useQuery({
    queryKey: ["markets", activeExchange],
    queryFn: async (): Promise<MarketInfo[]> => {
      const res = await fetch(
        `/intel/market/markets?exchange=${activeExchange}`
      );
      if (!res.ok) return [];
      const data = await res.json();
      return data.markets ?? [];
    },
    staleTime: 60_000,
    retry: false,
  });
}
