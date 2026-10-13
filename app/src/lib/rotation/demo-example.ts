import { CRYPTO_ASSETS, type Amounts, type MarketSnapshot, type Portfolio } from './contract';
import { createPortfolio } from './engine';

const SCALE = 100_000_000n;
function units(value: string): bigint {
  if (!/^(0|[1-9]\d*)(\.\d{1,8})?$/.test(value)) throw new Error('Invalid example market amount.');
  const [whole, fraction = ''] = value.split('.');
  return BigInt(whole) * SCALE + BigInt(fraction.padEnd(8, '0'));
}
function decimal(value: bigint): string { return `${value / SCALE}.${(value % SCALE).toString().padStart(8, '0')}`; }

/** Illustrative holdings, not a trade or an allocation recommendation. */
export function createExamplePortfolio(market: MarketSnapshot, now = new Date()): Portfolio {
  const opening: Amounts = { CAD: '0', BTC: '0', ETH: '0', LINK: '0' };
  let cash = 10_000n * SCALE;
  for (const asset of CRYPTO_ASSETS) {
    const book = market.books[asset];
    const midpoint = (units(book.bid) + units(book.ask)) / 2n;
    const increment = units(book.increment);
    if (midpoint <= 0n || increment <= 0n) throw new Error('Example market rules must be positive.');
    const budget = BigInt(asset === 'BTC' ? 4000 : 2000) * SCALE;
    const quantity = (budget * SCALE / midpoint) / increment * increment;
    if (quantity <= 0n) throw new Error('Example quantity is below the market increment.');
    opening[asset] = decimal(quantity);
    cash -= quantity * midpoint / SCALE;
  }
  opening.CAD = decimal(cash);
  const portfolio = createPortfolio({ name: '$10,000 example · paper only', opening, cadence: 'weekly', feeBps: 20 }, market, now);
  if (portfolio.initialValueCad !== '10000') throw new Error('Example opening value did not reconcile.');
  return portfolio;
}
