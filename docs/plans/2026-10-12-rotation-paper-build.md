# Rotation paper application build

**Superseded:** owner subsequently requested bootstrap completion with Netcup workshop, full Astra/no local models, and authorized deployment while retaining the funding gate. `2026-10-13-rotation-bootstrap-rebaseline.md` is the current plan. Browser-local storage and broker/GPU-QA instructions below record the initial slice only; do not execute those superseded instructions.

Purpose: This exists so that "I'm looking to trade crypto; i just want to know when to shift positions between CAD/BTC/ETH/LINK any pairing in/out looking to only make weekly or monthly trades".

Owner authorization: 2026-10-12 Eastern, "Keep building the trading bot/app". Continue the spot design, isolated from existing perp/LP wallets. Real financial actions remain unauthorized. Provider choice, actual capital, risk tolerance and concentration limits remain unknown; the app collects paper inputs rather than inventing these preferences.

## Implementation slice

A functioning `/rotation` paper workspace inside the existing Next app: owner-entered opening balances and cadence, real public CAD market books, persistent paper inventory/events, costed shift previews with explicit approval and expiry, lifetime HOLD benchmark, fees and realized/unrealized CAD P/L, export, and a genuine-data historical research comparison. Historical rule results are experimental; no calibrated forecast or proven alpha claim. Paper data stored on this browser only, visibly disclosed, with download export. A future server ledger and private account integration are separate milestones.

## Reuse gate

Existing code inspected in this session and prior source-backed REUSE-EVIDENCE.md: candle/book interfaces, Kraken adapter, WolfHunt wallet and simulator, portfolio/backtest screens, approval API, wallet connectors. Reuse visual language and chronology/accounting concepts. Old replay is long/short USD; history loader can generate synthetic data; old approval routes execute paper perps. New CAD spot domain is authorized by the owner’s explicit new-system requirements and continuation instruction. No existing wallet's trading logic will be edited.

## Files and acceptance

1. Contracts, exemplar and low-fi design (architect).
   - `app/src/lib/rotation/contract.ts`: asset, market, portfolio, preview and performance contracts plus existing-style vocabulary.
   - `app/src/components/rotation/MetricCard.tsx`: first canonical display exemplar.
   - `docs/research/2026-10-crypto-rotation/paper-workspace-mock.html`: local low-fi preview; capture/review PNG before page code.
   - Acceptance: real exports and bounded numeric inputs; no invented live balances; layout uses existing WolfPack colors, typography and cards.
2. Broker leaves, dispatched against contract/exemplar.
   - `app/src/components/rotation/HoldingsTable.tsx`, `ActivityList.tsx`: presentational only.
   - `app/src/lib/rotation/replay.ts`: pure historical rule comparison only if contract/exemplar ready; no model-selected tuning or synthetic data.
   - Acceptance: scoped compiler gate, read/review actual artifacts, recorded broker lesson. No GPU/model pin or hand-written broker task files.
3. Architect core/data/storage integration.
   - `app/src/lib/rotation/engine.ts`: canonical financial/accounting engine, fixed precision, immutable opening baseline, fill fees and preview/approval rules. This shared multi-export domain implementation stays with architect under route-by-shape policy.
   - `app/src/lib/rotation/storage.ts`: isolated versioned browser persistence, atomic append/revision verification, import validation if implemented; no keys or private account calls.
   - `app/src/app/api/rotation/market/route.ts`: server read-only public CAD books; validate responses/freshness; no fake fallback.
   - `app/src/app/api/rotation/history/route.ts`: genuine public daily data with explicit coverage and completed-bar handling.
   - Acceptance: no negative holdings; conservation and cost reconciliation; stale/insufficient-depth previews rejected; idempotent approval; immutable original benchmark; storage failures do not become success.
4. UI composition (architect).
   - `app/src/app/rotation/page.tsx`, route-scoped styles if needed: opening form, quotes, balances, performance, review/approval, activity, export and historical research.
   - `app/src/components/Nav.tsx`: add Rotation; suppress old circuit-breaker polling and perp selector on this route only; graph impact before edit.
   - Acceptance: full workflow on desktop/mobile, empty/failed data states honest; forecast explicitly unvalidated; no live-execution control.
5. Verification and review.
   - Written checklist `tests/agent/flow-rotation-paper.md` with explicit localhost target, independent expected cash/fee/benchmark scenarios, refresh/replay protection and mobile interaction.
   - Use QA Agent for browser testing, reserve GPU via broker/gpu-borrow as needed. No production endpoints or arbitrary test orders.
   - Run compiler/build in subagent, distinguish baseline failures, inspect source/diff, review screenshots and measured overflow/contrast. Approval/send screenshots only after review under standing instructions.
   - Update CURRENT_WORK with actual completion, limitations, broker task IDs and exact validation.

## Boundaries and risks

- This browser-local paper ledger is useful for proving the workflow, but is not a secure or durable live-money system. Actual custody/auth/private-account reconciliation require the server phase.
- Research fees and simple-rule parameters must be explicit in UI/reports; not owner risk defaults. No fabricated predictive confidence or extrapolated profit.
- Do not start the old intelligence service. Public data APIs are read-only; all simulated trades stay local.
- Preserve prior uncommitted investigation/transcription files. No broad staging or commits while broker is writing; no deployment-triggering push.

## Progress

- Startup live HEAD/status inspected; dependencies and graph navigation checked; source reuse investigation running. Broker live state reports pending work and occupied/reserved cards; tasks queue normally without interrupting owners.
