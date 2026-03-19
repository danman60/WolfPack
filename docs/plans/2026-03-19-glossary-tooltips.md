# Plan: Contextual Glossary Tooltips ("Explain Like I'm in Grade 8")

## Goal
Add hover tooltips to every financial/trading/crypto term across the entire WolfPack UI. Plain-English definitions that teach as you use. Beautiful animations via Framer Motion.

## Architecture

### New Files
1. `app/src/lib/glossary.ts` — 87 term definitions (id, term, definition, category)
2. `app/src/components/Term.tsx` — Reusable `<Term>` component with animated tooltip

### Modified Files (all 8 pages + key components)
3. `app/src/app/page.tsx` — Dashboard
4. `app/src/app/intelligence/page.tsx`
5. `app/src/app/trading/page.tsx`
6. `app/src/app/portfolio/page.tsx`
7. `app/src/app/backtest/page.tsx`
8. `app/src/app/auto-bot/page.tsx`
9. `app/src/app/pools/page.tsx`
10. `app/src/app/settings/page.tsx`
11. `app/src/components/charts/SentimentGauge.tsx`
12. `app/src/components/charts/PredictionAccuracy.tsx`
13. `app/src/components/charts/PredictionOverlay.tsx`
14. `app/src/components/charts/SignalFeed.tsx`
15. `app/src/components/TradingChart.tsx`

### Dependencies
- `framer-motion` (install if not present)

## Term Component Design

```tsx
<Term id="leverage">Leverage</Term>
```

Renders as:
- Inline text with subtle dotted underline (css: `decoration-dotted decoration-gray-600`)
- On hover: Framer Motion animated tooltip appears
  - Slides up + fades in (y: 8 → 0, opacity: 0 → 1)
  - Dark card with category pill + definition text
  - Soft shadow + backdrop blur
  - Smart positioning (above by default, flips below if near top)
  - Exits with fade out (150ms)
- On mobile: tap to show, tap elsewhere to dismiss

## 87 Terms (by category)

### Trading Basics (9)
- long, short, leverage, margin, notional, position, entry-price, exit-price, size-usd

### Risk Management (3)
- stop-loss, take-profit, circuit-breaker

### Portfolio Metrics (7)
- equity, pnl, unrealized-pnl, realized-pnl, return-pct, win-rate, equity-curve

### Backtest Metrics (11)
- sharpe-ratio, max-drawdown, profit-factor, sortino-ratio, calmar-ratio, expectancy, avg-win, avg-loss, avg-holding, max-consecutive, dd-duration

### Technical Analysis (7)
- sma, ema, bollinger-bands, rsi, macd, volatility, regime-detection

### Intelligence System (10)
- confidence, conviction, sentiment, signals, trend, risk-level, outlook, agent-brief, agent-quant, agent-snoop, agent-sage

### Liquidity & Execution (6)
- liquidity, funding-rate, volume, execution-timing, slippage, commission

### DeFi / Uniswap (9)
- lp-position, tvl, fee-tier, fee-apr, tick-range, concentrated-liquidity, tick, impermanent-loss, collect-fees

### Perpetuals (2)
- perpetual-futures, funding-rate-perps

### Exchange & Modes (3)
- paper-trading, auto-bot, pending-recommendation

### Charting (3)
- candlestick, timeframe, lookback-period

### Auto-Bot (3)
- conviction-threshold, equity-allocation, position-action

### Prediction (2)
- prediction-accuracy, prediction-vs-reality

### Market Data (2)
- change-24h, current-price

### General Finance (6)
- allocation, watchlist, symbol, bullish, bearish, neutral

## Implementation Order

1. Install framer-motion if needed
2. Create glossary.ts with all 87 definitions
3. Create Term.tsx component with Framer Motion animations
4. Apply /design-pass to Term.tsx for polish
5. Wrap terms on each page (start with Dashboard, work through all 8)
6. Wrap terms in chart components
7. Build + verify
8. Push

## Design Requirements
- Tooltip: dark card (var(--surface)), subtle border, backdrop-blur
- Category pill: colored by category (trading=cyan, risk=red, portfolio=emerald, etc.)
- Animation: spring physics (stiffness: 300, damping: 20)
- Dotted underline: subtle enough to not clutter, visible enough to invite hover
- Mobile: tap-to-show with AnimatePresence exit
- Respect dark theme throughout
