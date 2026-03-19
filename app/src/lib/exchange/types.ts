// Exchange adapter interface — unified API for Hyperliquid, dYdX, and Uniswap V3

export type ExchangeId = "hyperliquid" | "dydx" | "kraken";

export interface Asset {
  symbol: string;
  name: string;
  decimals: number;
}

export interface MarketInfo {
  symbol: string;
  baseAsset: string;
  quoteAsset: string;
  minSize: number;
  tickSize: number;
  maxLeverage: number;
  fundingRate: number;
  openInterest: number;
  volume24h: number;
  lastPrice: number;
}

export interface Position {
  id: string;
  symbol: string;
  side: "long" | "short";
  size: number;
  entryPrice: number;
  markPrice: number;
  liquidationPrice: number | null;
  unrealizedPnl: number;
  realizedPnl: number;
  leverage: number;
  margin: number;
  timestamp: number;
}

export interface OrderParams {
  symbol: string;
  side: "buy" | "sell";
  type: "market" | "limit";
  size: number;
  price?: number;
  reduceOnly?: boolean;
  leverage?: number;
  stopLoss?: number;
  takeProfit?: number;
}

export interface Order {
  id: string;
  symbol: string;
  side: "buy" | "sell";
  type: "market" | "limit";
  size: number;
  price: number;
  filledSize: number;
  status: "open" | "filled" | "cancelled" | "rejected";
  timestamp: number;
}

export interface AccountBalance {
  equity: number;
  freeCollateral: number;
  totalMarginUsed: number;
  unrealizedPnl: number;
  realizedPnl: number;
}

export interface Candle {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface FundingRate {
  symbol: string;
  rate: number;
  nextFundingTime: number;
  predictedRate: number | null;
}

/**
 * Unified exchange adapter interface.
 * Both Hyperliquid and dYdX implement this contract.
 */
export interface ExchangeAdapter {
  readonly id: ExchangeId;
  readonly name: string;
  readonly chainId: number;

  // Connection
  connect(credentials: ExchangeCredentials): Promise<void>;
  disconnect(): void;
  isConnected(): boolean;

  // Market data (public, no auth needed)
  getMarkets(): Promise<MarketInfo[]>;
  getCandles(symbol: string, interval: string, limit?: number): Promise<Candle[]>;
  getFundingRates(): Promise<FundingRate[]>;
  getOrderbook(symbol: string, depth?: number): Promise<OrderbookSnapshot>;

  // Account (requires auth)
  getBalance(): Promise<AccountBalance>;
  getPositions(): Promise<Position[]>;
  getOpenOrders(): Promise<Order[]>;
  getOrderHistory(limit?: number): Promise<Order[]>;

  // Trading (requires auth)
  placeOrder(params: OrderParams): Promise<Order>;
  cancelOrder(orderId: string): Promise<void>;
  cancelAllOrders(symbol?: string): Promise<void>;
}

export interface ExchangeCredentials {
  apiKey?: string;
  apiSecret?: string;
  walletAddress?: string;
  privateKey?: string;
}

export interface OrderbookSnapshot {
  symbol: string;
  bids: [number, number][]; // [price, size]
  asks: [number, number][]; // [price, size]
  timestamp: number;
}

export interface ExchangeConfig {
  id: ExchangeId;
  name: string;
  icon: string;
  chainId: number;
  rpcUrl: string;
  explorerUrl: string;
  testnet: boolean;
}

export const EXCHANGE_CONFIGS: Record<ExchangeId, ExchangeConfig> = {
  hyperliquid: {
    id: "hyperliquid",
    name: "Hyperliquid",
    icon: "HL",
    chainId: 42161, // Arbitrum for deposits
    rpcUrl: "https://api.hyperliquid.xyz",
    explorerUrl: "https://app.hyperliquid.xyz",
    testnet: false,
  },
  dydx: {
    id: "dydx",
    name: "dYdX",
    icon: "dY",
    chainId: 1, // Ethereum mainnet
    rpcUrl: "https://indexer.dydx.trade/v4",
    explorerUrl: "https://trade.dydx.exchange",
    testnet: false,
  },
  kraken: {
    id: "kraken",
    name: "Kraken",
    icon: "KR",
    chainId: 0,
    rpcUrl: "",
    explorerUrl: "https://www.kraken.com",
    testnet: false,
  },
};
