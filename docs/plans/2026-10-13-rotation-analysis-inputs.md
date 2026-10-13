# Rotation analysis input implementation

This exists so that the app shows "real continuous technical + SENTIMENT inputs" for all six requested pairs.

Scope: isolated server-owned analysis data modules and authenticated read-only route. Full Astra implementation is authorized. No existing wallet, private credential, funded-order or legacy indicator behavior changes.

1. Add `analysis-contract.ts`: exact six-pair chart, technical, headline and source/freshness types. Share with UI/backend owners before implementation dependencies.
2. Add `technical-analysis.ts`: aligned completed close ratios; close-only RSI14, MACD12/26/9, SMA20/50/200; prior20/60 closing extrema. Verify independent numerical formulas, flat/rising/falling RSI, gap rejection and prefix causality.
3. Add `sentiment.ts`: bounded public CoinDesk/Cointelegraph RSS fetches; title-only explicit asset mapping and transparent tone lexicon; publication/future/age checks; deduplication; separate attributed Bitcoin Fear & Greed source. No fabricated neutral data on failure.
4. Add `analysis-server.ts` and `api/rotation/analysis/route.ts`: compose/cache immutable hashed snapshots, authenticated read-only response, partial source failures visible. Preserve actual daily history adapter and all previous study bytes.
5. Verify current real feeds and route, then support full-workspace QA and isolated build after other owners finish. No new historical sentiment or strategy search is claimed.

Acceptance: exact BTC/CAD, ETH/CAD, LINK/CAD, ETH/BTC, LINK/BTC, LINK/ETH reference series; finite indicators; explicit timestamps and source links; absence of asset news represented as unavailable; historical replay never receives today's headlines.
