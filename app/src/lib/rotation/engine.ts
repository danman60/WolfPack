import {
  ASSETS, CRYPTO_ASSETS,
  type Amounts, type Asset, type Cadence, type CryptoAsset, type FillLeg,
  type HoldingRow, type LedgerEvent, type MarketBook, type MarketSnapshot,
  type Performance, type Portfolio, type ShiftPreview,
} from './contract';

// Eight decimal places for quantities AND CAD. Fees round up once per CAD leg.
const SCALE = 100_000_000n;
const LIMIT = 1_000_000_000_000n * SCALE;
const BPS = 10_000n;
const MAX_EVENTS = 100_000;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
type Units = Record<Asset, bigint>;
type Sealed = { preview: string; portfolio: string; market: MarketSnapshot; generatedAt: number };
const previews = new WeakMap<ShiftPreview, Sealed>();

export class RotationValidationError extends Error {
  constructor(message: string) { super(message); this.name = 'RotationValidationError'; }
}
function fail(message: string): never { throw new RotationValidationError(message); }
function decimal(value: unknown, label = 'Amount', signed = false): bigint {
  if (typeof value !== 'string' || value.length > 24 ||
      !(signed ? /^-?(?:0|[1-9]\d*)(?:\.\d{1,8})?$/ : /^(?:0|[1-9]\d*)(?:\.\d{1,8})?$/).test(value)) {
    fail(`${label} must be a plain decimal with at most 8 decimal places.`);
  }
  const negative = value.startsWith('-');
  const [whole, fraction = ''] = (negative ? value.slice(1) : value).split('.');
  const result = BigInt(whole) * SCALE + BigInt(fraction.padEnd(8, '0'));
  if (result > LIMIT) fail(`${label} exceeds the paper accounting limit.`);
  return negative ? -result : result;
}
function format(value: bigint): string {
  if (value > LIMIT || value < -LIMIT) fail('Result exceeds the paper accounting limit.');
  const sign = value < 0n ? '-' : '';
  const absolute = value < 0n ? -value : value;
  const fraction = (absolute % SCALE).toString().padStart(8, '0').replace(/0+$/, '');
  return `${sign}${absolute / SCALE}${fraction ? `.${fraction}` : ''}`;
}
function object(value: unknown, label: string): Record<string, unknown> {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) fail(`${label} is invalid.`);
  return value as Record<string, unknown>;
}
function amountUnits(value: unknown, label = 'Balances'): Units {
  const record = object(value, label);
  if (Object.keys(record).length !== ASSETS.length || Object.keys(record).some(key => !ASSETS.includes(key as Asset))) {
    fail(`${label} must contain exactly CAD, BTC, ETH and LINK.`);
  }
  return Object.fromEntries(ASSETS.map(asset => [asset, decimal(record[asset], `${label} ${asset}`)])) as Units;
}
function amounts(value: Units): Amounts {
  return Object.fromEntries(ASSETS.map(asset => [asset, format(value[asset])])) as Amounts;
}
function sameAmounts(a: Units, b: Units): boolean { return ASSETS.every(asset => a[asset] === b[asset]); }
function asset(value: unknown): asserts value is Asset { if (!ASSETS.includes(value as Asset)) fail('Unsupported asset.'); }
function text(value: unknown, label: string, max = 200): asserts value is string {
  if (typeof value !== 'string' || !value.trim() || value.length > max) fail(`${label} is invalid.`);
}
function date(value: unknown, label: string): number {
  if (typeof value !== 'string' || !/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{3})?Z$/.test(value)) fail(`${label} is invalid.`);
  const ms = Date.parse(value);
  if (!Number.isFinite(ms) || new Date(ms).toISOString().slice(0, 19) !== value.slice(0, 19)) fail(`${label} is invalid.`);
  return ms;
}
function nowMs(now: Date): number { const value = now.getTime(); if (!Number.isFinite(value)) fail('Invalid current time.'); return value; }
function feeRate(value: unknown): asserts value is number {
  if (!Number.isInteger(value) || (value as number) < 0 || (value as number) > 1000) fail('Fee must be a whole number from 0 to 1000 basis points.');
}
function ceil(n: bigint, d: bigint): bigint { return (n + d - 1n) / d; }
function fee(gross: bigint, rate: number): bigint { return ceil(gross * BigInt(rate), BPS); }
function id(): string { return crypto.randomUUID(); }

