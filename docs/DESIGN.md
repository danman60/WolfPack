# Rotation workspace design

Existing-project extension. Reuse WolfPack's shell and style vocabulary; do not scaffold a replacement application.

## Purpose

This exists so that "I'm looking to trade crypto; i just want to know when to shift positions between CAD/BTC/ETH/LINK any pairing in/out looking to only make weekly or monthly trades".

## Visual system

- Typeface: existing Geist sans for interface text and Geist Mono where precision helps.
- Existing backgrounds: `--background`, `--surface`, `--surface-elevated`; existing borders and radii.
- Emerald identifies the main action and positive state; amber conveys incomplete research or stale data; red identifies an actual error or loss. Meaning is always present in text too.
- Reuse `wolf-card`, `page-header`, `page-title`, `page-subtitle` and the rotation contract's `ROTATION_STYLE` vocabulary.
- Use explicit shrinkable grid tracks, contained tables, readable text and at least 44px touch targets. Small-screen layout must not rely on body overflow hiding.

The reviewed layout study is `research/2026-10-crypto-rotation/paper-workspace-mock.html`. Held 390px and 1440px screenshots passed mechanical overflow/contrast checks and visual inspection. Those are layout-study results, not final application acceptance.

## Screen hierarchy

1. Scope: CAD/BTC/ETH/LINK, paper mode and server-backed account identity.
2. Three primary numbers: portfolio CAD value, identical-start HOLD value, value added/lost by decisions after costs.
3. Four balance rows with units, CAD mark/value, allocation and initial HOLD units.
4. Review panel with shift/HOLD, explicit fee assumptions, quote details and bounded approval.
5. Activity ledger, cash flows and export.
6. Research panel with source/coverage, user-entered parameters, comparison and limitations.

Before setup, use a deliberate empty state with blank inputs rather than seeded owner capital. Demo data must be labeled and isolated. No placeholder profit figures or invented market values.

## States and copy

| State | Visible behavior |
|---|---|
| Signed out | Real sign-in and explicitly identified demo entry |
| Configuration unavailable | Name the unusable subsystem and prevent dependent actions |
| No portfolio | Opening form; no false zero-valued performance account |
| Fetching prices | Loading state with actions disabled until usable data arrives |
| Market failure/staleness | Source/time/error visible; no successful HOLD recommendation implied |
| Preview | Exact route, amounts, costs, expiry and paper-only approval |
| Approved | Persisted ledger and balances; repeat action cannot duplicate execution |
| HOLD | Decision recorded; units unchanged |
| Revision conflict | Explain portfolio changed and require reload/review |
| Research incomplete | State what is unvalidated; never show calibrated probabilities |

Display timestamps in America/Toronto. Distinguish market retrieval/expiry from the observation timestamp when the provider supplies one.

## Navigation and isolation

Add Rotation to the existing navigation. While on the rotation route, hide the legacy exchange toggle and circuit-breaker badge and stop its old intelligence polling. Existing routes keep their behavior.

The root providers may remain for compatibility; the rotation screen does not consume legacy perp portfolio hooks or execute old approval routes.

## Interaction quality

Every input has a programmatic label. Errors sit near the relevant action and are announced. Preview and approval are separate steps. Quote expiration and save failures remain explicit. Buttons convey pending state and prohibit double submission. Export downloads the real server-owned artifact.

Final acceptance uses the composed live local application at desktop and 390px mobile widths, with measured overflow also checked at 360px and 320px. Screenshots remain held until reviewed. No automatic Telegram delivery.
