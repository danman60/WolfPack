# Allocation workspace verification

The local customer flow passes. A fresh, isolated paper member entered `.1` BTC and `0.1` ETH through the real setup form, saved preferences, viewed all six observed-price charts, saved a forecast, adjusted percentages, applied an allocation, and restored the resulting ledger after reload. The three-order paper batch and its cash/units reconciliation are retained. The final current-source delivery capture shows an explicitly applied HOLD after refreshed public quotes: zero orders and no change to the ledger or its revision. A subsequent manual percentage edit correctly clears HOLD and previews genuine trade legs without applying them.

This verifies paper execution and accounting. No funded order or private exchange connection was exercised. The native execution file currently supplies an interface and an authoritative paper connection, not a signed private exchange adapter.

## Evidence

- Seven arbitrary allocation cases match an independently solved, piecewise linear self-financing equation within CAD 0.000000044. Fees, spread, extra slippage, actual fill quantities, and unchanged-unit comparisons reconcile. Explicit preserve-units HOLD preserves every unit with no trades, including when prices change between recommendation, save and Apply.
- Six genuine-history pairs supply 66 independently calculated technical values. Maximum numerical difference is 4.37e-11. Flat/rising/falling RSI, prior-close zones, malformed/future/gapped data and news attribution controls pass.
- The actual saved 719-close price forecast matches an independent Python augmented least-squares implementation within 3.73e-17. This is numerical agreement, not evidence that its forecasts are reliable.
- Real local API checks reject cross-origin mutations, stale portfolio and batch revisions, and another member’s batch retrieval/apply/advance/check-in. Owner-filtered workspace results exclude the other member’s projection. Duplicate Apply returns the existing batch without duplicating ledger events. Request-body live-mode fields cannot enable funded execution.
- A real paper sequence persisted intent, filled one order, paused, resumed, and cancelled remaining orders. The confirmed fill remained in the ledger; further advancement made no financial change. This is partial batch completion, not a simulated partial exchange fill.
- Actual mouse and Chrome touch gestures from an all-CAD allocation can reach distinct handles, transfer between funded adjacent segments, and autosave without changing actual holdings. Four zero-weight boundary hit targets remain distinct. Exact-percent edits also save.
- The browser shows an honest not-yet-due check-in. Pure fixed-date controls separately verify deposits, withdrawals, a trade one millisecond after the due close, partial/full/not-executed classifications, immutable predictions, and hypothetical versus actual outcomes. A matured live browser check-in has not occurred.
- Final full-page 390 px and 1440 px captures pass measured overflow, clipping, image and contrast checks. Visual review is recorded separately. Earlier gesture captures retained a nested scroll offset; those are not the final delivery images.

## Bounded historical diagnostic

One weekly scenario was declared before running: 60% crypto recommendation budget, initial CAD/BTC/ETH/LINK weights 40/20/20/20, 20 basis points per leg, and 10 basis points adverse execution prices. It used the most recent 719 acquired Coinbase USD closes converted with causal prior-business-day Bank of Canada FX. The same model and allocation engine produced 36 completed forecast cycles across 259 daily valuations. All 36 fits independently match Python. After correcting the real-quote HOLD drift bug, 34 HOLD decisions preserve exact units at their next-close execution time and incur no fees. The earlier replay is retained under `*-before-preserve-units.json`; it is superseded, not erased. Prefix truncation and future-price perturbations leave prior decisions and matured results unchanged. Wealth continues between cycles.

| Comparison | Ending CAD | Maximum drawdown |
|---|---:|---:|
| Adaptive allocation | 9,090.98 | 18.10% |
| Keep identical opening units | 9,779.63 | 23.22% |
| Cash, no interest | 10,000.00 | 0% |

Opening marked capital was CAD 10,000.000545 because initial units use eight decimal places. Modeled trading fees total CAD 19.410235. The strategy lagged unchanged units by CAD 688.65. Lower drawdown did not make this a profitable result. No parameter search or performance gate was used to replace current advice with permanent HOLD.

Historical books were not supplied: the replay uses stated adverse-price assumptions and sufficient depth. Historical sentiment was excluded because no point-in-time archive exists in the supplied study. Current headline tone is a transparent lexical summary with linked, dated sources; missing coverage is unavailable, never a fabricated neutral score. It does not add an invented numerical forecast uplift.

## Final refresh checks

Two genuine 25-second price polls update current marked value without changing the saved pre-Apply forecast. A real workspace refresh preserves the completed batch and an unsaved owner weight draft. Making only the isolated QA browser offline allows the actual quote to expire; stale warnings appear and new advice actions disable. Reconnection restores pricing through the normal automatic poll while the frozen forecast remains unchanged. The five-minute forecast timer is source-reviewed to invoke the same tested callback; a five-minute wall-clock firing is not claimed. Apply expiry controls accept one millisecond before due, and reject the due instant, later times and invalid dates. An explicitly applied, completed zero-order HOLD is classified as fully executed at check-in; an unapplied or after-due HOLD is not.

## Scope and reproducibility

Every mutating browser/API harness requires the explicit local endpoint `http://127.0.0.1:3218/rotation` and rejects production. Login used the ordinary customer authentication path. Cookies and account credentials remain outside the repository. The original reserved isolation member was used only for ordinary login and cross-owner read/rejection checks; its ledger remained unchanged.

The JSON artifacts contain the saved public history, market snapshot, frozen prediction, actual paper fills, mathematical findings, and API results. `CORRECTIONS.md` retains findings and harness mistakes rather than hiding failed first attempts. The final manifest binds source and evidence hashes. The exact matching isolated webpack build and post-build TypeScript check passed; build source manifest SHA-256 is `d10594a3e5710f3495004b4e8531a211b6169cda78a2ca3b946ff1400e632170`. Existing funded wallets and old study records were not modified.