export function emptyAmounts(): Amounts { return { CAD: '0', BTC: '0', ETH: '0', LINK: '0' }; }

function validateBook(value: unknown, expectedAsset: CryptoAsset): MarketBook {
  const book = object(value, 'Market book');
  if (book.asset !== expectedAsset) fail('Market book asset mismatch.');
  const bid = decimal(book.bid, 'Best bid');
  const ask = decimal(book.ask, 'Best ask');
  const minimum = decimal(book.minimum, 'Order minimum');
  const increment = decimal(book.increment, 'Order increment');
  if (bid <= 0n || ask <= bid || minimum <= 0n || increment <= 0n) fail('Market price or order rules are invalid.');
  for (const side of ['bids', 'asks'] as const) {
    const levels = book[side];
    if (!Array.isArray(levels) || levels.length === 0 || levels.length > 1000) fail('Market depth is invalid.');
    let previous: bigint | null = null;
    for (const item of levels) {
      const level = object(item, 'Book level');
      const price = decimal(level.price, 'Level price');
      const quantity = decimal(level.quantity, 'Level quantity');
      if (price <= 0n || quantity <= 0n) fail('Market depth must be positive.');
      if (previous !== null && (side === 'bids' ? price >= previous : price <= previous)) fail('Market depth must be strictly sorted.');
      previous = price;
    }
    if (decimal(levels[0].price) !== (side === 'bids' ? bid : ask)) fail('Top price does not match market depth.');
  }
  return book as MarketBook;
}
function validateMarket(value: MarketSnapshot, now: number, fresh: boolean): MarketSnapshot {
  const market = object(value, 'Market');
  text(market.id, 'Market ID'); text(market.source, 'Market source', 500);
  const fetched = date(market.fetchedAt, 'Market time');
  const expires = date(market.expiresAt, 'Market expiry');
  if (expires <= fetched || expires - fetched > 120_000 || fetched > now + 5_000) fail('Market timestamp is invalid.');
  if (fresh && (now >= expires || now - fetched > 120_000)) fail('Market quote expired. Refresh quotes before continuing.');
  const books = object(market.books, 'Market books');
  if (Object.keys(books).length !== CRYPTO_ASSETS.length || Object.keys(books).some(key => !CRYPTO_ASSETS.includes(key as CryptoAsset))) fail('Market books contain unsupported assets.');
  for (const symbol of CRYPTO_ASSETS) validateBook(books[symbol], symbol);
  return value;
}
function mark(market: MarketSnapshot, symbol: Asset): bigint {
  if (symbol === 'CAD') return SCALE;
  return (decimal(market.books[symbol].bid) + decimal(market.books[symbol].ask)) / 2n;
}
function valueOf(units: Units, market: MarketSnapshot): bigint {
  return ASSETS.reduce((sum, symbol) => sum + units[symbol] * mark(market, symbol) / SCALE, 0n);
}
function snapshot(portfolio: Portfolio): Portfolio { return JSON.parse(JSON.stringify(portfolio)) as Portfolio; }

export function createPortfolio(input: { name: string; opening: Amounts; cadence: Cadence; feeBps: number }, market: MarketSnapshot, now = new Date()): Portfolio {
  const time = nowMs(now);
  validateMarket(market, time, true);
  text(input.name, 'Portfolio name', 80);
  if (input.cadence !== 'weekly' && input.cadence !== 'monthly') fail('Select weekly or monthly reviews.');
  feeRate(input.feeBps);
  const units = amountUnits(input.opening, 'Opening balances');
  const initial = valueOf(units, market);
  if (initial <= 0n) fail('Opening portfolio value must be greater than zero.');
  const opening = amounts(units);
  // Opening crypto basis is a fresh paper midpoint, not historical/tax acquisition cost.
  const basisCad = amounts(Object.fromEntries(ASSETS.map(symbol => [symbol, symbol === 'CAD' ? 0n : units[symbol] * mark(market, symbol) / SCALE])) as Units);
  const event: LedgerEvent = { id: id(), at: now.toISOString(), kind: 'opening', description: 'Paper opening balances; crypto basis set to opening CAD midpoint.', feeCad: '0', realizedPnlCad: '0', balances: { ...opening } };
  return validatePortfolio({ version: 1, id: id(), revision: 0, name: input.name.trim(), createdAt: now.toISOString(), cadence: input.cadence, feeBps: input.feeBps,
    opening, balances: { ...opening }, baseline: { ...opening }, basisCad, initialValueCad: format(initial), netFlowsCad: '0', realizedPnlCad: '0', feesCad: '0', events: [event] });
}

