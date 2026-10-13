# Saved projection and check-in cycle

Owner approved the allocation mockup and clarified: "Changing the allocation should then show a projected profit increase of the portfolio and then upon projection, save that increase and then measure that at the next check-in whether it was accurate or not. And that is how the previous back testing to generate recommendations should work."

## Product behavior
1. Dragging the proposed pie recomputes expected ending portfolio value and profit after costs. Show the extra gain/loss compared with leaving the exact starting holdings untouched over the same horizon. Forecast benefit can be negative or zero; never manufacture an increase.
2. Commit the proposed scenario and save a fixed forecast with as-of time, check-in date, model version, starting units/prices/value, proposed weights, asset-return forecasts, fees/slippage assumptions, expected total profit and expected advantage over unchanged holdings. Keep old saved forecasts intact; a refresh is a new forecast.
3. At check-in, value actual holdings and the matched unchanged-holdings baseline using prices from that date. Compare realized total profit and incremental profit with the saved predictions. Show the difference in CAD plainly. Cash deposits/withdrawals are matched in both portfolios and do not count as profit.
4. Record whether the planned reallocation was fully executed, partly executed or not executed. A forecast about a target allocation cannot be graded as an executed investment if the owner did not make those trades. Its hypothetical price-path result and the actual account result remain identifiable.
5. Use these saved forecast/outcome records to measure forecasting error and inform later recommendations.

## Backtesting uses this same sequence
At each historical review use only the data and completed training outcomes then available. Generate the recommendation and forecast from that prefix; save it before seeing the next period. Carry units and trading costs forward without resetting wealth. At the historical check-in evaluate the frozen forecast using subsequently observed prices and compare with the matched starting-holdings baseline. Repeat at each review; strategy/predictions/allocations can adapt using matured past outcomes. No hindsight choice or replacement of an inaccurate forecast. If historic sentiment inputs are unavailable, do not pretend they were known then.

## This mockup revision
Illustrative weekly returns BTC+4%, ETH+2.5%, LINK-1.5%, CAD0. StartingCAD25000 at40/20/20/20 gives projectedHOLDprofit450. Proposed50/25/10/15 gives grossprofit618.75; modeled6250 turnover at20bps fees plus10bps slippage costs18.75, yielding netprofit600 and projectedextra150.

Illustrative check-in returns BTC+3.5%, ETH+1.5%, LINK-2%, CAD0 give unchangedHOLDprofit325 and targetprofit462.50 after the same costs. Actualextra137.50 versus projected150: the estimate was12.50 too high. This is a demonstration of the cycle, not historical or future market evidence.

Prototype revision only; the approved layout is preserved while adding this cycle. Existing production implementation is not represented as having these new features.
