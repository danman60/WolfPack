# Strategy Spec: School Run (SRS) + Anti-School Run (Anti-SRS)

**Priority:** 3
**Source:** Tom Hougaard
**Transcripts:** `school-run-trading-strategy-explained`, `v58-out-of-hours-srs-review-and-anti-srs`, `trading-strategie-der-school-run` (German), `reacting-to-tom-hougaards-school-run-strategy`

---

## Concept

The second 15-minute candle after market open (the "School Run bar") captures directional intent after the initial order-flow noise clears. Trade breakouts in the direction of the breakout. Filter with overnight range: if the School Run bar is inside the overnight range, FADE the breakout instead.

## Crypto Adaptation

Define three sessions with clear opens:
- **Asian:** 00:00 UTC (Tokyo open proxy)
- **London:** 08:00 UTC (European open proxy)
- **New York:** 13:30 UTC (US session proxy)

Define "overnight range" as the low-volume period preceding each session open:
- For London open: overnight = 00:00-06:00 UTC (Asian session)
- For NY open: overnight = 06:00-12:00 UTC (London morning quiet period -- less applicable)
- For Asian open: overnight = 21:00-00:00 UTC (post-NY wind-down)

London and Asian opens are most likely to produce clean SRS signals for crypto.

---

## Pseudocode

```python
def calculate_overnight_range(candles, overnight_start, overnight_end):
    """
    Calculate the high/low range during the overnight period.
    """
    overnight_candles = [c for c in candles if overnight_start <= c.time < overnight_end]
    if not overnight_candles:
        return None
    
    return {
        'high': max(c.high for c in overnight_candles),
        'low': min(c.low for c in overnight_candles),
        'range': max(c.high for c in overnight_candles) - min(c.low for c in overnight_candles)
    }


def identify_school_run_bar(candles_15m, session_open_time):
    """
    The School Run bar is the SECOND 15-minute candle after session open.
    """
    first_candle = get_candle_at(candles_15m, session_open_time)   # 00:00-00:15
    school_run_bar = get_next_candle(candles_15m, first_candle)     # 00:15-00:30
    
    return {
        'high': school_run_bar.high,
        'low': school_run_bar.low,
        'open': school_run_bar.open,
        'close': school_run_bar.close,
        'range': school_run_bar.high - school_run_bar.low,
        'bar': school_run_bar
    }


def classify_srs_context(sr_bar, overnight_range):
    """
    Determine if the School Run bar is inside, above, or below the overnight range.
    This determines whether to trade conventional SRS or Anti-SRS.
    """
    onr = overnight_range
    
    # Bar is ABOVE overnight range: both high and low above ONR high
    if sr_bar['low'] > onr['high']:
        return 'ABOVE_ONR'
    
    # Bar is BELOW overnight range: both high and low below ONR low
    if sr_bar['high'] < onr['low']:
        return 'BELOW_ONR'
    
    # Bar is INSIDE overnight range
    return 'INSIDE_ONR'


def generate_srs_signal(sr_bar, context, current_price, max_time):
    """
    Generate SRS or Anti-SRS signal based on context.
    
    Rules:
    - ABOVE_ONR: Buy above SR high (standard), Buy below SR low (buy the dip)
    - BELOW_ONR: Sell below SR low (standard), Sell above SR high (sell the rip)  
    - INSIDE_ONR: Sell above SR high (anti-SRS), Don't sell below SR low
    """
    if current_price.time > max_time:
        return None  # No trades after cutoff (e.g., 2 hours post-open)
    
    if context == 'ABOVE_ONR':
        # Bullish context -- everything is a buy
        if current_price > sr_bar['high']:
            return {'direction': 'LONG', 'type': 'SRS_STANDARD',
                    'entry': current_price,
                    'stop_loss': sr_bar['low'] - buffer,
                    'reason': 'Breakout above SR bar, bar above overnight range'}
        if current_price < sr_bar['low']:
            return {'direction': 'LONG', 'type': 'SRS_DIP_BUY',
                    'entry': current_price,
                    'stop_loss': sr_bar['low'] - sr_bar['range'] - buffer,
                    'reason': 'Buy below prior bar low, bullish context'}
    
    elif context == 'BELOW_ONR':
        # Bearish context -- everything is a sell
        if current_price < sr_bar['low']:
            return {'direction': 'SHORT', 'type': 'SRS_STANDARD',
                    'entry': current_price,
                    'stop_loss': sr_bar['high'] + buffer,
                    'reason': 'Breakdown below SR bar, bar below overnight range'}
        if current_price > sr_bar['high']:
            return {'direction': 'SHORT', 'type': 'SRS_RIP_SELL',
                    'entry': current_price,
                    'stop_loss': sr_bar['high'] + sr_bar['range'] + buffer,
                    'reason': 'Sell above prior bar high, bearish context'}
    
    elif context == 'INSIDE_ONR':
        # Anti-SRS: fade breakouts
        if current_price > sr_bar['high']:
            return {'direction': 'SHORT', 'type': 'ANTI_SRS',
                    'entry': current_price,
                    'stop_loss': current_price + 70,  # ~70 points DAX equivalent
                    'reason': 'Anti-SRS: fade breakout, bar inside overnight range'}
        # Do NOT sell short below in INSIDE_ONR context
    
    return None


# Optimized Forex Variant (Simply4x) -- for 30-min chart
def srs_optimized_forex(candles_30m, session_open_time='08:00', cutoff='10:00'):
    """
    Simplified SRS for GBP/USD on 30-minute chart.
    Wait for candle BODY to close above/below the 8AM candle's high/low.
    """
    open_candle = get_candle_at(candles_30m, session_open_time)  # 8:00 AM candle
    
    for candle in get_candles_after(candles_30m, open_candle, until=cutoff):
        # Body must close above previous candle's HIGH
        if candle.close > open_candle.high:
            return {
                'direction': 'LONG',
                'entry': candle.close,
                'stop_loss': candle.low - 3,  # 3 pips below entry candle low
                'target': 'R:R 1:1 then trail'
            }
        
        # Body must close below previous candle's LOW
        if candle.close < open_candle.low:
            return {
                'direction': 'SHORT',
                'entry': candle.close,
                'stop_loss': candle.high + 3,  # 3 pips above entry candle high
                'target': 'R:R 1:1 then trail'
            }
        
        # Update reference candle for next iteration
        open_candle = candle
    
    return None  # No signal before cutoff
```

