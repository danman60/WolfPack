# Actual paper cross-conversion acceptance

5 acceptance groups passed on October 12, 2026, 11:25 p.m. Eastern against the immutable [release preview](https://wolf-pack-n8aij5nb4-danman60s-projects.vercel.app/rotation). Three manual UI approvals, five real public-orderbook legs, zero browser console errors. Separate authorized synthetic account; existing opening, HOLD baseline, cash flows and ledger events preserved. No portfolio reset, live exchange order, or production harness.

| UI paper shift | Received | CAD fees | Saved revision |
|---|---:|---:|---:|
| 0.001 BTC → ETH | 0.032966 ETH | 0.47086827 | 4 |
| 0.032966 ETH → LINK | 6.3209 LINK | 0.46640449 | 5 |
| 6.3209 LINK → CAD | 115.44112506 CAD | 0.23134494 | 6 |

Total new fees: **1.16861770 CAD**. Both crypto-to-crypto conversions used independently reconciled sell/buy CAD legs, with 20 bps charged on each leg. Python Decimal independently walked the captured public depth and verified adverse rounding, gross amounts, fees, resulting balances and nonnegative cash. Neither cross conversion spent unrelated existing CAD. Every approved server event retained the exact preview ID, existing event prefix remained identical, and revisions advanced once per approval. Reload returned exactly the final authoritative portfolio.

Original HOLD units remained CAD 10100, BTC 0, ETH 0, LINK 0 throughout. Ending actual balances: CAD 9215.44468747, BTC 0.00742197, ETH 0, LINK 0. This confirms the requested route coverage; it is not exhaustive testing of all 12 directed asset pairs.

The first two attempts stopped before approvals due to harness assumptions, not an application failure: a synthetic ordinary-login fixture has demo=false, and a Python short-circuit prevented Playwright response-event dispatch until a browser RPC. Both corrections are documented in the successful run diagnostics.

`preview-pairs.json` retains the sanitized checks, initial ledger, three actual quote/public-market payloads and all three authoritative post-approval portfolios. No credentials or cookies are included. Screenshots and accessibility snapshots remain under `/tmp/wolfpack-rotation-preview-pairs-3/`. Final full-page ledger and both visible cross/exit previews were directly reviewed for readability and composition; the first viewport screenshot ends above its approval preview, whose text and exact payload were separately captured.

Harness: `tests/agent/rotation-pairs-qa.py`, using the existing QA Agent WebExecutor and explicit immutable-preview target guard.
