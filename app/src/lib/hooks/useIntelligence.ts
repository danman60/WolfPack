"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { supabase } from "@/lib/supabase";
import { intelFetch } from "@/lib/intel";

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

      // Deduplicate: keep latest per agent
      const seen = new Map<string, typeof data[0]>();
      for (const row of data ?? []) {
        if (!seen.has(row.agent_name)) {
          seen.set(row.agent_name, row);
        }
      }
      return Object.fromEntries(seen);
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

      // Deduplicate: keep latest per module
      const seen = new Map<string, typeof data[0]>();
      for (const row of data ?? []) {
        if (!seen.has(row.module_name)) {
          seen.set(row.module_name, row);
        }
      }
      return Object.fromEntries(seen);
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
      return data ?? [];
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
      // Refetch after a delay to let the background task complete
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ["agent-outputs"] });
        queryClient.invalidateQueries({ queryKey: ["module-outputs"] });
        queryClient.invalidateQueries({ queryKey: ["recommendations"] });
      }, 10_000);
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

// Fetch portfolio state from intel service
export function usePortfolio() {
  return useQuery({
    queryKey: ["portfolio"],
    queryFn: async () => {
      const res = await fetch("/intel/portfolio");
      if (!res.ok) return null;
      return res.json();
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
      const res = await fetch(`/intel/portfolio/history?limit=${limit}`);
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
      const res = await fetch("/intel/strategy/mode");
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

// Fetch agent status from intel service
export function useAgentStatus() {
  return useQuery({
    queryKey: ["agent-status"],
    queryFn: async () => {
      const res = await fetch("/intel/agents/status");
      if (!res.ok) return null;
      return res.json();
    },
    refetchInterval: 10_000,
    retry: false,
  });
}
