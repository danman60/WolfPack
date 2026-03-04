"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { supabase } from "@/lib/supabase";
import { intelFetch } from "@/lib/intel";

/* ── Row types matching Supabase wp_ tables ── */

interface AgentOutput {
  id: string;
  agent_name: string;
  exchange_id: string;
  summary: string;
  signals: Record<string, unknown>[];
  confidence: number;
  raw_data: Record<string, unknown>;
  created_at: string;
}

interface ModuleOutput {
  id: string;
  module_name: string;
  exchange_id: string;
  output_data: Record<string, unknown>;
  created_at: string;
}

interface TradeRecommendation {
  id: string;
  symbol: string;
  direction: string;
  conviction: number;
  status: string;
  rationale: string;
  entry_price: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  size_pct: number | null;
  created_at: string;
  [key: string]: unknown; // Allow additional fields from DB
}

/* ── Hooks ── */

// Fetch latest agent outputs (one per agent)
export function useAgentOutputs() {
  return useQuery({
    queryKey: ["agent-outputs"],
    queryFn: async () => {
      const { data, error } = await supabase
        .from("wp_agent_outputs")
        .select("*")
        .order("created_at", { ascending: false })
        .limit(20);

      if (error) throw error;

      const rows = (data ?? []) as unknown as AgentOutput[];
      // Deduplicate: keep latest per agent
      const seen = new Map<string, AgentOutput>();
      for (const row of rows) {
        if (!seen.has(row.agent_name)) {
          seen.set(row.agent_name, row);
        }
      }
      return Object.fromEntries(seen) as Record<string, AgentOutput>;
    },
    refetchInterval: 30_000, // Poll every 30s
  });
}

// Fetch latest module outputs
export function useModuleOutputs() {
  return useQuery({
    queryKey: ["module-outputs"],
    queryFn: async () => {
      const { data, error } = await supabase
        .from("wp_module_outputs")
        .select("*")
        .order("created_at", { ascending: false })
        .limit(40);

      if (error) throw error;

      const rows = (data ?? []) as unknown as ModuleOutput[];
      // Deduplicate: keep latest per module
      const seen = new Map<string, ModuleOutput>();
      for (const row of rows) {
        if (!seen.has(row.module_name)) {
          seen.set(row.module_name, row);
        }
      }
      return Object.fromEntries(seen) as Record<string, ModuleOutput>;
    },
    refetchInterval: 30_000,
  });
}

// Fetch trade recommendations
export function useRecommendations(status: string = "pending") {
  return useQuery({
    queryKey: ["recommendations", status],
    queryFn: async () => {
      const { data, error } = await supabase
        .from("wp_trade_recommendations")
        .select("*")
        .eq("status", status)
        .order("created_at", { ascending: false })
        .limit(20);

      if (error) throw error;
      return (data ?? []) as unknown as TradeRecommendation[];
    },
    refetchInterval: 15_000,
  });
}

// Trigger intelligence run via the intel service API
export function useRunIntelligence() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ exchange, symbol }: { exchange: string; symbol: string }) => {
      const res = await intelFetch(`/intel/intelligence/run?exchange=${exchange}&symbol=${symbol}`, {
        method: "POST",
      });
      if (!res.ok) throw new Error(`Intel service error: ${res.status}`);
      return res.json();
    },
    onSuccess: () => {
      // Intelligence cycle takes 30-60s. Poll at increasing intervals.
      const invalidateAll = () => {
        queryClient.invalidateQueries({ queryKey: ["agent-outputs"] });
        queryClient.invalidateQueries({ queryKey: ["module-outputs"] });
        queryClient.invalidateQueries({ queryKey: ["recommendations"] });
        queryClient.invalidateQueries({ queryKey: ["agent-status"] });
        queryClient.invalidateQueries({ queryKey: ["portfolio"] });
      };
      setTimeout(invalidateAll, 10_000);
      setTimeout(invalidateAll, 20_000);
      setTimeout(invalidateAll, 35_000);
      setTimeout(invalidateAll, 60_000);
    },
  });
}

