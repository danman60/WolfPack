# WolfPack CAD spot rotation

Status: active extension of the existing application; implementation and acceptance are in progress. This document does not certify live trading or predictive performance.

## Purpose

This exists so that "I'm looking to trade crypto; i just want to know when to shift positions between CAD/BTC/ETH/LINK any pairing in/out looking to only make weekly or monthly trades".

## Requirement sources

- Owner handoff: `/tmp/crypto-rotation-astra-20261012-214732.md`.
- Owner continuation: "Keep building the trading bot/app".
- Later owner direction: full Astra, no local models; complete according to bootstrap with the existing Netcup workshop database.
- Detailed research design: `docs/research/2026-10-crypto-rotation/DESIGN.md`.
- Current execution plan: `docs/plans/2026-10-13-rotation-bootstrap-rebaseline.md`.

The newer database instruction supersedes browser-local portfolio storage. The newer model instruction supersedes broker dispatch. The owner's later "You can deploy I'll mind the funding gate" authorizes deployment after verification; real money, custody and exchange credentials remain a separate gate.

## User and scope

One owner reviews a four-asset spot portfolio. The current deliverable is an authenticated paper workspace backed by Netcup workshop, with explicit demo access for nonfinancial evaluation. Existing perp, LP and wallet evolution behavior remains separate.

The asset universe is CAD, native BTC, ETH and LINK. Do not substitute stablecoins, wrapped BTC, leverage, futures or LP positions. A weekly/monthly review is an opportunity to trade; HOLD is a valid decision and leaves units unchanged.

## Owner journeys

1. Sign in to the rotation workspace or enter its deliberately isolated demo. Required configuration failures are visible. Opening inputs remain empty until the user provides a portfolio name, CAD/crypto quantities, review cadence and trading fee assumption.
2. Create a paper portfolio. Persist original units and starting CAD valuation permanently. Explain that opening crypto basis is the opening paper valuation, not historical acquisition or tax basis.
3. Read genuine public CAD market books with source and retrieval/expiry information. Display unavailable/stale data honestly. No synthetic quotes or silent fallback portfolio.
4. Choose assets and amount for a paper shift. Preview route, received units, fees, residual CAD and expiry before approval. CAD-mediated crypto conversions disclose both legs.
5. Approve exactly that preview. Record one immutable decision and resulting paper balances. Duplicate clicks, stale versions and expired quotes cannot spend twice or silently revise terms.
6. Record HOLD. Units and accumulated fees remain unchanged; the review itself becomes an audit event.
7. See actual CAD value, realized/unrealized paper P/L, fees, external flows, identical-start HOLD value and incremental decision value. Deposits and withdrawals are not profit.
8. Add an explicit CAD deposit or withdrawal. Apply the identical cash flow to the paper strategy and HOLD comparison. Refuse unsupported or unaffordable withdrawals instead of silently selling assets under an invented policy.
9. Reload or use another authenticated browser and recover the server-owned portfolio. Download its ledger for review.
10. Enter research parameters and run an explicitly experimental historical comparison using genuine data, disclosed source/coverage and realistic cost assumptions. Failed data acquisition is an error, never invented history.

## Predictive system requirements

The eventual recommendation engine must rank constrained shifts against unchanged current holdings using the same dated horizon and scenarios. Show expected CAD P/L for shift and HOLD, net incremental benefit, calibrated possible-loss ranges and probability of underperforming HOLD only when the evaluation supports those claims.

A simple historical momentum comparison is a research control, not fulfillment of validated forecasting. Until chronological evaluation and calibration pass, show that forecasts are unavailable. Do not manufacture probabilities, future profit numbers or a recommendation from an LLM confidence score.

Research must use point-in-time data, chronological train/validation/test windows, label-horizon purging, delayed fills, realistic fees/spread/slippage, unchanged-unit HOLD, regime checks and a retained trial history. Freeze numeric promotion thresholds and the final untouched period before reading final results. See the detailed research design for the full protocol.

## Preferences requiring explicit owner input

Actual custody/provider, funded capital and opening holdings, acquisition history, tolerable loss/drawdown, CAD reserve, maximum per-asset allocation, weekly/monthly timing and emergency-review preferences remain owner choices. Paper form inputs do not constitute funded-account authorization.

Ndax is the first direct-CAD public-data candidate. Final exchange choice still requires current Ontario eligibility, account-specific fees, available assets and CAD rails. A connected self-custody option requires separate native-BTC and CAD handling.

## Acceptance and completion boundaries

- Money workflows pass deterministic browser checks against server state and genuine market data.
- Anonymous and cross-owner requests cannot read or mutate another portfolio. Mutations enforce session identity, origin, bounded input, revision checks and idempotency.
- Mobile/desktop composed UI passes visual and measured overflow checks. Source/compiler checks alone are insufficient.
- Readiness reports actual dependency usability and unresolved forecast/live-execution capabilities explicitly.
- No real account, KYC, key creation/import, deposit, order, transfer or swap is part of paper acceptance.
- No live-trading or prediction-success claim without the separate evidence and owner authorization those claims require.

## Non-goals for this extension

Public marketplace, subscription billing, marketing funnel, invented legal entity, payment processor, tax filing and migration of the old futures system. Do not add unrelated bootstrap machinery solely because it exists in a greenfield template.
