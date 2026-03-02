"use client";

export default function PoolsPage() {
  return (
    <div className="space-y-6">
      <div className="border-b border-[var(--border)] pb-4">
        <h1 className="text-2xl font-bold text-white">LP Pool Manager</h1>
        <p className="text-gray-400 text-sm mt-1">
          Manage Uniswap V3 liquidity positions as separate profitability buckets
        </p>
      </div>

      {/* Pool Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-surface-elevated border border-[var(--border)] rounded-lg p-4">
          <p className="text-xs text-gray-500 uppercase">Active Positions</p>
          <p className="text-2xl font-bold text-[var(--wolf-purple)] mt-1">—</p>
        </div>
        <div className="bg-surface-elevated border border-[var(--border)] rounded-lg p-4">
          <p className="text-xs text-gray-500 uppercase">Total Liquidity</p>
          <p className="text-2xl font-bold text-[var(--wolf-blue)] mt-1">— <span className="text-sm font-normal text-gray-500">USD</span></p>
        </div>
        <div className="bg-surface-elevated border border-[var(--border)] rounded-lg p-4">
          <p className="text-xs text-gray-500 uppercase">Uncollected Fees</p>
          <p className="text-2xl font-bold text-[var(--wolf-emerald)] mt-1">— <span className="text-sm font-normal text-gray-500">USD</span></p>
        </div>
      </div>

      {/* Pool Browser */}
      <div className="bg-surface-elevated border border-[var(--border)] rounded-lg p-6">
        <h2 className="text-lg font-semibold text-white mb-4">Pool Browser</h2>
        <div className="text-center py-12 text-gray-500 text-sm">
          Connect wallet to browse and manage your Uniswap V3 positions.
          <br />
          Each position is tracked as a separate profitability bucket.
        </div>
      </div>
    </div>
  );
}
