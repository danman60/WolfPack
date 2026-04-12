"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { supabase } from "@/lib/supabase";
import { intelFetch } from "@/lib/intel";
import { toast } from "sonner";

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

// Fetch profit report for a time window
export function useProfit(hours: number) {
  return useQuery({
    queryKey: ["profit", hours],
    queryFn: async () => {
      const res = await intelFetch(`/intel/profit?hours=${hours}`);
      if (!res.ok) return null;
      return res.json();
    },
    refetchInterval: 60_000,
    retry: false,
    placeholderData: (prev: unknown) => prev,
  });
}

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
      if (!res.ok) {
        const text = await res.text().catch(() => `HTTP ${res.status}`);
        throw new Error(text.includes("403") ? "Intel service: API key not configured" : `Intel service error: ${res.status}`);
      }
      return res.json();
    },
    onMutate: () => {
      toast.loading("Intelligence cycle started — agents analyzing...", { id: "intel-run", duration: 90_000 });
    },
    onSuccess: () => {
      toast.success("Intelligence cycle running! Agents will report in ~30-60s.", { id: "intel-run" });
      // Poll at increasing intervals
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
      setTimeout(() => {
        invalidateAll();
        toast.success("Intelligence cycle complete — check agent outputs.", { id: "intel-done" });
      }, 60_000);
    },
    onError: (error: Error) => {
      toast.error(`Intelligence failed: ${error.message}`, { id: "intel-run", duration: 8_000 });
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
export function usePortfolio(wallet: string = "paper_perp") {
  return useQuery({
    queryKey: ["portfolio", wallet],
    queryFn: async () => {
      // Try VPS intel service first
      try {
        const res = await intelFetch(`/intel/portfolio?wallet=${wallet}`);
        if (res.ok) {
          const data = await res.json();
          if (data.status === "active") return data;
        }
      } catch {
        // VPS unreachable — fall through to snapshot
      }

      // Fallback: load latest snapshot from Supabase (filtered by wallet)
      // Resolve wallet name → wallet_id first
      let walletId: string | null = null;
      try {
        const { data: walletRow } = await supabase
          .from("wp_wallets")
          .select("id")
          .eq("name", wallet)
          .limit(1);
        const row = walletRow?.[0] as Record<string, unknown> | undefined;
        if (row?.id) walletId = String(row.id);
      } catch { /* proceed without filter */ }

      let query = supabase
        .from("wp_portfolio_snapshots")
        .select("*");
      if (walletId) {
        query = query.eq("wallet_id", walletId);
      }
      const { data, error } = await query
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
export function usePortfolioHistory(
  wallet: string = "paper_perp",
  limit: number = 100
) {
  return useQuery({
    queryKey: ["portfolio-history", wallet, limit],
    queryFn: async () => {
      const res = await intelFetch(
        `/intel/portfolio/history?wallet=${wallet}&limit=${limit}`
      );
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

// ── Position Action Hooks ──

interface PositionAction {
  id: string;
  symbol: string;
  exchange_id: string;
  action: string;
  reason: string | null;
  current_pnl_pct: number | null;
  suggested_stop: number | null;
  suggested_tp: number | null;
  reduce_pct: number | null;
  urgency: string;
  status: string;
  created_at: string;
  acted_at: string | null;
}

export function usePositionActions(status: string = "pending") {
  return useQuery({
    queryKey: ["position-actions", status],
    queryFn: async () => {
      const res = await intelFetch(`/intel/position-actions?status=${status}`);
      if (!res.ok) return [];
      const data = await res.json();
      return (data.actions ?? []) as PositionAction[];
    },
    refetchInterval: 15_000,
    retry: false,
  });
}

export function useApprovePositionAction() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, exchange }: { id: string; exchange: string }) => {
      const res = await intelFetch(`/intel/position-actions/${id}/approve?exchange=${exchange}`, {
        method: "POST",
      });
      if (!res.ok) throw new Error(`Approve failed: ${res.status}`);
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["position-actions"] });
      queryClient.invalidateQueries({ queryKey: ["portfolio"] });
    },
  });
}

export function useDismissPositionAction() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string) => {
      const res = await intelFetch(`/intel/position-actions/${id}/dismiss`, {
        method: "POST",
      });
      if (!res.ok) throw new Error(`Dismiss failed: ${res.status}`);
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["position-actions"] });
    },
  });
}

