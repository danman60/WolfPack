# Crypto rotation investigation and design

Date: 2026-10-12, Eastern. Scope: investigation and design only.

This exists so that "I'm looking to trade crypto; i just want to know when to shift positions between CAD/BTC/ETH/LINK any pairing in/out looking to only make weekly or monthly trades".

Owner source: `/tmp/crypto-rotation-astra-20261012-214732.md`. Preserve the four assets, HOLD, owner approval, CAD accounting, and action-versus-no-action comparisons. Provider, capital, risk and allocation preferences remain owner decisions.

## Deliverables and acceptance checks

1. Verify context and reusable implementation.
   - Read live HEAD/status, bounded project context, source behind graph navigation, and wallet state read-only.
   - Inspect WolfPack and WolfHunt for wired, dormant and embedded execution, data, backtest, accounting and wallet implementations.
   - Accept when reuse claims have file/line provenance and source limitations; failed wallet queries are recorded without claiming wallets disappeared.
2. Verify provider choices.
   - Read current Ontario regulator decisions and exchange documentation; query public market metadata and quotes.
   - Compare Ndax, Kraken and self-custody with actual CAD rails, native assets, API permissions, account requirements, routing and costs.
   - Accept when every factual provider claim has a primary source; distinguish public capability from untested account-specific permissions and executable quotes.
3. Write reviewable design and backtest protocol.
   - Files: `docs/research/2026-10-crypto-rotation/DESIGN.md`, `PROVIDER-EVIDENCE.md`, `REUSE-EVIDENCE.md`, `public-market-evidence.json`; update `CURRENT_WORK.md` with a bounded new-session entry.
   - Specify isolated spot accounting/execution, explicit approval, no-action baseline, paired recommendation counterfactuals, costs, chronological validation and calibrated estimates.
   - Accept when each owner requirement maps to a concrete behavior or explicitly unresolved owner decision. No fabricated return or confidence claim.
4. Review deliverables.
   - Check sources, asset identity, fee assumptions, links and git diff. No application build needed for documentation.
   - Report provider recommendation, reuse boundary, evaluation gates and unresolved preferences.

## Future implementation gates (proposed, not launched)

1. Owner selects custody/provider, portfolio starting state/capital, risk/allocation constraints and review cadence. Confirm whether the requested wallets mean asset balances, funded strategy accounts, or paper experiments.
2. Validate chosen account's accessible markets, fee tier, permissions, jurisdictional limits and reconciliation using read-only access. Separate new credentials/storage from the old futures service.
3. Audit data coverage and freeze a data manifest, split dates, trial budget, benchmarks, costs and pass criteria before any strategy fitting. Research on capital scenarios is allowed only when visibly labeled as scenarios.
4. Build the isolated ledger and identical-input HOLD comparison; replay real historical market data and externally specified flows. Acceptance: balance conservation, fees charged once, deposits never reported as profit, reproducible comparison.
5. Run bounded CPU walk-forward studies; any bulk model/GPU work must use the broker/gpu-borrow. Accept predictive claims only from unseen periods and measured calibration.
6. Implement review UI and paper execution with real public prices; browser QA against an explicit non-production endpoint. Demonstrate duplicate clicks, expired quotes, partial fills, reconnects and reconciliation.
7. Any real account funding, keys, transfers, orders, deployments or trading-policy changes require subsequent explicit authorization. Existing wallet policies are outside this project's authorized changes.

## Execution notes

- 2026-10-12: steps 1–2 underway; only read-only queries and research documents. A single repository-evidence worker handles long exploration under the standing AGENTS instruction; no implementation or bulk inference delegated.
- Public Ndax instruments confirm BTC/CAD, ETH/CAD and LINK/CAD. Kraken public metadata confirms BTC/CAD, ETH/CAD and crypto cross pairs. An API response is capability evidence, not a funded-account execution test.
- Current OSC platform list links August 18, 2026 amendments for both providers; use these with the underlying decisions rather than relying on older support-page lists alone.
- No historical backtest or model training has been run in this investigation.
- Investigation steps 1–4 completed: reuse/limitations documented, provider sources and public market metadata checked, architecture/accounting/backtest design written, document links and evidence JSON validated. Wallet-state lookup remains explicitly unresolved; owner preferences remain unassigned parameters.
- Review: 4 Markdown deliverables, 8 public instrument records and 8 quote snapshots. Local links resolve; JSON parses; whitespace/diff checks pass. No application tests/build are applicable to this documentation-only change. WolfHunt working tree remained clean.
- Documents intentionally remain local for review. No commit/push that could trigger deployment; launch scope prohibits production deployments.
