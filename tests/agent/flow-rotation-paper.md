# Rotation paper workspace — local browser acceptance

Run only against explicitly supplied `http://127.0.0.1:3218/rotation`.
Use QA Agent's `WebExecutor` with deterministic steps and assertions; no model inference.
Fresh isolated browser context. Real workshop demo session; no exchange credentials, legacy routes or production endpoints. Server API reads supply the independent ledger oracle; browser localStorage is not authoritative.
The amounts below are disposable QA inputs, not owner portfolio preferences.

- [ ] At desktop width, opening screen shows a paper-only workspace and genuine public market data or a clear unavailable state. No fabricated prices, forecasts or saved portfolio appear.
- [ ] Enter CAD 10000, BTC 0, ETH 0, LINK 0, fee 20 basis points and weekly review. Create the paper portfolio explicitly.
- [ ] Opening units and initial HOLD units match. Initial actual and HOLD values equal CAD 10000. P/L and decision value are zero.
- [ ] Preview a CAD 1000 to BTC shift. Preview discloses units, fees, route and expiry. Holdings remain unchanged before approval.
- [ ] Approve the paper shift. CAD declines by the approved spending, BTC increases by the approved receipt, exact quoted fees enter the ledger once, and initial HOLD stays CAD 10000 with zero crypto.
- [ ] Repeated submission of the same approved action cannot append a second fill or spend again. Use the visible action while pending/settled; no artificial storage injection.
- [ ] Record HOLD. Units and accumulated fees remain unchanged; an explicit hold decision appears in history.
- [ ] Reload and reauthenticate. Portfolio identity, balances, frozen opening units, HOLD units and ledger persist from the server; a second owner cannot read this portfolio.
- [ ] Deposit CAD 100 into paper portfolio. Actual and HOLD cash both rise by CAD 100, net external flows rise by CAD 100, and flow-adjusted P/L does not gain CAD 100. Compare both states under the same mark snapshot.
- [ ] Attempt a CAD withdrawal above available cash. A clear error appears and balances, HOLD units and ledger remain unchanged.
- [ ] Export the ledger. Downloaded JSON preserves portfolio identity, opening units, holdings, external flows and all recorded events.
- [ ] Enter all research inputs explicitly: CAD 10000, weekly cadence, lookback 30 days, allocation 50 percent, fee 20 basis points, slippage 10 basis points. Run research against real historical data.
- [ ] Research shows source, actual coverage, disclosed rule and costs, HOLD comparator, and limitations. If source/coverage fails, show the concrete data error without fabricated results.
- [ ] At mobile width 390, inspect composed page for horizontal overflow, clipped text, table containment, readable labels and reachable controls. Capture held screenshots at mobile and desktop widths.
- [ ] Browser console has no application exceptions. Network evidence contains only localhost application requests and explicitly public quote/history sources; no legacy `/intel/` or private trading call.

## Authorized immutable preview

The harness requires an explicit URL. `--workshop-preview` permits only an immutable `wolf-pack-<deployment>-danman60s-projects.vercel.app/rotation` address, then verifies authenticated readiness reports paper-workshop mode and live trading disabled before paper writes. Stable production aliases remain refused. The same verified preview artifact may be promoted; production smoke remains read-only.