export function performance(portfolio: Portfolio, market: MarketSnapshot): Performance {
  validatePortfolio(portfolio); validateMarket(market, Date.now(), false);
  const actual = valueOf(amountUnits(portfolio.balances), market);
  const hold = valueOf(amountUnits(portfolio.baseline), market);
  const initial = decimal(portfolio.initialValueCad);
  const flows = decimal(portfolio.netFlowsCad, 'Net flows', true);
  const realized = decimal(portfolio.realizedPnlCad, 'Realized profit', true);
  const profit = actual - initial - flows;
  return { actualCad: format(actual), holdCad: format(hold), incrementalCad: format(actual - hold), profitCad: format(profit), holdProfitCad: format(hold - initial - flows), realizedCad: format(realized), unrealizedCad: format(profit - realized), feesCad: portfolio.feesCad, netFlowsCad: portfolio.netFlowsCad };
}
export function holdingRows(portfolio: Portfolio, market: MarketSnapshot): HoldingRow[] {
  validatePortfolio(portfolio); validateMarket(market, Date.now(), false);
  const units = amountUnits(portfolio.balances);
  const total = valueOf(units, market);
  return ASSETS.map(symbol => {
    const price = mark(market, symbol);
    const value = units[symbol] * price / SCALE;
    return { asset: symbol, units: portfolio.balances[symbol], priceCad: format(price), valueCad: format(value), weightPercent: total > 0n ? Number(value * 1_000_000n / total) / 10_000 : 0, baselineUnits: portfolio.baseline[symbol] };
  });
}

