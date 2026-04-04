# Trader Tom's Opening Range Breakout Strategy

**Status:** Research — possible future implementation
**Source:** Tom Hougaard (tradertom.com, YouTube @TraderTom, author of "Best Loser Wins")

## Core Concept: School Run Strategy (SRS)

1. 5-minute chart, first 25 minutes after market open
2. Mark the HIGH and LOW of those first 5 candles
3. **Long:** price breaks above the high
4. **Short:** price breaks below the low
5. Cut losses fast, let winners run, pyramid into winners
6. Cancel opposite order when one side triggers
7. No indicators — pure price action with time-based levels

## Pre-Market Breakout (Original Documented Version)

- DAX: observe 7:00–7:59 AM GMT pre-market range
- Buy at high, sell at low
- **Stop: 9 pts, Target: 6 pts**
- Win rate ~90% for the 6-point target
- Asymmetric risk/reward: risk 9 to make 6, compensated by high win rate
- Same logic for Dow (13:30–14:29 GMT window)

## Variants

- **Advanced SRS (ASRS):** Enter on the 4th candle (~20 min) instead of 25
- **Anti-SRS:** Fade the breakout when context suggests failure
- **1st Bar Positive/Negative:** First candle direction determines fade entry

## Key Principles

- Works best at session opens with volatility spikes
- Designed for DAX/Dow CFDs, but ORB concept is adaptable
- NOT crypto-specific — crypto has 24/7 markets, so "session open" needs defining (e.g., US equities open 9:30 ET, or Asian/London/NY session boundaries)

## Crypto Adaptation Ideas

- Define observation windows around key session opens (NY 9:30, London 3:00 AM ET, Asia 8:00 PM ET)
- Use 5-min candles, 25-min ORB after session boundary
- Perps on Hyperliquid/dYdX have enough liquidity for breakout entries
- Funding rate alignment could filter: go long only when funding is negative (contrarian edge)
- Could combine with existing WolfPack regime detection to filter ORB signals by market regime

## TradingView Reference

- **[COG] Advanced School Run Strategy** by CognitiveAlpha (open-source PineScript)
- URL: tradingview.com/script/GT7L59eE-COG-Advanced-School-Run-Strategy/
