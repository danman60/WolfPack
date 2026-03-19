# Test Run Checkpoints

## Checkpoint: Flow 01 — Navigation & Page Load
Steps: 11 passed, 0 failed, 0 blocked
Console errors: 9 total (3 favicon/walletconnect non-critical, 2 intel predictions 404, 4 pools subgraph)
Network errors: 2 (intel prediction endpoints 404 — service not deployed)
Ledger entries: 0 rows tracked for cleanup

### Bugs Found
- BUG-01: Settings page shows Kraken description as "Decentralized perpetual exchange (Cosmos)" — should be Kraken-specific description
- BUG-02: Missing favicon (404)
- BUG-03: /intel/predictions/history and /intel/predictions/accuracy return 404

## Checkpoint: Flow 02 — Intelligence Visualizations & Trading
Steps: 13 passed, 0 failed, 0 blocked
Console errors: 2 (same walletconnect + favicon)
Network errors: 0 new
Ledger entries: 0 (watchlist add/remove cycle completed cleanly)

### Bugs Found
- BUG-04: Snoop Signal Feed shows raw JSON `{"type":"sentiment","score":-65}` instead of parsed headline/source format

## Checkpoint: Flow 03 — Backtest, Auto-Bot, Portfolio & LP Pools
Steps: 11 passed, 0 failed, 0 blocked
Console errors: 6 (pools subgraph failures — non-critical)
Network errors: 0 new
Ledger entries: 0

### Oracle Verifications
- Portfolio equity: DB=10015, UI=$10,015.04 — MATCH (minor rounding)
- Portfolio realized_pnl: DB=15.04, UI=+$15.04 — MATCH
- Backtest runs: DB=1 (failed), UI="No results yet" — CONSISTENT
- Auto trades: DB=0, UI=0 active — MATCH
