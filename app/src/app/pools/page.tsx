"use client";

import { useState, useMemo, useCallback } from "react";
import { useAccount, useConnect, useDisconnect } from "wagmi";
// useConnect and useDisconnect are used inside WalletButton component
import {
  useTopPools,
  usePoolDetail,
  useUserPositions,
  feeTierLabel,
  calcFeeApr,
  fmtUsd,
  fmtPct,
  type SubgraphPool,
} from "@/lib/hooks/usePools";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const FEE_FILTERS = [
  { label: "All", value: "all" },
  { label: "0.01%", value: "100" },
  { label: "0.05%", value: "500" },
  { label: "0.3%", value: "3000" },
  { label: "1%", value: "10000" },
] as const;

type SortKey = "pair" | "fee" | "tvl" | "volume" | "apr";
type SortDir = "asc" | "desc";

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function PoolsPage() {
  const { address, isConnected } = useAccount();

  // Pool data
  const { data: pools, isLoading: poolsLoading, error: poolsError } = useTopPools(50);
  const { data: positions } = useUserPositions(isConnected ? address : undefined);

  // Filters & sort
  const [feeFilter, setFeeFilter] = useState("all");
  const [sortKey, setSortKey] = useState<SortKey>("tvl");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [expandedPool, setExpandedPool] = useState<string | null>(null);

  const handleSort = useCallback(
    (key: SortKey) => {
      if (sortKey === key) {
        setSortDir((d) => (d === "asc" ? "desc" : "asc"));
      } else {
        setSortKey(key);
        setSortDir(key === "pair" ? "asc" : "desc");
      }
    },
    [sortKey]
  );

  const sortIndicator = useCallback(
    (key: SortKey) => {
      if (sortKey !== key) return "";
      return sortDir === "asc" ? " ▲" : " ▼";
    },
    [sortKey, sortDir]
  );

  // Filtered + sorted pools
  const displayedPools = useMemo(() => {
    if (!pools) return [];
    let arr = [...pools];

    // Filter by fee tier
    if (feeFilter !== "all") {
      arr = arr.filter((p) => p.feeTier === feeFilter);
    }

    // Sort
    const dir = sortDir === "asc" ? 1 : -1;
    arr.sort((a, b) => {
      switch (sortKey) {
        case "pair":
          return (
            `${a.token0.symbol}/${a.token1.symbol}`.localeCompare(
              `${b.token0.symbol}/${b.token1.symbol}`
            ) * dir
          );
        case "fee":
          return (Number(a.feeTier) - Number(b.feeTier)) * dir;
        case "tvl":
          return (Number(a.totalValueLockedUSD) - Number(b.totalValueLockedUSD)) * dir;
        case "volume":
          return (Number(a.volumeUSD) - Number(b.volumeUSD)) * dir;
        case "apr":
          return (
            (calcFeeApr(a.volumeUSD, a.totalValueLockedUSD, a.feeTier) -
              calcFeeApr(b.volumeUSD, b.totalValueLockedUSD, b.feeTier)) *
            dir
          );
        default:
          return 0;
      }
    });

    return arr;
  }, [pools, feeFilter, sortKey, sortDir]);

  // Position summary stats
  const positionCount = positions?.length ?? 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="border-b border-[var(--border)] pb-4 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">LP Pool Manager</h1>
          <p className="text-gray-400 text-sm mt-1">
            Browse Uniswap V3 pools and manage liquidity positions
          </p>
        </div>
        <WalletButton isConnected={isConnected} address={address} />
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-surface-elevated border border-[var(--border)] rounded-lg p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wider">Active Positions</p>
          <p className="text-2xl font-bold text-[var(--wolf-purple)] mt-1">
            {isConnected ? positionCount : "--"}
          </p>
        </div>
        <div className="bg-surface-elevated border border-[var(--border)] rounded-lg p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wider">Top Pools Loaded</p>
          <p className="text-2xl font-bold text-[var(--wolf-blue)] mt-1">
            {pools?.length ?? "--"}
          </p>
        </div>
        <div className="bg-surface-elevated border border-[var(--border)] rounded-lg p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wider">Filtered Results</p>
          <p className="text-2xl font-bold text-[var(--wolf-emerald)] mt-1">
            {displayedPools.length}
          </p>
        </div>
      </div>

      {/* User Positions (wallet connected) */}
      {isConnected && positions && positions.length > 0 && (
        <div className="bg-surface-elevated border border-[var(--border)] rounded-lg p-6">
          <h2 className="text-lg font-semibold text-white mb-4">Your Positions</h2>
          <div className="space-y-3">
            {positions.map((pos) => {
              const pair = `${pos.pool.token0.symbol}/${pos.pool.token1.symbol}`;
              const hasLiquidity = Number(pos.liquidity) > 0;
              return (
                <div
                  key={pos.id}
                  className="flex items-center justify-between py-3 px-4 border border-[var(--border)] rounded-lg"
                >
                  <div className="flex items-center gap-4">
                    <div
                      className={`w-2 h-2 rounded-full ${
                        hasLiquidity ? "bg-[var(--wolf-emerald)]" : "bg-gray-600"
                      }`}
                    />
                    <div>
                      <span className="text-sm text-white font-semibold font-mono">{pair}</span>
                      <span className="ml-2 text-xs text-gray-400">
                        {feeTierLabel(pos.pool.feeTier)}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-6 text-right">
                    <div>
                      <div className="text-[10px] text-gray-500 uppercase">Tick Range</div>
                      <div className="text-xs text-gray-300 font-mono">
                        {pos.tickLower.tickIdx} - {pos.tickUpper.tickIdx}
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] text-gray-500 uppercase">Status</div>
                      <div
                        className={`text-xs font-semibold ${
                          hasLiquidity ? "text-[var(--wolf-emerald)]" : "text-gray-500"
                        }`}
                      >
                        {hasLiquidity ? "Active" : "Closed"}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Wallet prompt when not connected */}
      {!isConnected && (
        <div className="bg-surface-elevated border border-[var(--border)] rounded-lg p-6">
          <h2 className="text-lg font-semibold text-white mb-2">Your Positions</h2>
          <div className="text-center py-8 text-gray-500 text-sm">
            Connect your wallet to view your Uniswap V3 LP positions.
          </div>
        </div>
      )}

      {/* Pool Browser */}
      <div className="bg-surface-elevated border border-[var(--border)] rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-white">Pool Browser</h2>

          {/* Fee tier filter */}
          <div className="flex items-center gap-1">
            {FEE_FILTERS.map((f) => (
              <button
                key={f.value}
                onClick={() => setFeeFilter(f.value)}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                  feeFilter === f.value
                    ? "bg-[var(--wolf-blue)] text-white"
                    : "bg-[var(--surface)] text-gray-400 hover:text-white hover:bg-[var(--surface-hover)]"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        {/* Loading state */}
        {poolsLoading && (
          <div className="space-y-3">
            {Array.from({ length: 8 }).map((_, i) => (
              <div
                key={i}
                className="h-12 bg-[var(--surface)] rounded-md animate-pulse"
              />
            ))}
          </div>
        )}

        {/* Error state */}
        {poolsError && (
          <div className="text-center py-8 text-[var(--wolf-red)] text-sm">
            Failed to load pools from subgraph. The Graph endpoint may require an API key.
            <br />
            <span className="text-gray-500 text-xs mt-1 block">
              {(poolsError as Error).message}
            </span>
          </div>
        )}

        {/* Pool table */}
        {!poolsLoading && !poolsError && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[700px] text-sm">
              <thead>
                <tr className="border-b border-[var(--border)]">
                  <SortHeader
                    label="Pair"
                    sortKey="pair"
                    onSort={handleSort}
                    indicator={sortIndicator("pair")}
                  />
                  <SortHeader
                    label="Fee Tier"
                    sortKey="fee"
                    onSort={handleSort}
                    indicator={sortIndicator("fee")}
                    align="right"
                  />
                  <SortHeader
                    label="TVL"
                    sortKey="tvl"
                    onSort={handleSort}
                    indicator={sortIndicator("tvl")}
                    align="right"
                  />
                  <SortHeader
                    label="Volume (All-time)"
                    sortKey="volume"
                    onSort={handleSort}
                    indicator={sortIndicator("volume")}
                    align="right"
                  />
                  <SortHeader
                    label="Fee APR (est)"
                    sortKey="apr"
                    onSort={handleSort}
                    indicator={sortIndicator("apr")}
                    align="right"
                  />
                </tr>
              </thead>
              <tbody>
                {displayedPools.length === 0 && (
                  <tr>
                    <td colSpan={5} className="text-center py-12 text-gray-500">
                      No pools found for this filter.
                    </td>
                  </tr>
                )}
                {displayedPools.map((pool) => (
                  <PoolRow
                    key={pool.id}
                    pool={pool}
                    isExpanded={expandedPool === pool.id}
                    onToggle={() =>
                      setExpandedPool((prev) => (prev === pool.id ? null : pool.id))
                    }
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function WalletButton({
  isConnected,
  address,
}: {
  isConnected: boolean;
  address: string | undefined;
}) {
  const { connectors, connect } = useConnect();
  const { disconnect } = useDisconnect();

  if (isConnected && address) {
    return (
      <div className="flex items-center gap-3">
        <span className="text-xs text-gray-400 font-mono">
          {address.slice(0, 6)}...{address.slice(-4)}
        </span>
        <button
          onClick={() => disconnect()}
          className="px-3 py-1.5 rounded-md text-xs font-medium bg-[var(--wolf-red)]/20 text-[var(--wolf-red)] hover:bg-[var(--wolf-red)]/30 transition"
        >
          Disconnect
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      {connectors.slice(0, 3).map((connector) => (
        <button
          key={connector.uid}
          onClick={() => connect({ connector })}
          className="px-3 py-1.5 rounded-md text-xs font-medium bg-[var(--wolf-blue)]/20 text-[var(--wolf-blue)] hover:bg-[var(--wolf-blue)]/30 transition"
        >
          {connector.name === "Injected" ? "Browser Wallet" : connector.name}
        </button>
      ))}
    </div>
  );
}

function SortHeader({
  label,
  sortKey,
  onSort,
  indicator,
  align = "left",
}: {
  label: string;
  sortKey: SortKey;
  onSort: (key: SortKey) => void;
  indicator: string;
  align?: "left" | "right";
}) {
  return (
    <th
      className={`px-3 py-3 text-xs text-gray-500 uppercase tracking-wider font-medium cursor-pointer hover:text-white transition-colors ${
        align === "right" ? "text-right" : "text-left"
      }`}
      onClick={() => onSort(sortKey)}
    >
      {label}
      {indicator && <span className="text-[var(--wolf-blue)] ml-1">{indicator}</span>}
    </th>
  );
}

function PoolRow({
  pool,
  isExpanded,
  onToggle,
}: {
  pool: SubgraphPool;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const apr = calcFeeApr(pool.volumeUSD, pool.totalValueLockedUSD, pool.feeTier);
  const pair = `${pool.token0.symbol}/${pool.token1.symbol}`;

  return (
    <>
      <tr
        onClick={onToggle}
        className="border-b border-[var(--border)] hover:bg-[var(--surface-hover)] cursor-pointer transition-colors"
      >
        <td className="px-3 py-3">
          <span className="text-white font-semibold font-mono">{pair}</span>
        </td>
        <td className="px-3 py-3 text-right">
          <span className="px-2 py-0.5 rounded text-xs font-medium bg-[var(--wolf-purple)]/20 text-[var(--wolf-purple)]">
            {feeTierLabel(pool.feeTier)}
          </span>
        </td>
        <td className="px-3 py-3 text-right text-gray-300">
          {fmtUsd(pool.totalValueLockedUSD)}
        </td>
        <td className="px-3 py-3 text-right text-gray-300">{fmtUsd(pool.volumeUSD)}</td>
        <td className="px-3 py-3 text-right">
          <span
            className={
              apr > 0.5
                ? "text-[var(--wolf-emerald)] font-semibold"
                : apr > 0.1
                ? "text-[var(--wolf-amber)]"
                : "text-gray-400"
            }
          >
            {apr > 0 ? fmtPct(apr) : "--"}
          </span>
        </td>
      </tr>
      {isExpanded && <PoolDetailRow poolId={pool.id} pool={pool} />}
    </>
  );
}

function PoolDetailRow({
  poolId,
  pool,
}: {
  poolId: string;
  pool: SubgraphPool;
}) {
  const { data: detail, isLoading } = usePoolDetail(poolId);

  return (
    <tr>
      <td colSpan={5} className="px-3 py-4 bg-[var(--surface)]">
        {isLoading && (
          <div className="text-center py-4 text-gray-500 text-sm">Loading pool details...</div>
        )}
        {detail && <APRCalculator pool={pool} detail={detail} />}
        {!isLoading && !detail && (
          <div className="text-center py-4 text-gray-500 text-sm">
            Could not load pool details.
          </div>
        )}
      </td>
    </tr>
  );
}

// ---------------------------------------------------------------------------
// Inline APR Calculator (ported from PoolParty)
// ---------------------------------------------------------------------------

function APRCalculator({
  pool,
  detail,
}: {
  pool: SubgraphPool;
  detail: { totalValueLockedUSD: string; volumeUSD: string; poolDayData?: { date: number; volumeUSD: string; feesUSD: string; tvlUSD: string }[] };
}) {
  const [sharePercent, setSharePercent] = useState(1);

  const tvl = Number(detail.totalValueLockedUSD);

  // Use recent 7d average daily volume if we have poolDayData, else fallback
  const recentDays = detail.poolDayData?.slice(0, 7) ?? [];
  const avgDailyVol =
    recentDays.length > 0
      ? recentDays.reduce((s, d) => s + Number(d.volumeUSD), 0) / recentDays.length
      : 0;

  const feeRate = Number(pool.feeTier) / 1_000_000;

  const poolApr = tvl > 0 && avgDailyVol > 0 ? (avgDailyVol * feeRate * 365) / tvl : 0;
  const userApr = poolApr * (sharePercent / 100);
  const userApy = Math.pow(1 + userApr / 365, 365) - 1;
  const dailyFeesUser = avgDailyVol * feeRate * (sharePercent / 100);

  return (
    <div className="space-y-4">
      <div className="text-sm font-semibold text-white">
        APR Calculator &mdash; {pool.token0.symbol}/{pool.token1.symbol}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MiniStat label="TVL" value={fmtUsd(tvl)} />
        <MiniStat label="Avg Daily Vol (7d)" value={fmtUsd(avgDailyVol)} />
        <MiniStat label="Fee Tier" value={feeTierLabel(pool.feeTier)} />
        <div>
          <label className="block text-[10px] text-gray-500 uppercase mb-1">
            Your Share (%)
          </label>
          <input
            type="number"
            min={0}
            max={100}
            step={0.1}
            value={sharePercent}
            onChange={(e) => setSharePercent(Number(e.target.value))}
            className="w-full bg-[var(--surface-elevated)] border border-[var(--border)] rounded px-2 py-1.5 text-sm text-white"
          />
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MiniStat label="Pool Fee APR" value={fmtPct(poolApr)} accent="emerald" />
        <MiniStat label="Your APR" value={fmtPct(userApr)} accent="blue" />
        <MiniStat label="Your APY (compound)" value={fmtPct(userApy)} accent="purple" />
        <MiniStat
          label="Est. Daily Fees (you)"
          value={dailyFeesUser > 0 ? `$${dailyFeesUser.toFixed(2)}` : "--"}
          accent="amber"
        />
      </div>

      {recentDays.length > 0 && (
        <div className="text-xs text-gray-500">
          Based on {recentDays.length}-day average. Actual returns depend on price range and
          position utilization.
        </div>
      )}
    </div>
  );
}

function MiniStat({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: string;
}) {
  const colorMap: Record<string, string> = {
    emerald: "text-[var(--wolf-emerald)]",
    blue: "text-[var(--wolf-blue)]",
    purple: "text-[var(--wolf-purple)]",
    amber: "text-[var(--wolf-amber)]",
  };

  return (
    <div className="bg-[var(--surface-elevated)] border border-[var(--border)] rounded-lg p-3">
      <div className="text-[10px] text-gray-500 uppercase">{label}</div>
      <div className={`text-sm font-semibold mt-0.5 ${accent ? colorMap[accent] : "text-white"}`}>
        {value}
      </div>
    </div>
  );
}