function grossFor(book: MarketBook, side: 'buy' | 'sell', quantity: bigint): bigint {
  let remaining = quantity;
  let numerator = 0n;
  for (const level of side === 'buy' ? book.asks : book.bids) {
    const available = decimal(level.quantity);
    const take = remaining < available ? remaining : available;
    numerator += take * decimal(level.price);
    remaining -= take;
    if (remaining === 0n) break;
  }
  if (remaining > 0n) fail(`Insufficient ${book.asset} order-book depth for this shift.`);
  return side === 'buy' ? ceil(numerator, SCALE) : numerator / SCALE;
}
function sellLeg(book: MarketBook, quantity: bigint, rate: number): FillLeg {
  const increment = decimal(book.increment);
  if (quantity < decimal(book.minimum)) fail(`${book.asset} amount is below the order minimum.`);
  if (quantity % increment !== 0n) fail(`${book.asset} amount must be a multiple of ${book.increment}.`);
  const gross = grossFor(book, 'sell', quantity);
  const cost = fee(gross, rate);
  if (gross <= cost) fail('Sale is too small after fees.');
  return { side: 'sell', asset: book.asset, quantity: format(quantity), grossCad: format(gross), feeCad: format(cost), price: format(gross * SCALE / quantity) };
}
function buyLeg(book: MarketBook, budget: bigint, rate: number): FillLeg {
  const increment = decimal(book.increment);
  const depth = book.asks.reduce((sum, level) => sum + decimal(level.quantity), 0n);
  const maximum = depth / increment;
  const totalCost = (count: bigint) => { const gross = grossFor(book, 'buy', count * increment); return gross + fee(gross, rate); };
  let lo = 0n; let hi = maximum;
  while (lo < hi) {
    const mid = (lo + hi + 1n) / 2n;
    if (totalCost(mid) <= budget) lo = mid; else hi = mid - 1n;
  }
  const quantity = lo * increment;
  if (quantity <= 0n || quantity < decimal(book.minimum)) fail(`${book.asset} purchase is below the order minimum after fees.`);
  const gross = grossFor(book, 'buy', quantity);
  const cost = fee(gross, rate);
  // A budget that could buy another increment beyond captured depth is not a full quote.
  const lastPrice = decimal(book.asks[book.asks.length - 1].price);
  if (lo === maximum) {
    const extraGross = ceil(increment * lastPrice, SCALE);
    if (budget >= gross + extraGross + fee(gross + extraGross, rate)) fail(`Insufficient ${book.asset} order-book depth for this CAD budget.`);
  }
  return { side: 'buy', asset: book.asset, quantity: format(quantity), grossCad: format(gross), feeCad: format(cost), price: format(gross * SCALE / quantity) };
}
function buildShift(portfolio: Portfolio, market: MarketSnapshot, from: Asset, to: Asset, amount: string, time: number, previewId: string): ShiftPreview {
  asset(from); asset(to);
  if (from === to) fail('Choose two different assets.');
  const requested = decimal(amount, 'Shift amount');
  if (requested <= 0n) fail('Shift amount must be greater than zero.');
  const balances = amountUnits(portfolio.balances);
  if (requested > balances[from]) fail(`Insufficient ${from} balance.`);
  const legs: FillLeg[] = [];
  let budget = requested;
  if (from !== 'CAD') {
    const leg = sellLeg(market.books[from], requested, portfolio.feeBps);
    legs.push(leg);
    budget = decimal(leg.grossCad) - decimal(leg.feeCad);
    balances[from] -= decimal(leg.quantity);
    balances.CAD += budget;
  }
  let received = budget;
  if (to !== 'CAD') {
    const leg = buyLeg(market.books[to], budget, portfolio.feeBps);
    legs.push(leg);
    balances.CAD -= decimal(leg.grossCad) + decimal(leg.feeCad);
    balances[to] += decimal(leg.quantity);
    received = decimal(leg.quantity);
  }
  if (balances.CAD < 0n) fail('Shift would overspend CAD.');
  return { id: previewId, portfolioId: portfolio.id, revision: portfolio.revision, from, to, amount: format(requested), received: format(received), feeCad: format(legs.reduce((sum, leg) => sum + decimal(leg.feeCad), 0n)), expiresAt: new Date(Math.min(date(market.expiresAt, 'Market expiry'), time + 30_000)).toISOString(), marketId: market.id, legs, after: amounts(balances) };
}
export function previewShift(portfolio: Portfolio, market: MarketSnapshot, from: Asset, to: Asset, amount: string, now = new Date()): ShiftPreview {
  validatePortfolio(portfolio);
  const time = nowMs(now);
  validateMarket(market, time, true);
  const captured = JSON.parse(JSON.stringify(market)) as MarketSnapshot;
  const result = buildShift(portfolio, captured, from, to, amount, time, id());
  previews.set(result, { preview: JSON.stringify(result), portfolio: JSON.stringify(portfolio), market: captured, generatedAt: time });
  return result;
}
function append(portfolio: Portfolio, event: LedgerEvent): Portfolio {
  const previous = portfolio.events[portfolio.events.length - 1];
  if (date(event.at, 'Event time') < date(previous.at, 'Previous event time')) fail('Event time precedes the last ledger entry.');
  portfolio.revision += 1;
  portfolio.events.push(event);
  return validatePortfolio(portfolio);
}
export function approveShift(portfolio: Portfolio, preview: ShiftPreview, now = new Date()): Portfolio {
  validatePortfolio(portfolio);
  const time = nowMs(now);
  const sealed = previews.get(preview);
  if (!sealed || JSON.stringify(preview) !== sealed.preview) fail('Preview was changed or restored. Generate a fresh preview.');
  if (preview.portfolioId !== portfolio.id || preview.revision !== portfolio.revision || JSON.stringify(portfolio) !== sealed.portfolio) fail('Portfolio changed. Generate a fresh preview.');
  if (portfolio.events.some(event => event.id === preview.id)) fail('This shift has already been approved.');
  if (time < sealed.generatedAt || time >= date(preview.expiresAt, 'Preview expiry')) fail('Preview expired. Generate a fresh preview.');
  validateMarket(sealed.market, time, true);
  const calculated = buildShift(portfolio, sealed.market, preview.from, preview.to, preview.amount, sealed.generatedAt, preview.id);
  if (JSON.stringify(calculated) !== sealed.preview) fail('Preview accounting changed. Generate a fresh preview.');
  const next = snapshot(portfolio);
  const basis = amountUnits(next.basisCad, 'Cost basis');
  const starting = amountUnits(portfolio.balances);
  let realized = 0n;
  for (const leg of calculated.legs) {
    const quantity = decimal(leg.quantity);
    const gross = decimal(leg.grossCad);
    const cost = decimal(leg.feeCad);
    if (leg.side === 'sell') {
      const removedBasis = quantity === starting[leg.asset] ? basis[leg.asset] : basis[leg.asset] * quantity / starting[leg.asset];
      basis[leg.asset] -= removedBasis;
      realized += gross - cost - removedBasis;
    } else basis[leg.asset] += gross + cost;
  }
  next.balances = { ...calculated.after };
  next.basisCad = amounts(basis);
  next.realizedPnlCad = format(decimal(next.realizedPnlCad, 'Realized profit', true) + realized);
  next.feesCad = format(decimal(next.feesCad) + decimal(calculated.feeCad));
  const approved = append(next, { id: calculated.id, at: now.toISOString(), kind: 'shift', description: `Paper shift ${calculated.amount} ${calculated.from} → ${calculated.received} ${calculated.to}${calculated.legs.length === 2 ? ' via CAD' : ''}.`, feeCad: calculated.feeCad, realizedPnlCad: format(realized), balances: { ...next.balances } });
  previews.delete(preview);
  return approved;
}
export function recordHold(portfolio: Portfolio, now = new Date()): Portfolio {
  validatePortfolio(portfolio); nowMs(now);
  const next = snapshot(portfolio);
  return append(next, { id: id(), at: now.toISOString(), kind: 'hold', description: 'HOLD recorded. Units unchanged; no paper fee.', feeCad: '0', realizedPnlCad: '0', balances: { ...next.balances } });
}
export function recordCashFlow(portfolio: Portfolio, kind: 'deposit' | 'withdrawal', amount: string, now = new Date()): Portfolio {
  validatePortfolio(portfolio); nowMs(now);
  if (kind !== 'deposit' && kind !== 'withdrawal') fail('Invalid cash-flow kind.');
  const quantity = decimal(amount, 'Cash flow');
  if (quantity <= 0n) fail('Cash flow must be greater than zero.');
  const next = snapshot(portfolio);
  const actual = amountUnits(next.balances); const baseline = amountUnits(next.baseline);
  if (kind === 'withdrawal' && (quantity > actual.CAD || quantity > baseline.CAD)) fail('Withdrawal requires enough CAD in both the paper portfolio and HOLD baseline. No automatic liquidation.');
  const delta = kind === 'deposit' ? quantity : -quantity;
  actual.CAD += delta; baseline.CAD += delta;
  next.balances = amounts(actual); next.baseline = amounts(baseline);
  next.netFlowsCad = format(decimal(next.netFlowsCad, 'Net flows', true) + delta);
  return append(next, { id: id(), at: now.toISOString(), kind, description: `Paper CAD ${kind}: ${format(quantity)}; matched in HOLD baseline.`, feeCad: '0', realizedPnlCad: '0', balances: { ...next.balances } });
}

