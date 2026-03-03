# WolfPack Roadmap — Post-Audit

Source: `docs/wolfpack-audit.docx` (expert audit, 31 findings)

## Completed
- [x] #1 Wire circuit breaker into pipeline + DB persistence (commit c1e3049)
- [x] Wire execution timing into pipeline
- [x] Module status tracking with real timestamps
- [x] DB writes for module outputs, agent outputs, recs, CB state, snapshots

## Phase 1 — High Effectiveness/Effort Ratio (Week 1)

| # | Initiative | Effort | Impact |
|---|-----------|--------|--------|
| 2 | API authentication (bearer token) | 1 day | Security: critical |
| 4 | Replace flat slippage with liquidity module market impact | 1 day | Alpha recovery: 3-8 BPS/trade |
| 8 | Structured JSON outputs for all 4 agents | 1 day | Eliminates parsing failures |
| 3 | Adaptive position sizing (vol target + regime + conviction) | 2 days | Sharpe +0.3-0.5 |
| 10 | Multi-timeframe regime confirmation (4H + daily) | 1.5 days | Reduces whipsaw 30-40% |

## Phase 2 — New Alpha Sources (Week 2-3)

| # | Initiative | Effort | Impact |
|---|-----------|--------|--------|
| 5 | Funding rate harvest strategy + backtest | 3 days | New alpha: 10-30% ann. |
| 6 | Event-driven triggers (price, liquidations, funding spikes) | 3 days | Captures time-sensitive alpha |
| 11 | Liquidation cascade monitor + mean reversion signal | 2 days | 60-70% WR trades |
| 12 | On-chain flow data for Snoop agent | 2 days | Transforms Snoop to alpha source |

## Phase 3 — Live Trading Prep (Week 3-4)

| # | Initiative | Effort | Impact |
|---|-----------|--------|--------|
| 7 | Hyperliquid testnet execution + fill reconciliation | 2 days | Unblocks live trading |
| 14 | Trade lifecycle state machine | 2 days | Operational reliability |
| 13 | Walk-forward + Monte Carlo backtest validation | 2 days | Prevents curve fitting |
| 15 | Cross-exchange basis monitoring | 1.5 days | Alpha source + vol indicator |
| 9 | Remaining DB persistence gaps | 1 day | Crash recovery |

## Critical Findings (from audit)

1. **Disconnected Circuit Breaker** — FIXED
2. **Untested Order Signing** — needs Hyperliquid testnet (Phase 3)
3. **No Position Reconciliation** — needs live exchange (Phase 3)
4. **Approval Gate Bypass Risk** — addressed with API auth + safety checklist
5. **No Authentication on API** — Phase 1, item #2