---

## Parameter Ranges for Optimization

| Parameter | Default | Min | Max | Notes |
|-----------|---------|-----|-----|-------|
| Session open (crypto) | 00:00 UTC | -- | -- | Test Asian/London/NY |
| School Run bar TF | 15min | 5min | 30min | Hougaard uses 15min; Simply4x uses 30min |
| Overnight range start | T-6h | T-8h | T-4h | Hours before session open |
| Overnight range end | Session open | -- | -- | -- |
| Stop loss (standard SRS) | SR bar range | 50% range | 150% range | Full bar range is safest |
| Stop loss (Anti-SRS) | 70 pts equiv | 50 | 100 | Fixed in ATR multiples for crypto |
| Max entry window | 2 hours | 1h | 3h | Simply4x uses 2h post-open |
| Buffer (pips/points) | 3 | 1 | 5 | Avoid exact-level wicks |

## Expected Performance

- Win rate (standard SRS): ~60-70% (Hougaard's reported rate)
- Win rate (Anti-SRS): ~55-65% (estimated, less backtesting data)
- Trades per session: 1 (sometimes 0 if no trigger)
- R:R: Variable -- Hougaard lets winners run; Simply4x uses 1:1 base

## Complementarity with WolfPack

- **Replaces/Enhances ORB Session:** The existing ORB session strategy in WolfPack is a basic version of this. SRS + Anti-SRS adds the overnight range filter.
- **Regime Module:** Overnight range classification (above/below/inside) IS a mini-regime filter. WolfPack's regime module can validate.
- **Session Trading:** WolfPack already tracks sessions. SRS signals can be generated at each session open.
