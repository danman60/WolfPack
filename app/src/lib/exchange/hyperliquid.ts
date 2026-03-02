import type {
  ExchangeAdapter,
  ExchangeCredentials,
  MarketInfo,
  Candle,
  FundingRate,
  OrderbookSnapshot,
  AccountBalance,
  Position,
  Order,
  OrderParams,
} from "./types";

const BASE_URL = "https://api.hyperliquid.xyz";

/**
 * Hyperliquid exchange adapter.
 * Uses the Hyperliquid REST API (info + exchange endpoints).
 * Docs: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api
 */
export class HyperliquidAdapter implements ExchangeAdapter {
  readonly id = "hyperliquid" as const;
  readonly name = "Hyperliquid";
  readonly chainId = 42161;

  private walletAddress: string | null = null;
  private connected = false;

  async connect(credentials: ExchangeCredentials): Promise<void> {
    this.walletAddress = credentials.walletAddress ?? null;
    this.connected = true;
  }

  disconnect(): void {
    this.walletAddress = null;
    this.connected = false;
  }

  isConnected(): boolean {
    return this.connected;
  }

  async getMarkets(): Promise<MarketInfo[]> {
    const res = await fetch(`${BASE_URL}/info`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ type: "meta" }),
    });
    const data = await res.json();
    return (data.universe ?? []).map((m: Record<string, unknown>) => ({
      symbol: m.name as string,
      baseAsset: m.name as string,
      quoteAsset: "USD",
      minSize: Number(m.szDecimals ?? 0),
      tickSize: 0.01,
      maxLeverage: Number(m.maxLeverage ?? 50),
      fundingRate: 0,
      openInterest: 0,
      volume24h: 0,
      lastPrice: 0,
    }));
  }

  async getCandles(symbol: string, interval: string, limit = 100): Promise<Candle[]> {
    const res = await fetch(`${BASE_URL}/info`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        type: "candleSnapshot",
        req: { coin: symbol, interval, startTime: Date.now() - limit * 60000 },
      }),
    });
    const data = await res.json();
    return (data ?? []).map((c: Record<string, unknown>) => ({
      timestamp: Number(c.t),
      open: Number(c.o),
      high: Number(c.h),
      low: Number(c.l),
      close: Number(c.c),
      volume: Number(c.v),
    }));
  }

  async getFundingRates(): Promise<FundingRate[]> {
    const res = await fetch(`${BASE_URL}/info`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ type: "meta" }),
    });
    const data = await res.json();
    return (data.universe ?? []).map((m: Record<string, unknown>) => ({
      symbol: m.name as string,
      rate: Number(m.funding ?? 0),
      nextFundingTime: Date.now() + 3600000,
      predictedRate: null,
    }));
  }

  async getOrderbook(symbol: string, depth = 20): Promise<OrderbookSnapshot> {
    const res = await fetch(`${BASE_URL}/info`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ type: "l2Book", coin: symbol, nSigFigs: 5 }),
    });
    const data = await res.json();
    return {
      symbol,
      bids: (data.levels?.[0] ?? []).slice(0, depth).map((l: Record<string, string>) => [Number(l.px), Number(l.sz)]),
      asks: (data.levels?.[1] ?? []).slice(0, depth).map((l: Record<string, string>) => [Number(l.px), Number(l.sz)]),
      timestamp: Date.now(),
    };
  }

  async getBalance(): Promise<AccountBalance> {
    this.requireAuth();
    const res = await fetch(`${BASE_URL}/info`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ type: "clearinghouseState", user: this.walletAddress }),
    });
    const data = await res.json();
    const summary = data.marginSummary ?? {};
    return {
      equity: Number(summary.accountValue ?? 0),
      freeCollateral: Number(summary.totalMarginUsed ?? 0),
      totalMarginUsed: Number(summary.totalMarginUsed ?? 0),
      unrealizedPnl: Number(summary.totalNtlPos ?? 0),
      realizedPnl: 0,
    };
  }

  async getPositions(): Promise<Position[]> {
    this.requireAuth();
    const res = await fetch(`${BASE_URL}/info`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ type: "clearinghouseState", user: this.walletAddress }),
    });
    const data = await res.json();
    return (data.assetPositions ?? []).map((p: Record<string, Record<string, unknown>>) => {
      const pos = p.position ?? ({} as Record<string, unknown>);
      const lev = pos.leverage as Record<string, unknown> | undefined;
      return {
        id: `${pos.coin}-${this.walletAddress}`,
        symbol: pos.coin as string,
        side: Number(pos.szi ?? 0) > 0 ? "long" : "short",
        size: Math.abs(Number(pos.szi ?? 0)),
        entryPrice: Number(pos.entryPx ?? 0),
        markPrice: 0,
        liquidationPrice: pos.liquidationPx ? Number(pos.liquidationPx) : null,
        unrealizedPnl: Number(pos.unrealizedPnl ?? 0),
        realizedPnl: Number(pos.returnOnEquity ?? 0),
        leverage: Number(lev?.value ?? 1),
        margin: Number(pos.marginUsed ?? 0),
        timestamp: Date.now(),
      };
    });
  }

  async getOpenOrders(): Promise<Order[]> {
    this.requireAuth();
    const res = await fetch(`${BASE_URL}/info`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ type: "openOrders", user: this.walletAddress }),
    });
    const data = await res.json();
    return (data ?? []).map((o: Record<string, unknown>) => ({
      id: String(o.oid),
      symbol: o.coin as string,
      side: o.side === "B" ? "buy" : "sell",
      type: o.orderType === "Limit" ? "limit" : "market",
      size: Number(o.sz ?? 0),
      price: Number(o.limitPx ?? 0),
      filledSize: 0,
      status: "open" as const,
      timestamp: Number(o.timestamp ?? Date.now()),
    }));
  }

  async getOrderHistory(limit = 50): Promise<Order[]> {
    this.requireAuth();
    const res = await fetch(`${BASE_URL}/info`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ type: "userFills", user: this.walletAddress }),
    });
    const data = await res.json();
    return (data ?? []).slice(0, limit).map((f: Record<string, unknown>) => ({
      id: String(f.oid),
      symbol: f.coin as string,
      side: f.side === "B" ? "buy" : "sell",
      type: "market" as const,
      size: Number(f.sz ?? 0),
      price: Number(f.px ?? 0),
      filledSize: Number(f.sz ?? 0),
      status: "filled" as const,
      timestamp: Number(f.time ?? Date.now()),
    }));
  }

  async placeOrder(params: OrderParams): Promise<Order> {
    this.requireAuth();
    // Order placement requires EIP-712 signing with the wallet
    // This is a placeholder — real implementation will use viem for signing
    throw new Error(
      "Order placement requires wallet signing. Use the trading UI with connected wallet."
    );
  }

  async cancelOrder(orderId: string): Promise<void> {
    this.requireAuth();
    throw new Error("Cancel requires wallet signing. Use the trading UI.");
  }

  async cancelAllOrders(): Promise<void> {
    this.requireAuth();
    throw new Error("Cancel requires wallet signing. Use the trading UI.");
  }

  private requireAuth() {
    if (!this.connected || !this.walletAddress) {
      throw new Error("Connect wallet first");
    }
  }
}
