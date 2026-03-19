"use client";

import { useQuery } from "@tanstack/react-query";
import { intelFetch } from "@/lib/intel";

interface PredictionAccuracy {
  accuracy_pct: number;
  total_scored: number;
  correct: number;
  incorrect: number;
  neutral: number;
}

interface PredictionRecord {
  id: string;
  recommendation_id: string;
  agent_name: string;
  exchange_id: string;
  symbol: string;
  predicted_direction: string;
  predicted_conviction: number;
  predicted_at: string;
  price_at_prediction: number;
  price_after: number;
  check_interval_hours: number;
  outcome: string;
  pnl_pct: number;
  scored_at: string;
}

export function usePredictionAccuracy(days: number = 7) {
  return useQuery({
    queryKey: ["prediction-accuracy", days],
    queryFn: async () => {
      const res = await intelFetch(`/intel/predictions/accuracy?days=${days}`);
      if (!res.ok) return { accuracy_pct: 0, total_scored: 0, correct: 0, incorrect: 0, neutral: 0 };
      return res.json() as Promise<PredictionAccuracy>;
    },
    refetchInterval: 60_000,
    retry: false,
  });
}

export function usePredictionHistory(days: number = 7) {
  return useQuery({
    queryKey: ["prediction-history", days],
    queryFn: async () => {
      const res = await intelFetch(`/intel/predictions/history?days=${days}`);
      if (!res.ok) return [];
      const data = await res.json();
      return (data.predictions ?? []) as PredictionRecord[];
    },
    refetchInterval: 60_000,
    retry: false,
  });
}
