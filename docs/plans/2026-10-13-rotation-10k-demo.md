# CAD10,000 example demo

This exists so that "Populate an example demo portfolio 10K value so I can just jump in".

Scope: reuse existing isolated rotation demo identity, portfolio ledger, settings and page. One click opens a populated example with working pie/sliders/charts/projection. Preserve existing portfolios, old wallets, dirty files and processes. No funded orders. Rough effort20–40minutes, reversible app changes. Cheapest probe: live HEAD/status and existing session/demo/create routes read before implementation. Prior owner live release authorization persists.

## 1. Backend — strategy_runner

Extend existing demoSignIn/session POST and reuse createPortfolio/commitPortfolio/saveAllocationSettings. Signed-out demo action seeds a new demo if no portfolio. Explicit Open CAD10,000 example from an authenticated account creates a fresh isolated demo identity, preserving the prior account's records. Never replace an existing portfolio. Prepare current public books before switching session; return actionable failure if unavailable.

Illustrative opening allocation: BTC40%,ETH20%,LINK20%,CAD20%. Derive coin units from actual Ndax midpoint quotes with existing eight-decimal arithmetic and venue increments. Put quantity-rounding residual in CAD so opening marked equity is exactly CAD10,000. Freeze opening books/units/example provenance in existing wpr_trials. Use clearly identified editable example defaults: weekly review,20bps fee,10bps extra slippage,80%crypto recommendation budget. This is example configuration, not a claim about owner preferences or profitable strategy. Seed settings without depending on history/news availability. Retry after partially completed setup must safely finish the same seed/settings; double clicks cannot overwrite or duplicate financial records.

Acceptance: exact10,000 opening equity at captured marks; four positive holdings; ordinary authentication/owner RLS; no existing-portfolio mutation; reload stable; defaults present; offline/source failures do not overwrite current records. App value may move with real prices after opening.

## 2. Frontend — spot_history

Extend current page's demo button to Open $10,000 demo. Add Open $10,000 example for authenticated setup/workspace so an existing visitor can jump into a fresh example. Adopt successful server-returned session/portfolio/market, bypass all starting-point and preference forms. Existing manual portfolio setup remains available. Show concise example label/starting value and editable assumptions. Pie/sliders/profit/chart behavior unchanged.

Acceptance: one click to populated allocation; no manual fields or blank preferences; amounts are real-price-derived; sliders immediately work; old account data remains intact;390/1440 composed screenshots pass mechanical and visual review.

## 3. QA and release — research_protocol, root and strategy_runner

Graph affected before edits; reuse wired/dormant/embedded paths. QA Agent on explicit local/true Git Preview only for mutations: signed-out demo, authenticated fresh example, existing-account preservation, exact opening/decimal quantities/settings, duplicate/retry behavior, slider/profit/save/reload. Production verification read-only; no synthetic financial write tests against production. Isolated build/TypeScript in agent. Root reviews screenshots/security/diff, commits scoped files, pushes immediately. Verify true Preview then deploy same clean source as Production --skip-domain, read-only verify and assign exact stable alias. Reviewed final screenshots privately DM under owner request.

Acceptance: relevant browser/accounting checks and build pass; exact released source/artifact recorded; original dirt/processes preserved; CURRENT_WORK and durable context updated. Native exchange choice remains separately pending and does not block this example.

## Execution and preservation detail

Implemented and locally verified: backend five-file scope, exact captured-mark opening, saved preferences, atomic prepared response and UI adoption. A minimal HttpOnly previous-session backup and Return to previous workspace control retain access to anonymous demo accounts when opening another example. Repeated switches retain the original backup; ordinary login/logout clear it. Return validates actual GoTrue identity and workspace membership before changing active cookies. No JWT reaches JavaScript. This extends account preservation without introducing account management or tables.

Local QA, independent eight-decimal accounting, isolated webpack build and post-build TypeScript passed. Captured composed390/1440 screenshots passed measured checks and root visual review. External-source failure ordering source-reviewed; no manufactured market outage or production financial writes. Exact Preview and Production release verification remain next.
