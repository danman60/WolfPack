# R4: EMA Parameter Optimization

## Research Question
Are 20/50 periods optimal for the EMA crossover strategy?

## Methodology
Testing 25 parameter combinations:
- fast periods: [8, 12, 15, 20, 25]
- slow periods: [30, 40, 50, 60, 80]

Backtest parameters:
- Symbol: BTC
- Exchange: Hyperliquid
- Interval: 1h candles
- Period: 30 days (2026-04-01 to 2026-04-30)
- Starting equity: $25,000
- Commission: 5 bps
- Slippage: 5 bps
- Max position: 25%

## Results
*Results will be populated after running all 25 backtests via the API.*

| fast_period | slow_period | Return % | Sharpe | Max DD % | Trades | Win Rate |
|-------------|-------------|----------|--------|----------|--------|----------|
| 8 | 30 | TBD | TBD | TBD | TBD | TBD |
| 8 | 40 | TBD | TBD | TBD | TBD | TBD |
| 8 | 50 | TBD | TBD | TBD | TBD | TBD |
| 8 | 60 | TBD | TBD | TBD | TBD | TBD |
| 8 | 80 | TBD | TBD | TBD | TBD | TBD |
| 12 | 30 | TBD | TBD | TBD | TBD | TBD |
| 12 | 40 | TBD | TBD | TBD | TBD | TBD |
| 12 | 50 | TBD | TBD | TBD | TBD | TBD |
| 12 | 60 | TBD | TBD | TBD | TBD | TBD |
| 12 | 80 | TBD | TBD | TBD | TBD | TBD |
| 15 | 30 | TBD | TBD | TBD | TBD | TBD |
| 15 | 40 | TBD | TBD | TBD | TBD | TBD |
| 15 | 50 | TBD | TBD | TBD | TBD | TBD |
| 15 | 60 | TBD | TBD | TBD | TBD | TBD |
| 15 | 80 | TBD | TBD | TBD | TBD | TBD |
| 20 | 30 | TBD | TBD | TBD | TBD | TBD |
| 20 | 40 | TBD | TBD | TBD | TBD | TBD |
| 20 | 50 | +2-3% | 5+ | TBD | TBD | TBD |
| 20 | 60 | TBD | TBD | TBD | TBD | TBD |
| 20 | 80 | TBD | TBD | TBD | TBD | TBD |
| 25 | 30 | TBD | TBD | TBD | TBD | TBD |
| 25 | 40 | TBD | TBD | TBD | TBD | TBD |
| 25 | 50 | TBD | TBD | TBD | TBD | TBD |
| 25 | 60 | TBD | TBD | TBD | TBD | TBD |
| 25 | 80 | TBD | TBD | TBD | TBD | TBD |

## Top 3 on BTC → ETH Validation
*Will run top 3 BTC winners on ETH to check generalization.*

## Conclusions
*Pending results analysis.*
