import { createHash } from 'node:crypto';
import { CRYPTO_ASSETS, type CryptoAsset } from './contract';
import type { AssetSentiment, NewsArticle, SentimentSnapshot } from './analysis-contract';

const WINDOW_HOURS = 72;
const FEEDS = [
  {name: 'CoinDesk', url: 'https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml', host: 'coindesk.com'},
  {name: 'Cointelegraph', url: 'https://cointelegraph.com/rss', host: 'cointelegraph.com'},
] as const;
const POSITIVE = new Set(['bullish', 'rally', 'rallies', 'surge', 'surges', 'gain', 'gains', 'rise', 'rises', 'breakout', 'approval', 'approved', 'inflow', 'inflows', 'adoption', 'upgrade', 'partnership']);
const NEGATIVE = new Set(['bearish', 'drop', 'drops', 'crash', 'crashes', 'fall', 'falls', 'plunge', 'plunges', 'loss', 'losses', 'hack', 'hacked', 'exploit', 'outflow', 'outflows', 'rejected', 'ban', 'fraud']);
const MATCH: Record<CryptoAsset, RegExp> = {BTC: /\b(?:bitcoin|btc)\b/i, ETH: /\b(?:ethereum|ether|eth)\b/i, LINK: /\bchainlink\b|\$LINK\b/i};

function text(raw: string): string {
  const entities: Record<string, string> = {amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' '};
  return raw.replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, '$1').replace(/<[^>]*>/g, ' ')
    .replace(/&(#x[0-9a-f]+|#\d+|amp|lt|gt|quot|apos|nbsp);/gi, (match, token: string) => {
      if (!token.startsWith('#')) return entities[token.toLowerCase()] ?? match;
      const code = token.toLowerCase().startsWith('#x') ? parseInt(token.slice(2), 16) : parseInt(token.slice(1), 10);
      return code > 0 && code <= 0x10ffff ? String.fromCodePoint(code) : '';
    }).replace(/\s+/g, ' ').trim();
}
function field(item: string, name: string): string {
  return text(item.match(new RegExp(`<${name}(?:\\s[^>]*)?>([\\s\\S]*?)<\\/${name}>`, 'i'))?.[1] ?? '');
}

/** Deliberately simple, inspectable headline-language score. Never a return forecast. */
export function headlineTone(title: string): Pick<NewsArticle, 'score' | 'positiveTerms' | 'negativeTerms'> {
  const tokens = title.toLowerCase().match(/[a-z]+/g) ?? [];
  const positiveTerms: string[] = []; const negativeTerms: string[] = [];
  tokens.forEach((token, index) => {
    if (!POSITIVE.has(token) && !NEGATIVE.has(token)) return;
    const negated = tokens.slice(Math.max(0, index - 3), index).some(word => ['no', 'not', 'never', 'without'].includes(word));
    const positive = POSITIVE.has(token) !== negated;
    (positive ? positiveTerms : negativeTerms).push(negated ? `negated ${token}` : token);
  });
  const count = positiveTerms.length + negativeTerms.length;
  return {score: count ? (positiveTerms.length - negativeTerms.length) / count : 0, positiveTerms, negativeTerms};
}

export function parseHeadlines(xml: string, source: string, allowedHost: string, now = new Date()): NewsArticle[] {
  if (xml.length > 1_500_000 || !/<rss\b/i.test(xml) || !/<\/rss>\s*$/i.test(xml) || !Number.isFinite(now.getTime())) throw new Error('Publisher returned an unsupported or oversized RSS document, or the observation time is invalid.');
  const result: NewsArticle[] = [];
  for (const match of xml.matchAll(/<item(?:\s[^>]*)?>([\s\S]*?)<\/item>/gi)) {
    const title = field(match[1], 'title'); const urlText = field(match[1], 'link'); const published = Date.parse(field(match[1], 'pubDate'));
    if (!title || title.length > 600 || !Number.isFinite(published) || published > now.getTime() || now.getTime() - published > WINDOW_HOURS * 3_600_000) continue;
    let url: URL;
    try { url = new URL(urlText); } catch { continue; }
    if (url.protocol !== 'https:' || !(url.hostname === allowedHost || url.hostname.endsWith(`.${allowedHost}`)) || url.username || url.password) continue;
    for (const key of [...url.searchParams.keys()]) if (key.startsWith('utm_')) url.searchParams.delete(key);
    url.hash = '';
    const assets = CRYPTO_ASSETS.filter(asset => MATCH[asset].test(title));
    if (!assets.length) continue;
    const id = createHash('sha256').update(url.toString()).digest('hex');
    result.push({id, title, url: url.toString(), source, publishedAt: new Date(published).toISOString(), assets, ...headlineTone(title)});
  }
  return result;
}

