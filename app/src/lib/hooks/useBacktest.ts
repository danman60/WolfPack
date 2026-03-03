"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

export interface StrategyDef {
  key: string;
  name: string;
  description: string;
  parameters: Record<string, { type: string; default: number; min: number; max: number; desc: string }>;
  warmup_bars: number;
}

export interface BacktestRun {
  id: string;
  config: Record<string, unknown>;
  status: "running" | "completed" | "failed";
  metrics: Record<string, number> | null;
  trade_count: number;
  duration_seconds: number | null;
  progress_pct: number;
  error: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface BacktestTrade {
  id: number;
  run_id: string;
  entry_time: number;
  exit_time: number;
  direction: "long" | "short";
  entry_price: number;
  exit_price: number;
  size_usd: number;
  pnl_usd: number;
  pnl_pct: number;
  exit_reason: string;
  holding_bars: number;
}

// List available strategies
export function useStrategies() {
  return useQuery<{ strategies: StrategyDef[] }>({
    queryKey: ["backtest-strategies"],
    queryFn: async () => {
      const res = await fetch("/intel/backtest/strategies");
      if (!res.ok) throw new Error(`Failed: ${res.status}`);
      return res.json();
    },
    staleTime: 5 * 60_000,
  });
}

// List recent backtest runs
export function useBacktestRuns(limit: number = 20) {
  return useQuery<{ runs: BacktestRun[] }>({
    queryKey: ["backtest-runs", limit],
    queryFn: async () => {
      const res = await fetch(`/intel/backtest/runs?limit=${limit}`);
      if (!res.ok) throw new Error(`Failed: ${res.status}`);
      return res.json();
    },
    refetchInterval: 10_000,
  });
}

// Get full result for a single run
export function useBacktestResult(runId: string | null) {
  return useQuery({
    queryKey: ["backtest-result", runId],
    queryFn: async () => {
      const res = await fetch(`/intel/backtest/runs/${runId}`);
      if (!res.ok) throw new Error(`Failed: ${res.status}`);
      return res.json();
    },
    enabled: !!runId,
  });
}

// Poll status while running
export function useBacktestStatus(runId: string | null) {
  return useQuery({
    queryKey: ["backtest-status", runId],
    queryFn: async () => {
      const res = await fetch(`/intel/backtest/runs/${runId}/status`);
      if (!res.ok) throw new Error(`Failed: ${res.status}`);
      return res.json();
    },
    enabled: !!runId,
    refetchInterval: 2_000,
  });
}

// Start a new backtest
export function useStartBacktest() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (config: Record<string, unknown>) => {
      const res = await fetch("/intel/backtest/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      });
      if (!res.ok) throw new Error(`Failed: ${res.status}`);
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["backtest-runs"] });
    },
  });
}

// Delete a backtest run
export function useDeleteBacktest() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (runId: string) => {
      const res = await fetch(`/intel/backtest/runs/${runId}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error(`Failed: ${res.status}`);
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["backtest-runs"] });
    },
  });
}

// Compare multiple runs
export function useBacktestComparison(runIds: string[]) {
  return useQuery({
    queryKey: ["backtest-compare", runIds],
    queryFn: async () => {
      const res = await fetch("/intel/backtest/compare", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(runIds),
      });
      if (!res.ok) throw new Error(`Failed: ${res.status}`);
      return res.json();
    },
    enabled: runIds.length >= 2,
  });
}
