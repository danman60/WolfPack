import { NextResponse } from "next/server";
import { CRYPTO_ASSETS, type CryptoAsset, type MarketBook, type MarketSnapshot } from "@/lib/rotation/contract";

export const dynamic = "force-dynamic";
type Instrument = { InstrumentId: number; Product1Symbol: string; Product2Symbol: string; SessionStatus: string; IsDisable: boolean; MinimumQuantity: number; QuantityIncrement: number };
let metadata: { at: number; instruments: Instrument[] } | undefined;
const API = "https://api.ndax.io:8443/AP/";

async function readPublic(path: string): Promise<unknown> {
  const response = await fetch(`${API}${path}`, { cache: "no-store", signal: AbortSignal.timeout(10_000) });
  if (!response.ok) throw new Error("Public market provider did not respond successfully.");
  return response.json();
}

export async function GET() {
  try {
    const started = Date.now();
    if (!metadata || started - metadata.at > 60_000) {
      const value = await readPublic("GetInstruments?OMSId=1");
      if (!Array.isArray(value)) throw new Error("Market instrument list is unavailable.");
      metadata = { at: started, instruments: value as Instrument[] };
    }
    let oldest = started;
    const entries = await Promise.all(CRYPTO_ASSETS.map(async (asset): Promise<[CryptoAsset, MarketBook]> => {
      const instrument = metadata!.instruments.find(row => row.Product1Symbol === asset && row.Product2Symbol === "CAD");
      if (!instrument || instrument.IsDisable || instrument.SessionStatus !== "Running" || !Number.isSafeInteger(instrument.InstrumentId)) {
        throw new Error(`${asset}/CAD is not available for this paper quote.`);
      }
      const raw = await readPublic(`GetL2Snapshot?OMSId=1&InstrumentId=${instrument.InstrumentId}&Depth=100`);
      if (!Array.isArray(raw) || raw.length < 2) throw new Error(`${asset}/CAD order book is incomplete.`);
      const sides = [new Map<number, number>(), new Map<number, number>()];
      let snapshotTime = 0;
      for (const row of raw) {
        if (!Array.isArray(row) || row.length < 10) throw new Error(`${asset}/CAD book format is invalid.`);
        const time = Number(row[2]); const price = Number(row[6]); const quantity = Number(row[8]); const side = Number(row[9]);
        if (!Number.isFinite(time) || time <= 0 || !Number.isFinite(price) || price <= 0 || !Number.isFinite(quantity) || quantity < 0 || (side !== 0 && side !== 1) || Number(row[7]) !== instrument.InstrumentId) {
          throw new Error(`${asset}/CAD book contains invalid values.`);
        }
        snapshotTime = Math.max(snapshotTime, time);
        if (quantity > 0) sides[side].set(price, (sides[side].get(price) ?? 0) + quantity);
      }
      if (Date.now() - snapshotTime > 45_000 || snapshotTime > Date.now() + 5000) throw new Error(`${asset}/CAD book is stale. Refresh shortly.`);
      oldest = Math.min(oldest, snapshotTime);
      const levels = (side: number) => [...sides[side]].sort((a, b) => side === 0 ? b[0] - a[0] : a[0] - b[0]).map(([price, quantity]) => ({ price: price.toFixed(8), quantity: quantity.toFixed(8) }));
      const bids = levels(0); const asks = levels(1);
      if (!bids.length || !asks.length || Number(bids[0].price) >= Number(asks[0].price)) throw new Error(`${asset}/CAD book is crossed or incomplete.`);
      if (!(instrument.MinimumQuantity > 0) || !(instrument.QuantityIncrement > 0)) throw new Error(`${asset}/CAD trading rules are incomplete.`);
      return [asset, { asset, bid: bids[0].price, ask: asks[0].price, bids, asks, minimum: instrument.MinimumQuantity.toFixed(8), increment: instrument.QuantityIncrement.toFixed(8) }];
    }));
    const fetchedAt = Date.now();
    const expiresAt = Math.min(fetchedAt + 30_000, oldest + 45_000);
    if (expiresAt <= fetchedAt) throw new Error("Market snapshot expired while loading. Refresh shortly.");
    const snapshot: MarketSnapshot = {
      id: crypto.randomUUID(), source: "Ndax public CAD spot order books", fetchedAt: new Date(fetchedAt).toISOString(),
      expiresAt: new Date(expiresAt).toISOString(), books: Object.fromEntries(entries) as Record<CryptoAsset, MarketBook>,
    };
    return NextResponse.json(snapshot, { headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    return NextResponse.json({ error: error instanceof Error ? error.message : "Market data is unavailable. No substitute prices were used." }, { status: 503, headers: { "Cache-Control": "no-store" } });
  }
}