// ── Trade History Hook ──

interface TradeHistoryItem {
  id: string;
  symbol: string;
  direction: string;
  entry_price: number;
  exit_price: number;
  size_usd: number;
  pnl_usd: number;
  recommendation_id: string | null;
  source: string;
  opened_at: string;
  closed_at: string;
}

export function useTradeHistory(
  wallet: string = "paper_perp",
  limit: number = 50
) {
  return useQuery({
    queryKey: ["trade-history", wallet, limit],
    queryFn: async () => {
      const res = await intelFetch(
        `/intel/portfolio/trades?wallet=${wallet}&limit=${limit}`
      );
      if (!res.ok) return [];
      const data = await res.json();
      return (data.trades ?? []) as TradeHistoryItem[];
    },
    refetchInterval: 30_000,
    retry: false,
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
  yolo_level: number;
  yolo_profile: {
    label: string;
    conviction_threshold: number;
    veto_floor: number;
    max_trades_per_day: number;
    penalty_multiplier: number;
    cooldown_seconds: number;
    max_size_pct: number;
    rejection_cooldown_hours: number;
  };
}

export function useAutoTraderStatus(wallet: string = "paper_perp") {
  return useQuery({
    queryKey: ["auto-trader-status", wallet],
    queryFn: async () => {
      const res = await intelFetch(`/intel/auto-trader/status?wallet=${wallet}`);
      if (!res.ok) return null;
      return res.json() as Promise<AutoTraderStatus>;
    },
    refetchInterval: 15_000,
    retry: false,
  });
}

export function useToggleAutoTrader(wallet: string = "paper_perp") {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      const res = await intelFetch(
        `/intel/auto-trader/toggle?wallet=${wallet}`,
        {
          method: "POST",
        }
      );
      if (!res.ok) throw new Error(`Toggle failed: ${res.status}`);
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["auto-trader-status"] });
    },
  });
}

// Fetch auto-trader trades
interface AutoTraderTrade {
  id: string;
  recommendation_id: string | null;
  symbol: string;
  direction: string;
  entry_price: number;
  size_usd: number;
  size_pct: number;
  conviction: number;
  status: string;
  opened_at: string;
}

export function useAutoTraderTrades(
  wallet: string = "paper_perp",
  limit: number = 50
) {
  return useQuery({
    queryKey: ["auto-trader-trades", wallet, limit],
    queryFn: async () => {
      const res = await intelFetch(
        `/intel/auto-trader/trades?wallet=${wallet}&limit=${limit}`
      );
      if (!res.ok) return [];
      const data = await res.json();
      return (data.trades ?? []) as AutoTraderTrade[];
    },
    refetchInterval: 15_000,
    retry: false,
  });
}

