# Independent paper sizing review

Six of six CPU scenarios passed against genuine Ndax public CAD books captured October 13, 2026, 10:26:40 a.m. Eastern. Exact capture timestamp and hashes are in `strategy-step-review.json`. Actual application modules were loaded; no generated prices, mock exchange, auth/database writes or live exchange orders.

- CAD buy to 60% BTC: one step; final target fraction 0.5999999772625803.
- Overweight BTC sale to 60%: one step; final fraction 0.6000000069673477.
- Mixed inventory to 60% ETH: three steps; final fraction 0.5999997657063991.
- Mixed inventory to CAD: three steps; final fraction 1.
- Below-minimum BTC dust: HOLD, zero steps/fees; original dust retained.
- Oversized buy exceeding actual captured depth: blocked, zero steps/fees.

Every approved in-memory leg had its fee ceiling independently checked with integer arithmetic. Original HOLD balances stayed identical; resulting inventories stayed nonnegative. These explicit QA targets exercise the sizing helper. **This is pure CPU verification, not recommended-SHIFT browser end-to-end acceptance or evidence that the selector recommended a trade.** The current actual backtests remain HOLD.

Files: `strategy-step-review.json` (decisions, amounts, fees and assertions), `strategy-step-review-public-books.json` (genuine source snapshot), `strategy-step-review.cjs` (runner). Run with explicit app root, a freshly retrieved genuine public-book JSON and output path. Old archived books deliberately fail the application's expiry guard; do not disable that guard to rerun.

Independent source review confirms cumulative adopted history uses the latest archived extension and fresh previews resize the frozen target against current books. Expiration/supersession of an unfinished target at the next review is verified: expired partial targets are discarded before the HOLD/completed check, preventing a partial allocation from being falsely marked complete. Recommendation expiry is capped at the review cutoff and checked before quoting/approval. Four independent executions of the actual conversion block resolved November 1, 2026, March 14, 2027, March 8, 2026, and October 20, 2026 to exactly 00:00 Eastern. Initial sizing and final reviewed source hashes are retained separately.