// Approve a recommendation
export function useApproveRecommendation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, exchange }: { id: string; exchange: string }) => {
      const res = await intelFetch(`/intel/recommendations/${id}/approve?exchange=${exchange}`, {
        method: "POST",
      });
      if (!res.ok) throw new Error(`Approve failed: ${res.status}`);
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["recommendations"] });
      queryClient.invalidateQueries({ queryKey: ["portfolio"] });
    },
  });
}

// Reject a recommendation
export function useRejectRecommendation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string) => {
      const res = await intelFetch(`/intel/recommendations/${id}/reject`, {
        method: "POST",
      });
      if (!res.ok) throw new Error(`Reject failed: ${res.status}`);
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["recommendations"] });
    },
  });
}

// Fetch portfolio state — tries VPS first, falls back to Supabase snapshot
export function usePortfolio() {
  return useQuery({
    queryKey: ["portfolio"],
    queryFn: async () => {
      // Try VPS intel service first
      try {
        const res = await intelFetch("/intel/portfolio");
        if (res.ok) {
          const data = await res.json();
          if (data.status === "active") return data;
        }
      } catch {
        // VPS unreachable — fall through to snapshot
      }

      // Fallback: load latest snapshot from Supabase
      const { data, error } = await supabase
        .from("wp_portfolio_snapshots")
        .select("*")
        .order("created_at", { ascending: false })
        .limit(1);

      if (error || !data?.length) return null;

      const snap = (data as unknown[])[0] as Record<string, unknown>;
      return {
        status: "active",
        equity: snap.equity ?? 10000,
        starting_equity: 10000,
        realized_pnl: snap.realized_pnl ?? 0,
        unrealized_pnl: snap.unrealized_pnl ?? 0,
        free_collateral: snap.free_collateral ?? 10000,
        positions: (snap.positions as Record<string, unknown>[]) ?? [],
        closed_trades: 0,
        winning_trades: 0,
        win_rate: 0,
      };
    },
    refetchInterval: 15_000,
    retry: false,
  });
}

// Fetch portfolio snapshot history
export function usePortfolioHistory(limit: number = 100) {
  return useQuery({
    queryKey: ["portfolio-history", limit],
    queryFn: async () => {
      const res = await intelFetch(`/intel/portfolio/history?limit=${limit}`);
      if (!res.ok) return { snapshots: [] };
      return res.json();
    },
    refetchInterval: 60_000,
    retry: false,
  });
}

// Close a paper position
export function useClosePosition() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ symbol, exchange }: { symbol: string; exchange: string }) => {
      const res = await intelFetch(`/intel/portfolio/close/${symbol}?exchange=${exchange}`, {
        method: "POST",
      });
      if (!res.ok) throw new Error(`Close failed: ${res.status}`);
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["portfolio"] });
      queryClient.invalidateQueries({ queryKey: ["portfolio-history"] });
    },
  });
}

// Fetch strategy mode and safety checklist
export function useStrategyMode() {
  return useQuery({
    queryKey: ["strategy-mode"],
    queryFn: async () => {
      const res = await intelFetch("/intel/strategy/mode");
      if (!res.ok) return null;
      return res.json();
    },
    refetchInterval: 30_000,
    retry: false,
  });
}

// Toggle strategy mode
export function useSetStrategyMode() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (mode: string) => {
      const res = await intelFetch(`/intel/strategy/mode?mode=${mode}`, {
        method: "POST",
      });
      if (!res.ok) throw new Error(`Set mode failed: ${res.status}`);
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["strategy-mode"] });
    },
  });
}

// ── Watchlist Hooks ──

interface WatchlistItem {
  id: string;
  symbol: string;
  exchange_id: string;
  added_at: string;
  notes: string | null;
}

interface SymbolSearchResult {
  symbol: string;
  last_price: number;
  volume_24h: number;
}

