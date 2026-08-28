# Pre-registration — 2026-08-27
Fixed BEFORE any result was viewed.
- Horizons: 60m and 240m ONLY. Not selected by max-t.
- Cost: measured per-coin from impact_bid/impact_ask. round_trip = 2 * mean((iask-ibid)/mid).
- Split: chronological 70% IS / 30% OOS. Both reported.
- Multiple comparisons: every test counted; Benjamini-Hochberg FDR q=0.10 across ALL tests.
- H1 CARRY: delta-neutral short-perp funding capture is net-positive after costs. Directional: mean(funding)>0.
- H2 FLOW: OI-delta x price-delta quadrant predicts forward return. Directional: crowding(OI+,P+) -> negative fwd; capitulation(OI-,P-) -> positive fwd.
- H3 PREMIUM: premium z-score extreme predicts reversal. Directional: high premium -> negative fwd.
