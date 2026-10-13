# Automated adaptive selector — actual retrospective evidence

**Result: HOLD for both weekly and monthly QA scenarios.** The continuous adaptive selector lost to unchanged holdings and costed CAD. Favorable training leaders did not pass the evidence gates. No profitable strategy or validated advice was established.

Run from the current public history endpoint, October 13, 2026 Eastern. Source: 719 exact matched completed Kraken daily observations, 2024-10-24 through 2026-10-12. LINK/CAD derives from matching LINK/ETH × ETH/CAD closes. Source SHA-256: `f18debc346fd2816e5a6f0f58b9d54ec28ad86a186a16a655e92bb3be7fb0a48`. Every date was already exposed; chronological calculation does not create an unseen test.

Explicit **QA scenario**, not owner preferences: CAD 10000 capital, 60% target crypto allocation when shifting, 20 bps fee per leg, 10 bps adverse slippage. Both weekly and calendar-monthly schedules evaluated. The app supplies no defaults for unknown owner capital or allocation.

| Continuous outer selector | Weekly | Monthly |
|---|---:|---:|
| Ending CAD value | 6,122.51 | 7,676.82 |
| Unchanged HOLD | 8,206.49 | 8,206.49 |
| Costed CAD | 10,002.68 | 10,002.68 |
| Difference versus HOLD | -2,083.97 | -529.67 |
| Difference versus CAD | -3,880.17 | -2,325.87 |
| Fees CAD | 177.17 | 68.18 |
| Gross turnover CAD | 88,585.13 | 34,087.82 |
| Executed legs | 25.00 | 9.00 |
| Maximum daily drawdown % | 43.42 | 34.08 |
| Completed outer horizons | 50.00 | 11.00 |

Outer evaluation: 2025-10-24 through 2026-10-12. Both paths begin with the same CAD4000 plus CAD2000 each in BTC/ETH/LINK. Costed CAD sells those opening crypto units at the next observed close and pays three sell-leg fees; its CAD10002.68 includes market movement before liquidation, not cash interest. The outer selector never resets its wealth at a block boundary.

Exactly five predefined candidates: 14/30/60/90/180-day positive momentum; no other windows, allocation levels or schedules were optimized. Training scores are the smaller after-cost advantage over HOLD and costed CAD on common dates beginning 2025-04-23. Every 60-day outer block chooses using only the earlier prefix. Nonpositive scores select HOLD. Same-target reviews preserve units and weight drift. The adopted policy is the full adaptive selector, not its final winning lookback.

| Outer block starts | Weekly choice | Monthly choice |
|---|---|---|
| 2025-10-24 | hold | momentum-90 |
| 2025-12-23 | momentum-60 | momentum-30 |
| 2026-02-21 | momentum-90 | momentum-90 |
| 2026-04-22 | momentum-90 | momentum-90 |
| 2026-06-21 | momentum-14 | momentum-90 |
| 2026-08-20 | momentum-14 | momentum-90 |

Five blocks are complete; the last is partial. The latest plan retains the selection trained through 2026-08-19 for its current block. New data appends to the original archive; dropping old bars would silently move the selection schedule and is forbidden for the same adopted policy.

Gate: at least three complete 60-day blocks and twelve complete non-overlapping review horizons, positive outer net edge over both baselines, positive current-block inner score and positive current paired historical mean advantage. These are **engineering evidence gates**, not statistical significance, calibrated confidence or maximum-loss limits. Monthly has only eleven complete outer horizons. Both schedules fail the outer edges and current paired mean gate. HOLD returns null target weights and retains current units; it does not liquidate into CAD.

Candidate hypothetical outcomes retained for explanation:
- Weekly: hypothetical CAD candidate, 76 earlier complete samples; mean shift CAD-45.64, HOLD CAD26.80, paired advantage CAD-72.44, advantage p10 CAD-511.76 / p90 CAD386.48. Horizon 2026-10-13 → 2026-10-20. This rejected candidate scenario is not the HOLD instruction.
- Monthly: hypothetical LINK candidate, 17 earlier complete samples; mean shift CAD89.83, HOLD CAD133.19, paired advantage CAD-43.37, advantage p10 CAD-423.22 / p90 CAD533.36. Horizon 2026-10-13 → 2026-11-13. This rejected candidate scenario is not the HOLD instruction.

Verification: eleven acceptance groups pass. Twenty-four real-history prefix runs preserve every earlier inner score, block choice, review signal and candidate/outer equity point. Independent HOLD marks and next-close costed-CAD calculations reconcile at every date. Fees reconcile to gross turnover × fee rate; observed daily drawdown recomputes from curves. Both 180-day candidate curves match the existing v1 replay, including fees and trade counts. Thirty-six real-history boundary scenarios (zero/full allocation, zero/high fees/slippage) stay finite and nonnegative; zero allocation creates no trades. Inputs are not mutated and repeated runs are identical.

Reproduce without network or database writes: compile `app/src/lib/rotation/strategy-study.ts` and its imported modules to an explicit CommonJS output directory, then run `node automated-selector-evidence.cjs COMPILED_ROTATION_DIR HISTORY_JSON OUTPUT_JSON`. Full numerical archive, five candidate curves, all inner trial scores, outer reviews/curves, source/fingerprint hashes and verification checks: `automated-selector-evidence.json`. The runner is a standalone CPU evidence check, not a webapp unit-test suite.

Separate longer-history strategy-discovery work belongs to another owner session and is neither modified nor claimed by this report. UI/API integration and browser acceptance are separate from these pure-evaluator checks.

Current plan cadence is separately enforced: weekly next review is 2026-10-16; monthly is 2026-11-01. The current 2026-10-13 snapshot is HOLD between reviews, in addition to its failed performance gates. Six scenarios at actual October 1/2/3 dates verify monthly/weekly due dates, same-Eastern-day exclusion, and unchanged historical curves. Stale data that does not reach the prior day fails rather than issuing advice.

The earlier CAD10369.53 result is a different experiment: one fixed 60-day rule starting 2024-12-24, with its own HOLD at CAD8021.76. This adaptive outer policy starts 2025-10-24 after the training prefix and switches windows using earlier scores. Different policy, starting dates/prices/units and review anchors make those end balances unsuitable for a direct ranking.
