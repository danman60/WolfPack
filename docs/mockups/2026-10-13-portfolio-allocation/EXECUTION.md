# Apply executes the approved allocation

Owner: "clicking apply should fire off the individual trades in programmatic sequences cheaply as possible".

Apply is one authorization for the displayed complete rebalance, rather than requiring separate approval for every leg. The plan must show estimated complete costs first and retain the saved profit projection. After Apply, choose the lowest estimated all-in cost among markets and routes supported by the connected account: fees, spread, slippage/depth and any applicable transfer costs. Do not pretend each analytical pair is an executable market. Do not claim an unknowable absolute minimum fee or force maker-only orders that may never fill.

Execute in dependencies: release required funds with sells, confirm fills, then buy. Reprice remaining orders from actual proceeds; keep amounts within funds, minimums, precision and the agreed cost/slippage limits. Each intent/order has a unique id so retries and double clicks cannot create duplicate trades. Fill history and actual costs attach to the frozen projection. A failed/partial order pauses the plan, preserves executed fills and exposes unfinished work; do not silently restart, roll back market trades or submit unfunded dependent orders.

At the next check-in compare actual executed holdings and costs with the immutable original projection and matched starting-holdings baseline. Partial/unexecuted plans are identified separately. Forecasts can change next period; old projections cannot be rewritten.

This prototype simulates the sequence only. Available illustrative execution markets are CAD pairs. Approved example: sell125LINK (CAD2500gross,7.50modeledcost), buy0.025BTC (2500notional,7.50cost), then0.5ETH (1250notional,3.75cost). Final illustrative units BTC0.125,ETH2.5,LINK125,CAD3731.25; total24981.25 after18.75cost. No exchange credentials, funded orders or production code are touched.
