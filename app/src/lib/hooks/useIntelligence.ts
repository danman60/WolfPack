"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { supabase } from "@/lib/supabase";

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
      const res = await fetch(`/intel/intelligence/run?exchange=${exchange}&symbol=${symbol}`, {
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
