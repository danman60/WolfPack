"use client";

import { useState, useMemo, useCallback } from "react";
import { useAccount, useConnect, useDisconnect } from "wagmi";
import {
  useTopPools,
  usePoolDetail,
  useUserPositions,
  feeTierLabel,
  calcFeeApr,
  fmtUsd,
  fmtPct,
  type SubgraphPool,
  type SubgraphPosition,
} from "@/lib/hooks/usePools";
import {
  useCollectFees,
  useRemoveLiquidity,
  useMintPosition,
  useApproveToken,
  toTokenUnits,
  roundTick,
  priceToTick,
} from "@/lib/hooks/useLPManagement";

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
    <div className="space-y-7">
      {/* Header */}
      <div className="page-header flex items-center justify-between">
        <div>
          <h1 className="page-title">LP Pool Manager</h1>
          <p className="page-subtitle">
            Browse Uniswap V3 pools and manage liquidity positions
          </p>
        </div>
        <WalletButton isConnected={isConnected} address={address} />
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="wolf-card stat-card stat-card-purple p-5">
          <p className="text-[11px] text-gray-500 uppercase tracking-wider font-medium">Active Positions</p>
          <p className="text-2xl font-bold text-[var(--wolf-purple)] mt-2 tracking-tight">
            {isConnected ? positionCount : "--"}
          </p>
        </div>
        <div className="wolf-card stat-card stat-card-blue p-5">
          <p className="text-[11px] text-gray-500 uppercase tracking-wider font-medium">Top Pools Loaded</p>
          <p className="text-2xl font-bold text-[var(--wolf-blue)] mt-2 tracking-tight">
            {pools?.length ?? "--"}
          </p>
        </div>
        <div className="wolf-card stat-card stat-card-emerald p-5">
          <p className="text-[11px] text-gray-500 uppercase tracking-wider font-medium">Filtered Results</p>
          <p className="text-2xl font-bold text-[var(--wolf-emerald)] mt-2 tracking-tight">
            {displayedPools.length}
          </p>
        </div>
      </div>

      {/* User Positions (wallet connected) */}
      {isConnected && positions && positions.length > 0 && (
        <div className="wolf-card p-6">
          <div className="flex items-center gap-2 mb-5">
            <div className="w-1 h-4 rounded-full bg-[var(--wolf-purple)]" />
            <h2 className="section-title">Your Positions</h2>
          </div>
          <div className="space-y-3">
            {positions.map((pos) => (
              <PositionCard key={pos.id} position={pos} />
            ))}
          </div>
        </div>
      )}

      {/* Wallet prompt when not connected */}
      {!isConnected && (
        <div className="wolf-card p-6">
          <h2 className="section-title mb-2">Your Positions</h2>
          <div className="empty-state">
            Connect your wallet to view your Uniswap V3 LP positions.
          </div>
        </div>
      )}

      {/* Pool Browser */}
      <div className="wolf-card p-6">
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2">
            <div className="w-1 h-4 rounded-full bg-[var(--wolf-blue)]" />
            <h2 className="section-title">Pool Browser</h2>
          </div>

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
          <div className="text-center py-10 space-y-3">
            <div className="text-[var(--wolf-amber)] text-sm font-semibold">Subgraph API Key Required</div>
            <p className="text-gray-400 text-sm max-w-md mx-auto">
              Uniswap V3 pool data requires a free API key from The Graph.
            </p>
            <div className="bg-[var(--surface)] border border-[var(--border)] rounded-lg p-4 max-w-sm mx-auto text-left space-y-2">
              <p className="text-xs text-gray-300 font-semibold">Setup (2 minutes):</p>
              <ol className="text-xs text-gray-400 space-y-1 list-decimal list-inside">
                <li>Go to <a href="https://thegraph.com/studio/" target="_blank" rel="noopener" className="text-[var(--wolf-cyan)] underline">thegraph.com/studio</a></li>
                <li>Create a free account &amp; API key</li>
                <li>Add to <code className="text-gray-300">.env.local</code>:</li>
              </ol>
              <code className="block text-xs text-[var(--wolf-emerald)] bg-black/30 rounded p-2 font-mono">
                NEXT_PUBLIC_SUBGRAPH_API_KEY=your_key
              </code>
            </div>
            <p className="text-gray-600 text-xs">
              {(poolsError as Error).message}
            </p>
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
  // Pool listing only has all-time cumulative volume — APR requires daily volume from poolDayData
  const apr = 0; // Accurate APR shown in expanded detail view
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

