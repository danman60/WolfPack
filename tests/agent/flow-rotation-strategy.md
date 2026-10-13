# Integrated paper strategy acceptance

Explicit target: `http://127.0.0.1:3218/rotation`. Stable production is refused. Use the reserved synthetic isolation account from the private fixture file. Real public CAD history/order books and the workshop `wpr_` database only. No inference, mocks, local storage seeding, live orders, or reset of existing ledgers.

1. Sign in through the real form. Verify server readiness identifies paper-workshop and live trading disabled.
2. Enter explicit QA assumptions: 60% target crypto allocation when shifting, 10 bps adverse slippage. Cadence, fees, current holdings come from the saved portfolio.
3. Click **Backtest & build my plan**. Confirm all five windows (14/30/60/90/180), chronological outer evidence and retrospective-unvalidated status. The financial ledger must remain identical.
4. Click **Use this strategy**. Confirm plan revision increases separately from financial revision. Current recommendation references the adopted study, portfolio revision and immutable evidence.
5. Confirm Shift, HOLD and Shift-minus-HOLD mean CAD amounts and downside are present; reconcile mean difference independently. If evidence rejects SHIFT, label the candidate hypothetical and recommend unchanged units.
6. Follow the real decision: recommended HOLD preserves all balances/baseline/fees/flows; SHIFT opens the existing recommendation-bound fresh quote without automatically trading; blocked remains distinct from HOLD.
7. A changed financial revision invalidates the previous recommendation. Refresh derives a new recommendation. Repeated refresh does not silently execute anything.
8. Reload. Confirm plan/recommendation restore and complete export retains study/recommendation evidence. Existing Advanced research stays accessible.
9. Capture 390px/1440px full workspace. Measure overflow, clipped text, contrast and images; manually review both. Retain screenshots for parent review before delivery.

Runner: `python3 tests/agent/rotation-strategy-qa.py --url http://127.0.0.1:3218/rotation --account-file <private fixture> --report-dir <private output>`.

Limits: a real HOLD dataset proves HOLD behavior. It does not prove the recommendation SHIFT branch executes; do not manufacture market data or call that branch tested. Engine runtime probes cover identity/revision protections separately.
