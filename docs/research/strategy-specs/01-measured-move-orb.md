# Strategy Spec: Measured Move / Opening Range Breakout

**Priority:** 1 (Highest)
**Source:** Doug (26-year professional trader)
**Transcript:** `trading-isnt-hard-its-basic-math-start-winning-with-this-3-step-formula`

---

## Concept

The first significant price move after session open establishes a "measured move" distance. Subsequent price waves throughout the session will approximately replicate this distance. Trade breakouts from consolidation, targeting exactly 1x measured move.

## Crypto Adaptation

For 24/7 crypto markets, define session opens as:
- **Asian:** 00:00 UTC
- **London:** 08:00 UTC
- **New York:** 13:30 UTC

Test each session independently. The session with highest volume spike at open will produce the most reliable measured move.

---

## Pseudocode

```python
def calculate_measured_move(candles, session_open_time, timeframe_minutes=15):
    """
    Calculate the measured move from the first candle of a session.
    """
    # Step 1: Find the first candle after session open
    first_candle = get_candle_at(candles, session_open_time, timeframe_minutes)
    
    # Step 2: Measured move = high - low of first candle (wicks included)
    measured_move = first_candle.high - first_candle.low
    
    # Step 3: Risk = 30% of measured move
    max_risk = measured_move * 0.30
    
    return {
        'measured_move': measured_move,
        'max_risk': max_risk,
        'opening_range_high': first_candle.high,
        'opening_range_low': first_candle.low,
        'rr_ratio': measured_move / max_risk  # Always ~3.33
    }


def detect_consolidation(candles_5m, lookback=6):
    """
    Detect consolidation after the opening impulse move.
    Consolidation = price range narrows, bars stay within a tight band.
    """
    recent = candles_5m[-lookback:]
    range_high = max(c.high for c in recent)
    range_low = min(c.low for c in recent)
    consolidation_range = range_high - range_low
    
    # Consolidation if range is less than 50% of measured move
    # and bars are overlapping (not trending)
    avg_body = mean(abs(c.close - c.open) for c in recent)
    is_consolidating = consolidation_range < measured_move * 0.50
    
    return {
        'is_consolidating': is_consolidating,
        'range_high': range_high,
        'range_low': range_low,
        'consolidation_range': consolidation_range
    }


def entry_signal(current_candle, consolidation, measured_move_data, trend_bias=None):
    """
    Generate entry signal on consolidation breakout.
    """
    mm = measured_move_data
    cons = consolidation
    
    if not cons['is_consolidating']:
        return None
    
    # LONG: candle closes above consolidation high
    if current_candle.close > cons['range_high']:
        return {
            'direction': 'LONG',
            'entry': current_candle.close,
            'stop_loss': current_candle.close - mm['max_risk'],
            'take_profit': cons['range_low'] + mm['measured_move'],
            # TP measured from base of the move, not from entry
            'risk_reward': mm['measured_move'] / mm['max_risk']
        }
    
    # SHORT: candle closes below consolidation low
    if current_candle.close < cons['range_low']:
        return {
            'direction': 'SHORT',
            'entry': current_candle.close,
            'stop_loss': current_candle.close + mm['max_risk'],
            'take_profit': cons['range_high'] - mm['measured_move'],
            'risk_reward': mm['measured_move'] / mm['max_risk']
        }
    
    return None


def manage_trade(position, current_price):
    """
    Simple management: hit target or stop. No trailing.
    """
    if position['direction'] == 'LONG':
        if current_price >= position['take_profit']:
            return 'CLOSE_PROFIT'
        if current_price <= position['stop_loss']:
            return 'CLOSE_LOSS'
    
    if position['direction'] == 'SHORT':
        if current_price <= position['take_profit']:
            return 'CLOSE_PROFIT'
        if current_price >= position['stop_loss']:
            return 'CLOSE_LOSS'
    
    return 'HOLD'
```

---

## Parameter Ranges for Optimization

| Parameter | Default | Min | Max | Notes |
|-----------|---------|-----|-----|-------|
| Opening range candle TF | 15min | 5min | 30min | Smaller = more noise, larger = fewer trades |
| Entry timeframe | 5min | 1min | 15min | Must be smaller than opening range TF |
| Max risk % of measured move | 30% | 20% | 40% | Lower = tighter stops, more stopouts |
| Consolidation lookback bars | 6 | 3 | 12 | Minimum bars to confirm consolidation |
| Consolidation range threshold | 50% of MM | 30% | 70% | % of measured move that defines "tight" |
| Session open time (crypto) | 00:00 UTC | -- | -- | Test Asian/London/NY opens |
| Max trades per session | 3 | 1 | 5 | Doug shows 3 waves typically |
| No-trade zone | First 15 min | 5min | 30min | Never trade during opening chaos |

## Expected Performance

- Win rate: ~55-65% (breakouts from consolidation have edge)
- Risk-reward: ~3.3:1 fixed
- Trades per day: 2-4
- Max drawdown target: < 10% (with 2% risk per trade)

## Complementarity with WolfPack

- **Extends ORB Session:** Current ORB strategy uses arbitrary targets. Measured move provides a data-driven target calibration.
- **Regime Filter:** Only take measured move trades when WolfPack's regime module says "trending" or "breakout" (not "mean-reverting").
- **Vol Breakout Synergy:** High-volatility sessions will produce larger measured moves = larger targets = bigger wins.