/** Strict structural and ledger reconciliation validation; browser storage is not an authenticated ledger. */
export function validatePortfolio(value: unknown): Portfolio {
  const p = object(value, 'Saved portfolio');
  if (p.version !== 1 || typeof p.id !== 'string' || !UUID.test(p.id)) fail('Saved portfolio version or ID is invalid.');
  if (!Number.isSafeInteger(p.revision) || (p.revision as number) < 0) fail('Saved portfolio revision is invalid.');
  text(p.name, 'Portfolio name', 80); feeRate(p.feeBps);
  if (p.cadence !== 'weekly' && p.cadence !== 'monthly') fail('Saved review cadence is invalid.');
  const created = date(p.createdAt, 'Creation time');
  const opening = amountUnits(p.opening, 'Opening balances');
  const balances = amountUnits(p.balances); const baseline = amountUnits(p.baseline, 'HOLD balances');
  const basis = amountUnits(p.basisCad, 'Cost basis');
  if (basis.CAD !== 0n || CRYPTO_ASSETS.some(symbol => balances[symbol] === 0n && basis[symbol] !== 0n)) fail('Saved cost basis is inconsistent.');
  const initial = decimal(p.initialValueCad, 'Initial value');
  const netFlows = decimal(p.netFlowsCad, 'Net flows', true);
  const realized = decimal(p.realizedPnlCad, 'Realized profit', true);
  const fees = decimal(p.feesCad, 'Fees');
  if (initial <= 0n || ASSETS.every(symbol => opening[symbol] === 0n)) fail('Saved opening value must be positive.');
  if (baseline.CAD !== opening.CAD + netFlows || CRYPTO_ASSETS.some(symbol => baseline[symbol] !== opening[symbol])) fail('HOLD baseline does not match original units and cash flows.');
  if (!Array.isArray(p.events) || p.events.length === 0 || p.events.length > MAX_EVENTS || p.events.length !== (p.revision as number) + 1) fail('Ledger revision or event count is inconsistent.');
  const ids = new Set<string>();
  let previous = opening; let previousTime = created; let eventFees = 0n; let eventRealized = 0n; let eventFlows = 0n;
  for (let index = 0; index < p.events.length; index += 1) {
    const event = object(p.events[index], 'Ledger event');
    if (typeof event.id !== 'string' || !UUID.test(event.id) || ids.has(event.id)) fail('Ledger contains an invalid or duplicate event ID.');
    ids.add(event.id);
    const at = date(event.at, 'Event time');
    if (at < previousTime) fail('Ledger event chronology is inconsistent.');
    previousTime = at;
    text(event.description, 'Event description', 1000);
    const current = amountUnits(event.balances, 'Event balances');
    const eventFee = decimal(event.feeCad, 'Event fee');
    const eventProfit = decimal(event.realizedPnlCad, 'Event realized profit', true);
    if (index === 0) {
      if (event.kind !== 'opening' || at !== created || !sameAmounts(current, opening) || eventFee !== 0n || eventProfit !== 0n) fail('Opening ledger entry is inconsistent.');
    } else if (event.kind === 'hold') {
      if (!sameAmounts(previous, current) || eventFee !== 0n || eventProfit !== 0n) fail('HOLD entry changed balances or charged costs.');
    } else if (event.kind === 'deposit' || event.kind === 'withdrawal') {
      const delta = current.CAD - previous.CAD;
      if ((event.kind === 'deposit' ? delta <= 0n : delta >= 0n) || CRYPTO_ASSETS.some(symbol => current[symbol] !== previous[symbol]) || eventFee !== 0n || eventProfit !== 0n) fail('Cash-flow ledger entry is inconsistent.');
      eventFlows += delta;
      if (opening.CAD + eventFlows < 0n) fail('Cash flow made HOLD CAD negative.');
    } else if (event.kind === 'shift') {
      const changed = CRYPTO_ASSETS.filter(symbol => current[symbol] !== previous[symbol]);
      if (changed.length < 1 || changed.length > 2) fail('Shift entry has an invalid asset route.');
      if (changed.length === 2 && !changed.some(symbol => current[symbol] > previous[symbol])) fail('Shift entry lacks a purchased asset.');
      if (changed.length === 2 && !changed.some(symbol => current[symbol] < previous[symbol])) fail('Shift entry lacks a sold asset.');
      if (changed.length === 2 && current.CAD < previous.CAD) fail('Crypto conversion spent unrelated CAD.');
      if (changed.length === 1) {
        const delta = current[changed[0]] - previous[changed[0]];
        if (delta > 0n ? current.CAD >= previous.CAD : current.CAD <= previous.CAD) fail('Shift CAD movement is inconsistent.');
        if (delta > 0n && eventProfit !== 0n) fail('A purchase cannot realize profit.');
      }
      if (p.feeBps === 0 && eventFee !== 0n) fail('Zero-fee portfolio contains a fee.');
      if ((p.feeBps as number) > 0 && eventFee === 0n) fail('Shift entry is missing its fee.');
    } else fail('Unknown ledger event kind.');
    eventFees += eventFee; eventRealized += eventProfit; previous = current;
  }
  if (!sameAmounts(previous, balances) || eventFees !== fees || eventRealized !== realized || eventFlows !== netFlows) fail('Portfolio totals do not reconcile with the ledger.');
  const remainingBasis = CRYPTO_ASSETS.reduce((sum, symbol) => sum + basis[symbol], 0n);
  if (balances.CAD + remainingBasis - realized !== initial + netFlows) fail('Cash, remaining cost basis and realized profit do not reconcile.');
  return value as Portfolio;
}
