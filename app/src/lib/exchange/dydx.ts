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

const BASE_URL = "https://indexer.dydx.trade/v4";

/**
 * dYdX v4 exchange adapter.
 * Uses the dYdX v4 Indexer REST API.
 * Docs: https://docs.dydx.exchange/
 */
export class DydxAdapter implements ExchangeAdapter {
  readonly id = "dydx" as const;
  readonly name = "dYdX";
  readonly chainId = 1;

  private address: string | null = null;
  private connected = false;

  async connect(credentials: ExchangeCredentials): Promise<void> {
    this.address = credentials.walletAddress ?? credentials.apiKey ?? null;
    this.connected = true;
  }

  disconnect(): void {
    this.address = null;
    this.connected = false;
  }

  isConnected(): boolean {
    return this.connected;
  }

  async getMarkets(): Promise<MarketInfo[]> {
    const res = await fetch(`${BASE_URL}/perpetualMarkets`);
    const data = await res.json();
    const markets = data.markets ?? {};
    return (Object.values(markets) as Record<string, unknown>[]).map((m) => ({
      symbol: m.ticker as string,
      baseAsset: (m.ticker as string).replace("-USD", ""),
      quoteAsset: "USD",
      minSize: Number(m.stepBaseQuantums ?? 0),
      tickSize: Number(m.subticksPerTick ?? 0.01),
      maxLeverage: 20,
      fundingRate: 0,
      openInterest: Number(m.openInterest ?? 0),
      volume24h: Number(m.volume24H ?? 0),
      lastPrice: Number(m.oraclePrice ?? 0),
    }));
  }

  async getCandles(symbol: string, interval: string, limit = 100): Promise<Candle[]> {
    const resolution = this.mapInterval(interval);
    const res = await fetch(
      `${BASE_URL}/candles/perpetualMarkets/${symbol}?resolution=${resolution}&limit=${limit}`
    );
    const data = await res.json();
    return (data.candles ?? []).map((c: Record<string, unknown>) => ({
      timestamp: new Date(c.startedAt as string).getTime(),
      open: Number(c.open),
      high: Number(c.high),
      low: Number(c.low),
      close: Number(c.close),
      volume: Number(c.baseTokenVolume ?? 0),
    }));
  }

  async getFundingRates(): Promise<FundingRate[]> {
    const markets = await this.getMarkets();
    const rates: FundingRate[] = [];
    // Batch first 10 markets for funding rates
    for (const m of markets.slice(0, 10)) {
      try {
        const res = await fetch(
          `${BASE_URL}/historicalFunding/${m.symbol}?limit=1`
        );
        const data = await res.json();
        const latest = data.historicalFunding?.[0];
        rates.push({
          symbol: m.symbol,
          rate: latest ? Number(latest.rate) : 0,
          nextFundingTime: Date.now() + 3600000,
          predictedRate: null,
        });
      } catch {
        rates.push({
          symbol: m.symbol,
          rate: 0,
          nextFundingTime: Date.now() + 3600000,
          predictedRate: null,
        });
      }
    }
    return rates;
  }

  async getOrderbook(symbol: string, depth = 20): Promise<OrderbookSnapshot> {
    const res = await fetch(`${BASE_URL}/orderbooks/perpetualMarket/${symbol}`);
    const data = await res.json();
    return {
      symbol,
      bids: (data.bids ?? []).slice(0, depth).map((b: Record<string, string>) => [Number(b.price), Number(b.size)]),
      asks: (data.asks ?? []).slice(0, depth).map((a: Record<string, string>) => [Number(a.price), Number(a.size)]),
      timestamp: Date.now(),
    };
  }

