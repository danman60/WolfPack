/** Isolated CAD spot paper workspace. Decimal strings persist; never persist bigint. */
export const ASSETS = ["CAD", "BTC", "ETH", "LINK"] as const;
export const CRYPTO_ASSETS = ["BTC", "ETH", "LINK"] as const;
export type Asset = (typeof ASSETS)[number];
export type CryptoAsset = (typeof CRYPTO_ASSETS)[number];
export type Amounts = Record<Asset, string>;
export type Cadence = "weekly" | "monthly";
export type BookLevel = { price: string; quantity: string };
export type MarketBook = { asset: CryptoAsset; bid: string; ask: string; bids: BookLevel[]; asks: BookLevel[]; minimum: string; increment: string };
export type MarketSnapshot = { id: string; source: string; fetchedAt: string; expiresAt: string; books: Record<CryptoAsset, MarketBook> };
export type LedgerEvent = { id: string; at: string; kind: "opening" | "shift" | "hold" | "deposit" | "withdrawal"; description: string; feeCad: string; realizedPnlCad: string; balances: Amounts };
export type Portfolio = {
  version: 1; id: string; revision: number; name: string; createdAt: string; cadence: Cadence; feeBps: number;
  opening: Amounts; balances: Amounts; baseline: Amounts; basisCad: Amounts;
  initialValueCad: string; netFlowsCad: string; realizedPnlCad: string; feesCad: string; events: LedgerEvent[];
};
export type FillLeg = { side: "buy" | "sell"; asset: CryptoAsset; quantity: string; grossCad: string; feeCad: string; price: string };
export type ShiftPreview = { id: string; portfolioId: string; revision: number; from: Asset; to: Asset; amount: string; received: string; feeCad: string; expiresAt: string; marketId: string; legs: FillLeg[]; after: Amounts };
export type Performance = { actualCad: string; holdCad: string; incrementalCad: string; profitCad: string; holdProfitCad: string; realizedCad: string; unrealizedCad: string; feesCad: string; netFlowsCad: string };
export type HoldingRow = { asset: Asset; units: string; priceCad: string; valueCad: string; weightPercent: number; baselineUnits: string };
export type DailyPoint = { date: string; prices: Record<CryptoAsset, number> };
export type HistoryDataset = { source: string; fetchedAt: string; points: DailyPoint[]; coverageStart: string; coverageEnd: string; note: string };
export type ResearchConfig = { capitalCad: number; cadence: Cadence; lookbackDays: number; riskPercent: number; feeBps: number; slippageBps: number };
export type ResearchPoint = { date: string; strategyCad: number; holdCad: number };
export type ResearchResult = { points: ResearchPoint[]; finalCad: number; holdCad: number; incrementalCad: number; feesCad: number; trades: number; maxDrawdownPercent: number; start: string; end: string; latestRanking: { asset: CryptoAsset; trailingReturnPercent: number }[]; suggestedAsset: Asset; note: string };

export const ROTATION_STYLE = {
  panel: "wolf-card p-5 md:p-6 min-w-0",
  title: "text-base font-semibold text-white",
  muted: "text-sm text-slate-300 leading-relaxed",
  tableWrap: "overflow-x-auto",
  table: "w-full text-sm text-left",
  cell: "py-3 pr-4 border-b border-white/10 tabular-nums",
  label: "text-xs uppercase tracking-wider text-slate-300",
};

export function cad(value: string | number): string {
  const n = Number(value);
  return Number.isFinite(n) ? new Intl.NumberFormat("en-CA", { style: "currency", currency: "CAD", maximumFractionDigits: 2 }).format(n) : "—";
}
export function eastern(value: string): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "America/Toronto", dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}
