# Rotation research evidence

Generated Monday, October 12, 2026 at 10:55:00 p.m. EDT.

Source: real Kraken spot OHLC, 719 completed matching daily candle dates, 2024-10-24 through 2026-10-12. LINK/CAD is LINK/ETH close multiplied by the same-date ETH/CAD close. These are reference prices, not executable Ndax fills. Source archive, exact inputs, daily curves, chronological decisions and fold output are preserved in [backtest-evidence.json](backtest-evidence.json).

## Explicit QA experiments

Both runs use CAD 10,000 starting value, 60% crypto allocation, 60-day lookback, 20 bps fee per executed leg, and 10 bps adverse slippage. These are engineering QA scenarios chosen to exercise the implementation, not owner preferences, optimized settings or recommendations.

| Cadence | Strategy ending value | Unchanged HOLD | Difference vs HOLD | Strategy profit/loss | Fees | Executed legs | Max daily drawdown |
|---|---:|---:|---:|---:|---:|---:|---:|
| weekly | $10,369.53 | $8,021.76 | $2,347.77 | $369.53 | $371.62 | 33 | 39.59% |
| monthly | $9,087.25 | $8,021.76 | $1,065.49 | -$912.75 | $199.46 | 19 | 41.83% |

Both continual replays begin on 2024-12-24 after the shared warm-up. Strategy and HOLD start with identical already-owned units: 20% each BTC/ETH/LINK and 40% CAD. No artificial initial trade fee. HOLD units remain fixed. Strategy trades only on a changed winner; unchanged winners permit weight drift. Signals use prior-day data, execution waits until the next daily close, and each sell/buy incurs the configured costs. Neither run assumes intraday limit fills or known order-book history. Drawdown can exceed the allocation percentage a user might mistake for a loss limit.

Monthly strategy loses money despite beating this HOLD baseline. A positive difference versus HOLD does not mean positive absolute profit or predictive skill.

## Chronological validation and exposed tail

The first 365 observations form the initial training prefix. Then 60-calendar-day evaluation folds use expanding empirical joint horizon-return samples whose labels ended strictly before each review. Labels crossing fold boundaries are excluded from fold summaries. The final 180 historical days are shown separately and were already exposed in earlier replay work. They are NOT an untouched final test.

- weekly: 24 complete decision horizons, mean paired shift advantage -$39.21, observed 10–90% interval coverage 83.3%.
- monthly: 5 complete decision horizons, mean paired shift advantage -$299.53, observed 10–90% interval coverage 60.0%.

These last-period paired results are negative in both scenarios. Each paired comparison starts a fresh identical endowment for shift and HOLD; these per-decision averages are not additive continuous portfolio profits. Monthly folds contain very few complete decisions, and the interval coverage is observed sample coverage, not a calibrated probability. Status remains **unvalidated**.

## Verified invariants

- Replaying a real 600-date prefix produces exactly the same completed chronological decisions as the corresponding prefix of the full real dataset.
- Every training label ends before its decision review date.
- An all-CAD scenario preserves CAD 10,000 in strategy and HOLD with zero trades.
- Earlier verification covered 36 real-data replay combinations: weekly/monthly, lookbacks 14/60/180, allocation 0/60/100%, and fees/slippage 0/1,000 bps. Independent unchanged-unit terminal value and daily maximum drawdown agree.
- Calendar-month clamping handles January 31 to February 29 in leap year 2024.
- TypeScript checks for the research modules and route passed with zero diagnostics. Browser lifecycle/visual checks are tracked separately by the application QA agent; these arithmetic checks do not claim full browser E2E.

## Registered prospective evaluation integrity

Authenticated protocol registration fetches authoritative data server-side and archives source prices, config, actual saved portfolio units and fresh public marks. Client-supplied price/result claims are not stored as evidence. A SHA-256 source hash and compiled evaluator fingerprint are stored before scoring. Each protocol’s future scoring endpoint stays sealed until all required completed observations from the registered 12-calendar-month period exist. The server refuses evaluator-version or fingerprint mismatches, and a database uniqueness constraint permits only one first-opening record per owner/protocol. Original saved results remain viewable.

This is registered prospective evaluation of a frozen rule, not a guaranteed account-wide untouched test. A later protocol can use newly available historical data that overlaps an earlier protocol’s future period, exposing those outcomes through its development report. No account-wide research embargo is implemented. Truly untouched final statistical validation remains an unmet evidence requirement; a frozen-rule future result is useful but does not by itself satisfy that stronger claim.

Every evaluator logic change must bump RESEARCH_VERSION and include every implementation helper in the fingerprint. A compiler transformation can conservatively invalidate the fingerprint even without an intended strategy change; register a new prospective protocol rather than silently replace the old evaluator. An optional deployment commit is recorded when supplied by the deployment environment. Future outcomes and completed independent validation cannot be produced today.

Source SHA-256: `f18debc346fd2816e5a6f0f58b9d54ec28ad86a186a16a655e92bb3be7fb0a48`. Evidence harness evaluator SHA-256: `42aa3b5f2d934b24fc890b5d072e945534600a69d1c45bacc9e685406dd35f06`. The evidence harness and Next server can compile differently, so their executable fingerprints need not match.
