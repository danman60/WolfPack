# Strategy Spec: Turtle Trading / Donchian Breakout

**Priority:** 2
**Source:** Richard Dennis / Turtle Traders
**Transcript:** `the-simple-strategy-that-made-him-turn-1600-into-350-million`

---

## Concept

Trade breakouts of N-period highest highs / lowest lows with trend filter (SMA 200). Accept many small losses to capture large trend moves. ATR-based stops, structural exit on opposite breakout.

## Crypto Adaptation

Naturally suited to crypto -- works on any trending asset on any timeframe. Crypto's trending behavior and 24/7 markets make this ideal for the 4H or daily timeframe.

---

## Pseudocode

```python
def turtle_signals(candles, period_short=20, period_long=55, atr_period=20, sma_period=200):
    """
    Generate Turtle Trading signals.
    
    Short-term system: 20-period (for 1H-4H)
    Long-term system: 55-period (for Daily-Weekly)
    """
    # Calculate indicators
    highest_high = rolling_max(candles.high, period_short)
    lowest_low = rolling_min(candles.low, period_short)
    
    atr = average_true_range(candles, atr_period)
    atr_sma = sma(atr, atr_period)
    
    trend_sma = sma(candles.close, sma_period)
    
    current = candles[-1]
    prev_hh = highest_high[-2]  # Previous bar's highest high
    prev_ll = lowest_low[-2]    # Previous bar's lowest low
    
    # Trend filter
    is_uptrend = current.close > trend_sma[-1]
    is_downtrend = current.close < trend_sma[-1]
    
    signal = None
    
    # LONG: price breaks above 20-period highest high AND in uptrend
    if current.close > prev_hh and is_uptrend:
        stop_distance = atr_sma[-1] * 2
        signal = {
            'direction': 'LONG',
            'entry': current.close,
            'stop_loss': current.close - stop_distance,
            'exit_trigger': 'lowest_low_break',  # Exit when price breaks 20-period lowest low
            'atr_stop_distance': stop_distance
        }
    
    # SHORT: price breaks below 20-period lowest low AND in downtrend
    elif current.close < prev_ll and is_downtrend:
        stop_distance = atr_sma[-1] * 2
        signal = {
            'direction': 'SHORT',
            'entry': current.close,
            'stop_loss': current.close + stop_distance,
            'exit_trigger': 'highest_high_break',
            'atr_stop_distance': stop_distance
        }
    
    return signal


def turtle_exit(position, candles, period=20):
    """
    Exit when price breaks the opposite N-period channel.
    Longs exit on break of 20-period lowest low.
    Shorts exit on break of 20-period highest high.
    """
    current = candles[-1]
    
    if position['direction'] == 'LONG':
        exit_level = rolling_min(candles.low, period)[-2]
        if current.close < exit_level:
            return 'EXIT_STRUCTURE'
        if current.close <= position['stop_loss']:
            return 'EXIT_STOP'
    
    if position['direction'] == 'SHORT':
        exit_level = rolling_max(candles.high, period)[-2]
        if current.close > exit_level:
            return 'EXIT_STRUCTURE'
        if current.close >= position['stop_loss']:
            return 'EXIT_STOP'
    
    return 'HOLD'


def position_size(account_balance, risk_pct, stop_distance, contract_value):
    """
    Standard Turtle position sizing.
    Risk a fixed percentage per trade.
    """
    risk_amount = account_balance * risk_pct
    position_size = risk_amount / stop_distance
    return position_size
```

---

## Parameter Ranges for Optimization

| Parameter | Default | Min | Max | Notes |
|-----------|---------|-----|-----|-------|
| Breakout period (short) | 20 | 10 | 30 | Dennis used 20 for intraday/medium |
| Breakout period (long) | 55 | 40 | 70 | Dennis used 55 for daily/weekly |
| ATR period | 20 | 10 | 30 | Must match breakout period |
| ATR multiplier for stop | 2.0 | 1.5 | 3.0 | Higher = wider stops, fewer stopouts |
| Trend SMA period | 200 | 100 | 300 | Longer = stronger trend confirmation |
| Risk per trade | 2% | 1% | 3% | Dennis standard |
| Timeframe (crypto) | 4H | 1H | 1D | 4H balances signal quality and frequency |
| Exit period | 20 | 10 | 20 | Can use shorter for faster exits |

## Expected Performance

- Win rate: 30-40% (expected, by design)
- Average winner / average loser: 4:1 to 10:1
- Trades per month (4H, single asset): 2-5
- Drawdown periods: Extended (weeks/months of small losses before a big winner)
- Best in: Strong trending markets
- Worst in: Choppy, ranging markets (need regime filter)

## Complementarity with WolfPack

- **Regime Module:** Only activate Turtle in "trending" or "breakout" regime. Disable in "mean-reverting" or "choppy" regime. This is the single most important filter.
- **Multi-Asset:** Run across BTC, ETH, SOL simultaneously. Turtle's strength is catching the one that trends while small-losing on the others.
- **Existing ATR/Volatility:** WolfPack's volatility module already calculates ATR -- reuse directly.
- **Time Horizon:** Complements intraday strategies (SRS, ORB, Measured Move) by capturing multi-day trends.
