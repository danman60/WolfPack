---
name: Live money cutover plan
description: User plans to switch from paper to real funds (~$1K) after ~1 week more monitoring. Expects same growth. MetaMask wallet for LP, Hyperliquid for perps.
type: project
---

Live cutover planned for ~2026-04-13. Starting capital ~$1K.

**Why:** Paper trading showing edge (perp +$723/6h, LP +$23 fees). User wants real returns.

**How to apply:** All code changes should consider live execution path. Position sizing must scale to $1K. Gas cost analysis critical for LP on L1 vs L2. Build the live execution layer incrementally alongside paper — don't wait until cutover day.