  async getBalance(): Promise<AccountBalance> {
    this.requireAuth();
    const res = await fetch(`${BASE_URL}/addresses/${this.address}/subaccounts`);
    const data = await res.json();
    const sub = data.subaccounts?.[0];
    if (!sub) {
      return { equity: 0, freeCollateral: 0, totalMarginUsed: 0, unrealizedPnl: 0, realizedPnl: 0 };
    }
    return {
      equity: Number(sub.equity ?? 0),
      freeCollateral: Number(sub.freeCollateral ?? 0),
      totalMarginUsed: Number(sub.equity ?? 0) - Number(sub.freeCollateral ?? 0),
      unrealizedPnl: 0,
      realizedPnl: 0,
    };
  }

  async getPositions(): Promise<Position[]> {
    this.requireAuth();
    const res = await fetch(
      `${BASE_URL}/addresses/${this.address}/subaccounts/0/perpetualPositions?status=OPEN`
    );
    const data = await res.json();
    return (data.positions ?? []).map((p: Record<string, unknown>) => ({
      id: `${p.market}-${this.address}`,
      symbol: p.market as string,
      side: p.side === "LONG" ? "long" : "short",
      size: Math.abs(Number(p.size ?? 0)),
      entryPrice: Number(p.entryPrice ?? 0),
      markPrice: 0,
      liquidationPrice: null,
      unrealizedPnl: Number(p.unrealizedPnl ?? 0),
      realizedPnl: Number(p.realizedPnl ?? 0),
      leverage: 1,
      margin: 0,
      timestamp: new Date(p.createdAt as string).getTime(),
    }));
  }

  async getOpenOrders(): Promise<Order[]> {
    this.requireAuth();
    const res = await fetch(
      `${BASE_URL}/addresses/${this.address}/subaccounts/0/orders?status=OPEN`
    );
    const data = await res.json();
    return (data ?? []).map((o: Record<string, unknown>) => ({
      id: o.id as string,
      symbol: o.ticker as string,
      side: o.side === "BUY" ? "buy" : "sell",
      type: o.type === "LIMIT" ? "limit" : "market",
      size: Number(o.size ?? 0),
      price: Number(o.price ?? 0),
      filledSize: Number(o.totalFilled ?? 0),
      status: "open" as const,
      timestamp: new Date(o.createdAtHeight as string).getTime(),
    }));
  }

  async getOrderHistory(limit = 50): Promise<Order[]> {
    this.requireAuth();
    const res = await fetch(
      `${BASE_URL}/fills?address=${this.address}&subaccountNumber=0&limit=${limit}`
    );
    const data = await res.json();
    return (data.fills ?? []).map((f: Record<string, unknown>) => ({
      id: f.id as string,
      symbol: f.market as string,
      side: f.side === "BUY" ? "buy" : "sell",
      type: f.type === "LIMIT" ? "limit" : "market",
      size: Number(f.size ?? 0),
      price: Number(f.price ?? 0),
      filledSize: Number(f.size ?? 0),
      status: "filled" as const,
      timestamp: new Date(f.createdAt as string).getTime(),
    }));
  }

  async placeOrder(_params: OrderParams): Promise<Order> {
    this.requireAuth();
    throw new Error(
      "dYdX v4 order placement requires cosmos signing. Use the trading UI with connected wallet."
    );
  }

  async cancelOrder(_orderId: string): Promise<void> {
    this.requireAuth();
    throw new Error("Cancel requires cosmos signing. Use the trading UI.");
  }

  async cancelAllOrders(): Promise<void> {
    this.requireAuth();
    throw new Error("Cancel requires cosmos signing. Use the trading UI.");
  }

  private requireAuth() {
    if (!this.connected || !this.address) {
      throw new Error("Connect wallet first");
    }
  }

  private mapInterval(interval: string): string {
    const map: Record<string, string> = {
      "1m": "1MIN",
      "5m": "5MINS",
      "15m": "15MINS",
      "30m": "30MINS",
      "1h": "1HOUR",
      "4h": "4HOURS",
      "1d": "1DAY",
    };
    return map[interval] ?? "1HOUR";
  }
}