// Fetch watchlist
export function useWatchlist(exchangeId: string = "hyperliquid") {
  return useQuery({
    queryKey: ["watchlist", exchangeId],
    queryFn: async () => {
      const res = await intelFetch(`/intel/watchlist?exchange_id=${exchangeId}`);
      if (!res.ok) return [];
      const data = await res.json();
      return (data.watchlist ?? []) as WatchlistItem[];
    },
    refetchInterval: 30_000,
    retry: false,
  });
}

// Add symbol to watchlist
export function useAddToWatchlist() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ symbol, exchangeId = "hyperliquid" }: { symbol: string; exchangeId?: string }) => {
      const res = await intelFetch("/intel/watchlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol, exchange_id: exchangeId }),
      });
      if (!res.ok) throw new Error(`Add failed: ${res.status}`);
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["watchlist"] });
    },
  });
}

// Remove symbol from watchlist
export function useRemoveFromWatchlist() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ symbol, exchangeId = "hyperliquid" }: { symbol: string; exchangeId?: string }) => {
      const res = await intelFetch(`/intel/watchlist/${symbol}?exchange_id=${exchangeId}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error(`Remove failed: ${res.status}`);
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["watchlist"] });
    },
  });
}

// Search available symbols (debounced in component)
export function useSymbolSearch(query: string, exchange: string = "hyperliquid") {
  return useQuery({
    queryKey: ["symbol-search", query, exchange],
    queryFn: async () => {
      if (!query || query.length < 1) return [];
      const res = await intelFetch(`/intel/watchlist/search?q=${encodeURIComponent(query)}&exchange=${exchange}`);
      if (!res.ok) return [];
      const data = await res.json();
      return (data.results ?? []) as SymbolSearchResult[];
    },
    enabled: query.length >= 1,
    retry: false,
    staleTime: 10_000,
  });
}

// Run intelligence for all watchlist symbols
export function useRunAllIntelligence() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ exchange }: { exchange: string }) => {
      const res = await intelFetch(`/intel/intelligence/run-all?exchange=${exchange}`, {
        method: "POST",
      });
      if (!res.ok) throw new Error(`Run-all failed: ${res.status}`);
      return res.json();
    },
    onSuccess: () => {
      const invalidateAll = () => {
        queryClient.invalidateQueries({ queryKey: ["agent-outputs"] });
        queryClient.invalidateQueries({ queryKey: ["module-outputs"] });
        queryClient.invalidateQueries({ queryKey: ["recommendations"] });
        queryClient.invalidateQueries({ queryKey: ["agent-status"] });
      };
      setTimeout(invalidateAll, 15_000);
      setTimeout(invalidateAll, 30_000);
      setTimeout(invalidateAll, 60_000);
      setTimeout(invalidateAll, 120_000);
    },
  });
}

// ── Auto-Trader Hooks ──

interface AutoTraderStatus {
  enabled: boolean;
  conviction_threshold: number;
  equity: number;
  starting_equity: number;
  realized_pnl: number;
  unrealized_pnl: number;
  open_positions: number;
  positions: Record<string, unknown>[];
}

export function useAutoTraderStatus() {
  return useQuery({
    queryKey: ["auto-trader-status"],
    queryFn: async () => {
      const res = await intelFetch("/intel/auto-trader/status");
      if (!res.ok) return null;
      return res.json() as Promise<AutoTraderStatus>;
    },
    refetchInterval: 15_000,
    retry: false,
  });
}

export function useToggleAutoTrader() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      const res = await intelFetch("/intel/auto-trader/toggle", {
        method: "POST",
      });
      if (!res.ok) throw new Error(`Toggle failed: ${res.status}`);
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["auto-trader-status"] });
    },
  });
}

// Fetch agent status from intel service
export function useAgentStatus() {
  return useQuery({
    queryKey: ["agent-status"],
    queryFn: async () => {
      const res = await intelFetch("/intel/agents/status");
      if (!res.ok) return null;
      return res.json();
    },
    refetchInterval: 10_000,
    retry: false,
  });
}
