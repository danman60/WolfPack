# Technical and sentiment inputs

Verified October 13, 2026, Eastern. This is implementation input discovery, not a new parameter search.

## Reuse and boundaries

The rotation history adapter already returns aligned completed daily CAD reference closes. Its Kraken source supplies up to720 entries including the unfinished final bar, which the adapter excludes. [Kraken's official OHLC contract](https://docs.kraken.com/api-reference/market-data/get-ohlc-data) confirms that older observations cannot be obtained by backward pagination.

BTC/CAD, ETH/CAD and LINK/CAD use those observed reference closes. ETH/BTC, LINK/BTC and LINK/ETH are same-observation ratios. They are analytical reference series, not executable quotes or independent cross-market candles. In particular, LINK/CAD already derives from aligned LINK/ETH and ETH/CAD closes. No synthetic intraday high, low, volume or filled missing observation is needed.

The chart indicator module supplies SMA, EMA and MACD formulas. Its legacy RSI implementation maps zero average loss to a finite ratio100, producing approximately99.01 even for a rising or flat series. The isolated close-only analysis should use Wilder RSI with rising100, falling0 and flat50 conventions, without silently changing legacy chart behavior. Support and resistance use explicitly named prior20 completed-close extrema, not invented OHLC extremes. Trend and momentum observations are descriptive confluence, not probabilities.

The existing Python Snoop consumes quantitative context and social summaries; it is not a primary news feed. The existing social module defaults unavailable inputs to neutral50. The new feed must retain missing coverage as unavailable rather than substituting a neutral observation.

## Current sentiment sources

Direct publisher probes returned200 from [CoinDesk RSS](https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml) and [Cointelegraph RSS](https://cointelegraph.com/rss). The observed25 CoinDesk and30 Cointelegraph items contained respectively11/10 BTC title mentions,3/1 ETH mentions and0/0 explicit Chainlink mentions. These counts describe the sampled feeds, not all news on the internet.

Use headline text, publisher URL and publication timestamp only. Asset attribution requires an explicit name or unambiguous ticker in the title. A transparent fixed lexicon can describe positive/negative headline language, with matched terms available for inspection. This is headline tone, not measured public opinion, event verification, a calibrated forecast or evidence of profitability. Sarcasm, context and ambiguous wording remain limitations. Duplicate titles/URLs should count once; missing dates, future dates and headlines outside the72-hour window should not enter the current score.

[Alternative.me's source description](https://alternative.me/crypto/fear-and-greed-index/) says the current index measures Bitcoin. Display its real published timestamp and attribution separately; never copy it into ETH or LINK as asset-specific sentiment. API failure must remain unavailable.

The key name `NEWSAPI_KEY` exists in the global key store; no key value was printed or used. That does not establish a licensed production feed. [NewsAPI's official pricing](https://newsapi.org/pricing) states that its free developer plan is delayed24 hours and restricted to development, excluding staging and production. Publisher RSS avoids depending on an unverified subscription.

## Snapshot contract

Each server snapshot should retain a version, content hash, fetched time, completed chart time, source provenance, all six pair series/indicator values, per-asset headline coverage and dated source links. A five-minute analysis cache and ten-minute news cache bound repeated requests; headline publication age and technical candle completion remain separate freshness measures. Stale or invalid chart inputs cannot yield a fresh technical claim. Unavailable news should not prevent valid charts from being shown.

Historical replay uses available historical prices only. Current news must never be injected into older folds. Newly observed headline snapshots can be archived prospectively with first-observed time for future evaluation. No current sentiment performance claim is implied.

## Read-only exchange capability reference

[Kraken's current authentication documentation](https://docs.kraken.com/exchange/guides/rest/authentication) specifies API-Key and API-Sign headers, HMAC-SHA512 signing over the path and hashed nonce/payload, and a strictly increasing per-key nonce. It supplies an offline signing test vector. Documentation review does not authorize using a real account key or sending a funded order.
