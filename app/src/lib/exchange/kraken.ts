import { intelFetch } from "@/lib/intel";
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

/**
 * Kraken exchange adapter.
 * Routes ALL calls through the Python intel service (CLI is server-side only).
 */
export class KrakenAdapter implements ExchangeAdapter {
  readonly id = "kraken" as const;
  readonly name = "Kraken";
  readonly chainId = 0;

  private connected = false;

  async connect(_credentials: ExchangeCredentials): Promise<void> {
    // Kraken paper trading requires no API keys
    this.connected = true;
  }

  disconnect(): void {
    this.connected = false;
  }

  isConnected(): boolean {
    return this.connected;
  }

  async getMarkets(): Promise<MarketInfo[]> {
    const res = await intelFetch("/intel/market/markets?exchange=kraken");
    if (!res.ok) return [];
    const data = await res.json();
    return (data.markets ?? []).map((m: Record<string, unknown>) => ({
      symbol: m.symbol as string,
      baseAsset: m.base_asset as string,
      quoteAsset: "USD",
      minSize: 0,
      tickSize: 0.01,
      maxLeverage: Number(m.max_leverage ?? 50),
      fundingRate: Number(m.funding_rate ?? 0),
      openInterest: Number(m.open_interest ?? 0),
      volume24h: Number(m.volume_24h ?? 0),
      lastPrice: Number(m.last_price ?? 0),
    }));
  }

  async getCandles(symbol: string, interval: string, limit = 100): Promise<Candle[]> {
    const res = await intelFetch(
      `/intel/market/candles?symbol=${symbol}&interval=${interval}&limit=${limit}&exchange=kraken`
    );
    if (!res.ok) return [];
    const data = await res.json();
    return (data.candles ?? []).map((c: Record<string, unknown>) => ({
      timestamp: Number(c.timestamp),
      open: Number(c.open),
      high: Number(c.high),
      low: Number(c.low),
      close: Number(c.close),
      volume: Number(c.volume),
    }));
  }

  async getFundingRates(): Promise<FundingRate[]> {
    const markets = await this.getMarkets();
    return markets.map((m) => ({
      symbol: m.symbol,
      rate: m.fundingRate,
      nextFundingTime: Date.now() + 3600000,
      predictedRate: null,
    }));
  }

  async getOrderbook(symbol: string, depth = 20): Promise<OrderbookSnapshot> {
    const res = await intelFetch(
      `/intel/market/orderbook?symbol=${symbol}&depth=${depth}&exchange=kraken`
    );
    if (!res.ok) {
      return { symbol, bids: [], asks: [], timestamp: Date.now() };
    }
    const data = await res.json();
    const ob = data.orderbook ?? data;
    return {
      symbol,
      bids: (ob.bids ?? []).slice(0, depth).map((b: Record<string, number>) => [b.price, b.size]),
      asks: (ob.asks ?? []).slice(0, depth).map((a: Record<string, number>) => [a.price, a.size]),
      timestamp: ob.timestamp ?? Date.now(),
    };
  }

  async getBalance(): Promise<AccountBalance> {
    const res = await intelFetch("/intel/kraken/paper/balance");
    if (!res.ok) {
      return { equity: 0, freeCollateral: 0, totalMarginUsed: 0, unrealizedPnl: 0, realizedPnl: 0 };
    }
    const data = await res.json();
    return {
      equity: Number(data.equity ?? data.balance ?? 0),
      freeCollateral: Number(data.free_collateral ?? data.available ?? 0),
      totalMarginUsed: Number(data.margin_used ?? 0),
      unrealizedPnl: Number(data.unrealized_pnl ?? 0),
      realizedPnl: Number(data.realized_pnl ?? 0),
    };
  }

  async getPositions(): Promise<Position[]> {
    const res = await intelFetch("/intel/kraken/paper/status");
    if (!res.ok) return [];
    const data = await res.json();
    return (data.positions ?? []).map((p: Record<string, unknown>, i: number) => ({
      id: `kraken-${i}`,
      symbol: p.symbol as string,
      side: p.side as "long" | "short",
      size: Number(p.size ?? 0),
      entryPrice: Number(p.entry_price ?? 0),
      markPrice: Number(p.mark_price ?? 0),
      liquidationPrice: null,
      unrealizedPnl: Number(p.unrealized_pnl ?? 0),
      realizedPnl: 0,
      leverage: Number(p.leverage ?? 1),
      margin: 0,
      timestamp: Date.now(),
    }));
  }

  async getOpenOrders(): Promise<Order[]> {
    return [];
  }

  async getOrderHistory(_limit = 50): Promise<Order[]> {
    const res = await intelFetch("/intel/kraken/paper/history");
    if (!res.ok) return [];
    const data = await res.json();
    return (data.trades ?? []).map((t: Record<string, unknown>) => ({
      id: t.id as string,
      symbol: t.symbol as string,
      side: t.side as "buy" | "sell",
      type: "market" as const,
      size: Number(t.size ?? 0),
      price: Number(t.price ?? 0),
      filledSize: Number(t.size ?? 0),
      status: "filled" as const,
      timestamp: Number(t.timestamp ?? Date.now()),
    }));
  }

  async placeOrder(params: OrderParams): Promise<Order> {
    const endpoint = params.side === "buy"
      ? "/intel/kraken/paper/buy"
      : "/intel/kraken/paper/sell";
    const res = await intelFetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pair: params.symbol, volume: params.size }),
    });
    if (!res.ok) throw new Error("Kraken paper trade failed");
    const data = await res.json();
    return {
      id: data.id ?? `kraken-${Date.now()}`,
      symbol: params.symbol,
      side: params.side,
      type: params.type,
      size: params.size,
      price: Number(data.price ?? params.price ?? 0),
      filledSize: params.size,
      status: "filled",
      timestamp: Date.now(),
    };
  }

  async cancelOrder(_orderId: string): Promise<void> {
    // Paper trading doesn't support pending orders
  }

  async cancelAllOrders(): Promise<void> {
    // Paper trading doesn't support pending orders
  }
}
