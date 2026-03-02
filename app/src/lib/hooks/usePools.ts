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
// Constants
// ---------------------------------------------------------------------------

const SUBGRAPH_URL =
  "https://gateway.thegraph.com/api/subgraphs/id/5zvR82QoaXYFyDEKLZ9t6v9adgnptxYpKpSbxtgVENFV";

// Fallback if the gateway requires an API key
const SUBGRAPH_FALLBACK =
  "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3";

// ---------------------------------------------------------------------------
// Subgraph fetcher with automatic fallback
// ---------------------------------------------------------------------------

async function subgraphFetch<T>(
  query: string,
  variables: Record<string, unknown>
): Promise<T> {
  // Try primary endpoint first
  for (const url of [SUBGRAPH_URL, SUBGRAPH_FALLBACK]) {
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, variables }),
      });
      if (!res.ok) continue;
      const json = await res.json();
      if (json.errors) continue;
      return json.data as T;
    } catch {
      continue;
    }
  }
  throw new Error("Failed to fetch from Uniswap V3 subgraph");
}

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------

const TOP_POOLS_QUERY = `
  query TopPools($first: Int!) {
    pools(
      first: $first
      orderBy: totalValueLockedUSD
      orderDirection: desc
      where: { volumeUSD_gt: "1000000" }
    ) {
      id
      feeTier
      totalValueLockedUSD
      volumeUSD
      token0 { id symbol name decimals }
      token1 { id symbol name decimals }
    }
  }
`;

const POOL_DETAIL_QUERY = `
  query PoolDetail($id: ID!) {
    pool(id: $id) {
      id
      feeTier
      totalValueLockedUSD
      volumeUSD
      sqrtPrice
      tick
      liquidity
      token0 { id symbol name decimals }
      token1 { id symbol name decimals }
      poolDayData(first: 30, orderBy: date, orderDirection: desc) {
        date
        volumeUSD
        feesUSD
        tvlUSD
      }
    }
  }
`;

const POSITIONS_QUERY = `
  query Positions($owner: Bytes!, $first: Int!) {
    positions(
      where: { owner: $owner }
      first: $first
      orderBy: liquidity
      orderDirection: desc
    ) {
      id
      pool {
        id
        token0 { id symbol name decimals }
        token1 { id symbol name decimals }
        feeTier
      }
      liquidity
      depositedToken0
      depositedToken1
      withdrawnToken0
      withdrawnToken1
      collectedFeesToken0
      collectedFeesToken1
      tickLower { tickIdx }
      tickUpper { tickIdx }
    }
  }
`;

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

export function useTopPools(count = 50) {
  return useQuery<SubgraphPool[]>({
    queryKey: ["uniswap-top-pools", count],
    queryFn: async () => {
      const data = await subgraphFetch<{ pools: SubgraphPool[] }>(
        TOP_POOLS_QUERY,
        { first: count }
      );
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
      const data = await subgraphFetch<{ pool: SubgraphPoolDetail | null }>(
        POOL_DETAIL_QUERY,
        { id: poolId.toLowerCase() }
      );
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
      const data = await subgraphFetch<{ positions: SubgraphPosition[] }>(
        POSITIONS_QUERY,
        { owner: address.toLowerCase(), first: 50 }
      );
      return data.positions;
    },
    enabled: !!address,
    staleTime: 30_000,
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

/** Calculate fee APR from volume, TVL, and fee tier */
export function calcFeeApr(
  volumeUSD: string | number,
  tvlUSD: string | number,
  feeTier: string | number
): number {
  const vol = Number(volumeUSD);
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
