# Strategy Spec: Trailing Stop on Higher Timeframe

**Priority:** 4
**Source:** Tom Hougaard
**Transcript:** `what-is-your-philosophy-in-day-trading-how-do-you-move-your-stop-loss`

---

## Concept

Trade management overlay (not an entry strategy). After entering on a lower timeframe, move stop management to a higher timeframe. Trail stop behind each new bar that extends the trend on the higher TF. Keeps you in trends longer by filtering out lower-TF noise.

---

## Pseudocode

```python
def trailing_stop_higher_tf(position, candles_higher_tf, buffer_points=5):
    """
    Trail stop on a higher timeframe to stay in trends longer.
    
    Entry TF -> Management TF mapping:
    - 1min entry  -> 5min management
    - 5min entry  -> 15min management
    - 15min entry -> 1H management
    - 1H entry    -> 4H management
    - 4H entry    -> 1D management
    
    Args:
        position: dict with 'direction', 'entry', 'stop_loss'
        candles_higher_tf: list of candles on the management timeframe
        buffer_points: small buffer above/below bar extreme
    """
    current_bar = candles_higher_tf[-1]
    previous_bar = candles_higher_tf[-2]
    
    if position['direction'] == 'SHORT':
        # For shorts: if current bar makes a new low below previous bar's low
        if current_bar.low < previous_bar.low:
            new_stop = current_bar.high + buffer_points
            # Only move stop if it's tighter (lower for shorts)
            if new_stop < position['stop_loss']:
                position['stop_loss'] = new_stop
                position['stop_reason'] = 'trailing_higher_tf'
    
    elif position['direction'] == 'LONG':
        # For longs: if current bar makes a new high above previous bar's high
        if current_bar.high > previous_bar.high:
            new_stop = current_bar.low - buffer_points
            # Only move stop if it's tighter (higher for longs)
            if new_stop > position['stop_loss']:
                position['stop_loss'] = new_stop
                position['stop_reason'] = 'trailing_higher_tf'
    
    return position


def detect_climactic_move(candles, lookback=20):
    """
    Detect exhaustion/climactic moves that often end trends.
    A climactic move is an abnormally large bar in the trend direction
    followed by immediate reversal.
    
    Optional exit signal -- use as warning, not automatic exit.
    """
    current = candles[-1]
    avg_range = mean(c.high - c.low for c in candles[-lookback:-1])
    current_range = current.high - current.low
    
    # Climactic if current bar is 2x+ the average range
    is_climactic = current_range > avg_range * 2.0
    
    # Check for immediate reversal (next bar)
    # This would need to be checked on the NEXT bar
    
    return {
        'is_climactic': is_climactic,
        'current_range': current_range,
        'avg_range': avg_range,
        'ratio': current_range / avg_range if avg_range > 0 else 0
    }
```

---

## Parameter Ranges

| Parameter | Default | Min | Max | Notes |
|-----------|---------|-----|-----|-------|
| Entry TF | 5min | 1min | 15min | Lower TF for precision entry |
| Management TF | 2x entry TF | 1.5x | 4x | Hougaard uses 5min->10min (2x) |
| Buffer points | 5 | 2 | 10 | Small buffer above/below bar extreme |
| Climactic threshold | 2.0x avg | 1.5x | 3.0x | Multiple of average range |

## Integration with WolfPack

This is a **universal overlay** that applies to ALL entry strategies:
- Measured Move entries: trail on 15min after entering on 5min
- SRS entries: trail on 1H after entering on 15min
- Turtle entries: trail on 1D after entering on 4H
- EMA Crossover entries: trail on 4H after entering on 1H

Implementation: Add as a `TradeManager` class method that runs on every higher-TF candle close.