export function summarizeHeadlines(articles: NewsArticle[], feedsAvailable: boolean): Record<CryptoAsset, AssetSentiment> {
  const unique = new Map<string, NewsArticle>(); const titles = new Set<string>();
  for (const article of [...articles].sort((a, b) => b.publishedAt.localeCompare(a.publishedAt))) {
    const title = article.title.toLowerCase().replace(/\W+/g, ' ').trim();
    if (unique.has(article.id) || titles.has(title)) continue;
    unique.set(article.id, article); titles.add(title);
  }
  return Object.fromEntries(CRYPTO_ASSETS.map(asset => {
    const rows = [...unique.values()].filter(article => article.assets.includes(asset));
    const score = rows.length ? rows.reduce((sum, article) => sum + article.score, 0) / rows.length : null;
    const label = score === null ? feedsAvailable ? 'No asset-specific headlines in the 72-hour window' : 'News feeds unavailable'
      : score > .15 ? 'Positive headline language' : score < -.15 ? 'Negative headline language' : 'Mixed or no directional headline language';
    return [asset, {status: rows.length ? 'available' : 'unavailable', score, label, headlineCount: rows.length, asOf: rows[0]?.publishedAt ?? null, articles: rows}];
  })) as Record<CryptoAsset, AssetSentiment>;
}

async function publicText(url: string): Promise<string> {
  const response = await fetch(url, {cache: 'no-store', signal: AbortSignal.timeout(8_000), headers: {'User-Agent': 'WolfPack personal market analysis/1.0', Accept: 'application/rss+xml, application/xml, application/json, text/xml'}});
  if (!response.ok) throw new Error(`Source returned HTTP ${response.status}.`);
  if (Number(response.headers.get('content-length')) > 1_500_000) throw new Error('Source response exceeds the size limit.');
  const content = await response.text();
  if (content.length > 1_500_000) throw new Error('Source response exceeds the size limit.');
  return content;
}

let cached: {until: number; value: SentimentSnapshot} | undefined;
let pending: Promise<SentimentSnapshot> | undefined;
export async function fetchSentiment(): Promise<SentimentSnapshot> {
  if (cached && cached.until > Date.now()) return cached.value;
  if (pending) return pending;
  pending = (async () => {
    const now = new Date();
    const [feeds, fearGreed] = await Promise.all([
      Promise.all(FEEDS.map(async feed => {
        try { const articles = parseHeadlines(await publicText(feed.url), feed.name, feed.host, now); return {source: {name: feed.name, url: feed.url, status: 'available' as const, itemCount: articles.length}, articles}; }
        catch (error) { return {source: {name: feed.name, url: feed.url, status: 'unavailable' as const, itemCount: 0, error: error instanceof Error ? error.message : 'News source unavailable.'}, articles: [] as NewsArticle[]}; }
      })),
      (async (): Promise<SentimentSnapshot['bitcoinFearGreed']> => {
        const base = {sourceUrl: 'https://alternative.me/crypto/fear-and-greed-index/', scope: 'Bitcoin only' as const};
        try {
          const row = JSON.parse(await publicText('https://api.alternative.me/fng/?limit=1')).data?.[0];
          const value = Number(row?.value); const at = Number(row?.timestamp) * 1000;
          if (typeof row?.value !== 'string' || !/^\d{1,3}$/.test(row.value) || typeof row?.timestamp !== 'string' || !/^\d+$/.test(row.timestamp) || !Number.isInteger(value) || value < 0 || value > 100 || !Number.isFinite(at) || at > now.getTime() || now.getTime() - at > 48 * 3_600_000 || typeof row?.value_classification !== 'string') throw new Error('Invalid or stale Bitcoin sentiment observation.');
          return {...base, status: 'available', value, label: row.value_classification.slice(0, 80), asOf: new Date(at).toISOString()};
        } catch { return {...base, status: 'unavailable', value: null, label: 'Bitcoin index unavailable', asOf: null}; }
      })(),
    ]);
    const value: SentimentSnapshot = {fetchedAt: now.toISOString(), method: 'Fixed headline lexicon with explicit title asset matching and short negation window; not a prediction model', windowHours: WINDOW_HOURS,
      assets: summarizeHeadlines(feeds.flatMap(feed => feed.articles), feeds.some(feed => feed.source.status === 'available')), sources: feeds.map(feed => feed.source), bitcoinFearGreed: fearGreed,
      limitations: ['Headline language is not measured public opinion, verified event impact or a probability of profit.', 'The title lexicon can miss context, sarcasm and events whose effect differs between assets.', 'Missing asset headlines remain unavailable, not neutral. Publisher coverage is incomplete.', 'Current headlines are not inserted into historical backtests. These snapshots support prospective records only.']};
    cached = {until: Date.now() + (feeds.some(feed => feed.source.status === 'available') ? 600_000 : 60_000), value};
    return value;
  })().finally(() => { pending = undefined; });
  return pending;
}