function PositionCard({ position }: { position: SubgraphPosition }) {
  const pair = `${position.pool.token0.symbol}/${position.pool.token1.symbol}`;
  const hasLiquidity = Number(position.liquidity) > 0;
  const tokenId = BigInt(position.id);
  const [expanded, setExpanded] = useState(false);

  const collectFees = useCollectFees();
  const removeLiq = useRemoveLiquidity();

  const feesToken0 = Number(position.collectedFeesToken0);
  const feesToken1 = Number(position.collectedFeesToken1);

  return (
    <div className="border border-[var(--border)] rounded-lg overflow-hidden">
      <div
        className="flex items-center justify-between py-3 px-4 cursor-pointer hover:bg-[var(--surface-hover)] transition"
        onClick={() => setExpanded(!expanded)}
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
              {feeTierLabel(position.pool.feeTier)}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-6 text-right">
          <div>
            <div className="text-[10px] text-gray-500 uppercase">Tick Range</div>
            <div className="text-xs text-gray-300 font-mono">
              {position.tickLower.tickIdx} - {position.tickUpper.tickIdx}
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
          <span className="text-gray-500 text-xs">{expanded ? "▲" : "▼"}</span>
        </div>
      </div>

      {expanded && (
        <div className="px-4 py-4 border-t border-[var(--border)] bg-[var(--surface)] space-y-4">
          {/* Position details */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <MiniStat label={`Deposited ${position.pool.token0.symbol}`} value={Number(position.depositedToken0).toFixed(4)} />
            <MiniStat label={`Deposited ${position.pool.token1.symbol}`} value={Number(position.depositedToken1).toFixed(4)} />
            <MiniStat label={`Fees ${position.pool.token0.symbol}`} value={feesToken0.toFixed(4)} accent="emerald" />
            <MiniStat label={`Fees ${position.pool.token1.symbol}`} value={feesToken1.toFixed(4)} accent="emerald" />
          </div>

          {/* Action buttons */}
          {hasLiquidity && (
            <div className="flex items-center gap-3">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  collectFees.collect(tokenId);
                }}
                disabled={collectFees.isPending || collectFees.isConfirming}
                className="px-4 py-2 bg-[var(--wolf-emerald)]/20 text-[var(--wolf-emerald)] rounded-md text-xs font-semibold hover:bg-[var(--wolf-emerald)]/30 transition disabled:opacity-50"
              >
                {collectFees.isPending ? "Signing..." : collectFees.isConfirming ? "Confirming..." : "Collect Fees"}
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  removeLiq.removeLiquidity(tokenId, BigInt(position.liquidity));
                }}
                disabled={removeLiq.isPending || removeLiq.isConfirming}
                className="px-4 py-2 bg-[var(--wolf-red)]/20 text-[var(--wolf-red)] rounded-md text-xs font-semibold hover:bg-[var(--wolf-red)]/30 transition disabled:opacity-50"
              >
                {removeLiq.isPending ? "Signing..." : removeLiq.isConfirming ? "Confirming..." : "Remove Liquidity"}
              </button>
              {collectFees.isSuccess && (
                <span className="text-xs text-[var(--wolf-emerald)]">Fees collected!</span>
              )}
              {removeLiq.isSuccess && (
                <span className="text-xs text-[var(--wolf-emerald)]">Liquidity removed!</span>
              )}
              {(collectFees.error || removeLiq.error) && (
                <span className="text-xs text-[var(--wolf-red)]">
                  {(collectFees.error || removeLiq.error)?.message?.slice(0, 60)}
                </span>
              )}
            </div>
          )}

          <div className="text-xs text-gray-500 font-mono">
            Token ID: {position.id}
          </div>
        </div>
      )}
    </div>
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
  const { isConnected } = useAccount();

  return (
    <tr>
      <td colSpan={5} className="px-3 py-4 bg-[var(--surface)]">
        {isLoading && (
          <div className="text-center py-4 text-gray-500 text-sm">Loading pool details...</div>
        )}
        {detail && (
          <div className="space-y-6">
            <APRCalculator pool={pool} detail={detail} />
            {isConnected && <AddLiquidityPanel pool={pool} />}
          </div>
        )}
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
// Add Liquidity Panel
// ---------------------------------------------------------------------------

function AddLiquidityPanel({ pool }: { pool: SubgraphPool }) {
  const [amount0, setAmount0] = useState("");
  const [amount1, setAmount1] = useState("");
  const [priceLower, setPriceLower] = useState("");
  const [priceUpper, setPriceUpper] = useState("");

  const d0 = Number(pool.token0.decimals);
  const d1 = Number(pool.token1.decimals);

  const mintPosition = useMintPosition();
  const approve0 = useApproveToken(pool.token0.id as `0x${string}`);
  const approve1 = useApproveToken(pool.token1.id as `0x${string}`);

  const handleMint = useCallback(() => {
    if (!amount0 || !amount1 || !priceLower || !priceUpper) return;

    const tickSpacing = Number(pool.feeTier) === 500 ? 10 : Number(pool.feeTier) === 3000 ? 60 : Number(pool.feeTier) === 10000 ? 200 : 1;
    const tickLower = roundTick(priceToTick(Number(priceLower), d0, d1), tickSpacing);
    const tickUpper = roundTick(priceToTick(Number(priceUpper), d0, d1), tickSpacing);

    mintPosition.mint({
      token0: pool.token0.id as `0x${string}`,
      token1: pool.token1.id as `0x${string}`,
      fee: Number(pool.feeTier),
      tickLower,
      tickUpper,
      amount0: toTokenUnits(amount0, d0),
      amount1: toTokenUnits(amount1, d1),
    });
  }, [amount0, amount1, priceLower, priceUpper, pool, d0, d1, mintPosition]);

  return (
    <div className="border-t border-[var(--border)] pt-4">
      <h3 className="text-sm font-semibold text-white mb-3">Add Liquidity</h3>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div>
          <label className="block text-[10px] text-gray-500 uppercase mb-1">
            {pool.token0.symbol} Amount
          </label>
          <input
            type="text"
            value={amount0}
            onChange={(e) => setAmount0(e.target.value)}
            placeholder="0.0"
            className="w-full bg-[var(--surface-elevated)] border border-[var(--border)] rounded px-2 py-1.5 text-sm text-white"
          />
        </div>
        <div>
          <label className="block text-[10px] text-gray-500 uppercase mb-1">
            {pool.token1.symbol} Amount
          </label>
          <input
            type="text"
            value={amount1}
            onChange={(e) => setAmount1(e.target.value)}
            placeholder="0.0"
            className="w-full bg-[var(--surface-elevated)] border border-[var(--border)] rounded px-2 py-1.5 text-sm text-white"
          />
        </div>
        <div>
          <label className="block text-[10px] text-gray-500 uppercase mb-1">
            Lower Price ({pool.token1.symbol}/{pool.token0.symbol})
          </label>
          <input
            type="text"
            value={priceLower}
            onChange={(e) => setPriceLower(e.target.value)}
            placeholder="0.0"
            className="w-full bg-[var(--surface-elevated)] border border-[var(--border)] rounded px-2 py-1.5 text-sm text-white"
          />
        </div>
        <div>
          <label className="block text-[10px] text-gray-500 uppercase mb-1">
            Upper Price ({pool.token1.symbol}/{pool.token0.symbol})
          </label>
          <input
            type="text"
            value={priceUpper}
            onChange={(e) => setPriceUpper(e.target.value)}
            placeholder="0.0"
            className="w-full bg-[var(--surface-elevated)] border border-[var(--border)] rounded px-2 py-1.5 text-sm text-white"
          />
        </div>
      </div>

      <div className="flex items-center gap-3 mt-3">
        <button
          onClick={() => approve0.approve(toTokenUnits(amount0 || "0", d0))}
          disabled={!amount0 || approve0.isPending || approve0.isConfirming}
          className="px-3 py-1.5 bg-[var(--wolf-blue)]/20 text-[var(--wolf-blue)] rounded text-xs font-semibold hover:bg-[var(--wolf-blue)]/30 transition disabled:opacity-50"
        >
          {approve0.isPending ? "Signing..." : approve0.isConfirming ? "Confirming..." : `Approve ${pool.token0.symbol}`}
        </button>
        <button
          onClick={() => approve1.approve(toTokenUnits(amount1 || "0", d1))}
          disabled={!amount1 || approve1.isPending || approve1.isConfirming}
          className="px-3 py-1.5 bg-[var(--wolf-blue)]/20 text-[var(--wolf-blue)] rounded text-xs font-semibold hover:bg-[var(--wolf-blue)]/30 transition disabled:opacity-50"
        >
          {approve1.isPending ? "Signing..." : approve1.isConfirming ? "Confirming..." : `Approve ${pool.token1.symbol}`}
        </button>
        <button
          onClick={handleMint}
          disabled={!amount0 || !amount1 || !priceLower || !priceUpper || mintPosition.isPending || mintPosition.isConfirming}
          className="px-4 py-1.5 bg-[var(--wolf-emerald)]/20 text-[var(--wolf-emerald)] rounded text-xs font-semibold hover:bg-[var(--wolf-emerald)]/30 transition disabled:opacity-50"
        >
          {mintPosition.isPending ? "Signing..." : mintPosition.isConfirming ? "Confirming..." : "Mint Position"}
        </button>
      </div>

      {mintPosition.isSuccess && (
        <p className="text-xs text-[var(--wolf-emerald)] mt-2">Position minted successfully!</p>
      )}
      {mintPosition.error && (
        <p className="text-xs text-[var(--wolf-red)] mt-2">{mintPosition.error.message?.slice(0, 80)}</p>
      )}
    </div>
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