// Configure auto-trader (equity + conviction threshold)
export function useConfigureAutoTrader(wallet: string = "paper_perp") {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ equity, conviction_threshold }: { equity?: number; conviction_threshold?: number }) => {
      const res = await intelFetch(`/intel/auto-trader/config?wallet=${wallet}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ equity, conviction_threshold }),
      });
      if (!res.ok) throw new Error(`Config failed: ${res.status}`);
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["auto-trader-status"] });
      queryClient.invalidateQueries({ queryKey: ["auto-trader-trades"] });
    },
  });
}

// Set YOLO meter level
export function useSetYoloLevel(wallet: string = "paper_perp") {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (level: number) => {
      const res = await intelFetch(
        `/intel/auto-trader/yolo?level=${level}&wallet=${wallet}`,
        { method: "POST" }
      );
      if (!res.ok) throw new Error(`YOLO level update failed: ${res.status}`);
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["auto-trader-status"] });
    },
  });
}

// Fetch list of all 4 wallets with status and equity
export function useWallets() {
  return useQuery({
    queryKey: ["wallets"],
    queryFn: async () => {
      const res = await intelFetch("/intel/wallets");
      if (!res.ok) return { wallets: [] };
      return res.json();
    },
    refetchInterval: 30_000,
    retry: false,
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

// ── Evolution / Multi-Wallet Hooks ──

export interface WalletSummary {
  name: string;
  display_name: string;
  description: string;
  version: number;
  status: string;
  starting_equity: number;
  config: Record<string, unknown>;
  equity: number;
  realized_pnl: number;
  unrealized_pnl: number;
  open_positions: number;
  yolo_level: number;
  trade_count: number;
  win_rate: number;
  total_pnl: number;
  // Phase 2 evolution metadata
  generation?: number;
  parent_wallet_id?: string | null;
}

// Supplementary wallet metadata pulled directly from Supabase wp_wallets
export interface WalletMeta {
  id: string;
  name: string;
  display_name: string | null;
  created_at: string | null;
  parent_wallet_id: string | null;
  generation: number;
}

// Fetch wallet metadata (created_at, parent/generation) directly from Supabase,
// since /wallets/summary doesn't expose created_at.
export function useWalletMeta() {
  return useQuery({
    queryKey: ["wallet-meta"],
    queryFn: async () => {
      const { data, error } = await supabase
        .from("wp_wallets")
        .select(
          "id, name, display_name, created_at, parent_wallet_id, generation"
        );
      if (error) throw error;
      const rows = (data ?? []) as unknown as Array<{
        id: string;
        name: string;
        display_name: string | null;
        created_at: string | null;
        parent_wallet_id: string | null;
        generation: number | null;
      }>;
      const byId: Record<string, WalletMeta> = {};
      const byName: Record<string, WalletMeta> = {};
      for (const r of rows) {
        const meta: WalletMeta = {
          id: r.id,
          name: r.name,
          display_name: r.display_name,
          created_at: r.created_at,
          parent_wallet_id: r.parent_wallet_id,
          generation: r.generation ?? 0,
        };
        byId[r.id] = meta;
        byName[r.name] = meta;
      }
      return { byId, byName };
    },
    refetchInterval: 5 * 60_000,
    retry: false,
    staleTime: 60_000,
  });
}

// Fetch all wallet summaries for evolution dashboard
export function useWalletsSummary() {
  return useQuery({
    queryKey: ["wallets-summary"],
    queryFn: async () => {
      const res = await intelFetch("/intel/wallets/summary");
      if (!res.ok) return [];
      return res.json() as Promise<WalletSummary[]>;
    },
    refetchInterval: 15_000,
    retry: false,
  });
}

// ── Wallet Management Mutations ──

export function useCreateWallet() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: {
      name: string;
      display_name: string;
      description?: string;
      starting_equity?: number;
      config?: Record<string, unknown>;
      clone_from?: string;
    }) => {
      const res = await intelFetch("/intel/wallets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(await res.text());
      return res.json();
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["wallets-summary"] });
      qc.invalidateQueries({ queryKey: ["wallets"] });
    },
  });
}

export function useUpdateWalletConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      name,
      config,
    }: {
      name: string;
      config: Record<string, unknown>;
    }) => {
      const res = await intelFetch(`/intel/wallets/${name}/config`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      });
      if (!res.ok) throw new Error(await res.text());
      return res.json();
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["wallets-summary"] });
      qc.invalidateQueries({ queryKey: ["wallets"] });
    },
  });
}

export function useCloneWallet() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      name,
      new_name,
      new_display_name,
      config_mutations,
    }: {
      name: string;
      new_name: string;
      new_display_name: string;
      config_mutations?: Record<string, unknown>;
    }) => {
      const res = await intelFetch(`/intel/wallets/${name}/clone`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          new_name,
          new_display_name,
          config_mutations: config_mutations || {},
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      return res.json();
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["wallets-summary"] });
      qc.invalidateQueries({ queryKey: ["wallets"] });
    },
  });
}

export function usePauseResumeWallet() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      name,
      action,
    }: {
      name: string;
      action: "pause" | "resume";
    }) => {
      const res = await intelFetch(`/intel/wallets/${name}/${action}`, {
        method: "POST",
      });
      if (!res.ok) throw new Error(await res.text());
      return res.json();
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["wallets-summary"] });
      qc.invalidateQueries({ queryKey: ["wallets"] });
    },
  });
}

// Fetch time-series metrics for a specific wallet
export function useWalletMetrics(wallet: string, hours: number = 24) {
  return useQuery({
    queryKey: ["wallet-metrics", wallet, hours],
    queryFn: async () => {
      const res = await intelFetch(
        `/intel/wallets/${wallet}/metrics?hours=${hours}`
      );
      if (!res.ok) return null;
      return res.json();
    },
    refetchInterval: 30_000,
    retry: false,
  });
}
