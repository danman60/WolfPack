import { useQuery } from "@tanstack/react-query";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface SubgraphToken {
  id: string;
  symbol: string;
  name: string;
  decimals: string;
}

export interface SubgraphPool {
  id: string;
  feeTier: string;
  totalValueLockedUSD: string;
  volumeUSD: string;
  token0: SubgraphToken;
  token1: SubgraphToken;
}

export interface SubgraphPoolDetail extends SubgraphPool {
  sqrtPrice: string;
  tick: string;
  liquidity: string;
  poolDayData: {
    date: number;
    volumeUSD: string;
    feesUSD: string;
    tvlUSD: string;
  }[];
}

export interface SubgraphPosition {
  id: string;
  pool: {
    id: string;
    token0: SubgraphToken;
    token1: SubgraphToken;
    feeTier: string;
  };
  liquidity: string;
  depositedToken0: string;
  depositedToken1: string;
  withdrawnToken0: string;
  withdrawnToken1: string;
  collectedFeesToken0: string;
  collectedFeesToken1: string;
  tickLower: { tickIdx: string };
  tickUpper: { tickIdx: string };
}

// ---------------------------------------------------------------------------
// Pool data fetcher via VPS proxy (no API key needed on frontend)
// ---------------------------------------------------------------------------

async function fetchFromIntel<T>(path: string): Promise<T> {
  const res = await fetch(`/intel${path}`);
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || `Failed to fetch: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

export function useTopPools(count = 50) {
  return useQuery<SubgraphPool[]>({
    queryKey: ["uniswap-top-pools", count],
    queryFn: async () => {
      const data = await fetchFromIntel<{ pools: SubgraphPool[] }>(`/pools/top?first=${count}`);
      return data.pools;
    },
    staleTime: 60_000,
    refetchInterval: 60_000,
  });
}

export function usePoolDetail(poolId: string | undefined) {
  return useQuery<SubgraphPoolDetail | null>({
    queryKey: ["uniswap-pool-detail", poolId],
    queryFn: async () => {
      if (!poolId) return null;
      const data = await fetchFromIntel<{ pool: SubgraphPoolDetail | null }>(`/pools/detail?pool_id=${poolId}`);
      return data.pool;
    },
    enabled: !!poolId,
    staleTime: 30_000,
  });
}

export function useUserPositions(address: string | undefined) {
  return useQuery<SubgraphPosition[]>({
    queryKey: ["uniswap-positions", address],
    queryFn: async () => {
      if (!address) return [];
      const data = await fetchFromIntel<{ positions: SubgraphPosition[] }>(`/pools/positions?owner=${address}&first=50`);
      return data.positions;
    },
    enabled: !!address,
    staleTime: 30_000,
  });
}

// ---------------------------------------------------------------------------
// Pool Screening (scored via intel service)
// ---------------------------------------------------------------------------

interface ScreenedPool {
  pool_id: string;
  pair: string;
  fee_tier: string;
  tvl_usd: number;
  volume_usd_24h: number;
  score: number;
  recommendation: "Enter" | "Consider" | "Caution" | "Avoid";
  breakdown: Record<string, number>;
}

export function usePoolScreening(limit = 20) {
  return useQuery<ScreenedPool[]>({
    queryKey: ["pool-screening", limit],
    queryFn: async () => {
      const res = await fetch(`/intel/pools/screen?limit=${limit}`);
      if (!res.ok) return [];
      const data = await res.json();
      return (data.pools ?? []) as ScreenedPool[];
    },
    staleTime: 120_000,
    refetchInterval: 120_000,
    retry: false,
  });
}

// ---------------------------------------------------------------------------
// LP Autobot Status
// ---------------------------------------------------------------------------

interface LPPositionDetail {
  pair: string;
  pool: string;
  status: string;
  liquidity_usd: number;
  fees_earned: number;
  il_pct: number;
  il_usd: number;
  net_pnl: number;
  in_range: boolean;
}

interface LPStatus {
  enabled: boolean;
  paper_mode: boolean;
  equity: number;
  positions: number;
  max_positions: number;
  total_fees: number;
  total_il: number;
  realized_pnl: number;
  watched_pools: number;
  active_il_hedges: number;
  total_hedge_usd: number;
  scanner_candidates: number;
  top_pools: { name: string; apr: number; score: number }[];
  position_details: LPPositionDetail[];
}

export function useLPStatus(wallet: string = "paper_lp") {
  return useQuery<LPStatus | null>({
    queryKey: ["lp-status", wallet],
    queryFn: async () => {
      const res = await fetch(`/intel/lp/status?wallet=${wallet}`);
      if (!res.ok) return null;
      return res.json() as Promise<LPStatus>;
    },
    refetchInterval: 30_000,
    retry: false,
  });
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Fee tier mapping: raw value to human-readable string */
export const FEE_TIER_MAP: Record<string, string> = {
  "100": "0.01%",
  "500": "0.05%",
  "3000": "0.3%",
  "10000": "1%",
};

export function feeTierLabel(raw: string): string {
  return FEE_TIER_MAP[raw] ?? `${(Number(raw) / 10000).toFixed(2)}%`;
}

/** Calculate fee APR from daily volume, TVL, and fee tier.
 *
 * IMPORTANT: Pass daily volume, NOT all-time cumulative volumeUSD.
 * For pool listings without poolDayData, pass 0 to get 0 APR (unknown).
 */
export function calcFeeApr(
  dailyVolumeUSD: string | number,
  tvlUSD: string | number,
  feeTier: string | number
): number {
  const vol = Number(dailyVolumeUSD);
  const tvl = Number(tvlUSD);
  const fee = Number(feeTier) / 1_000_000; // 3000 -> 0.003
  if (tvl <= 0 || vol <= 0 || fee <= 0) return 0;
  return (vol * fee * 365) / tvl;
}

/** Format USD value */
export function fmtUsd(n: number | string): string {
  const v = Number(n);
  if (!v || v <= 0) return "--";
  if (v >= 1_000_000_000) return `$${(v / 1_000_000_000).toFixed(2)}B`;
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(2)}M`;
  if (v >= 1_000) return `$${(v / 1_000).toFixed(1)}K`;
  return `$${v.toFixed(2)}`;
}

/** Format percentage */
export function fmtPct(n: number): string {
  return `${(n * 100).toFixed(2)}%`;
}
