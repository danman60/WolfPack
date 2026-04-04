# Strategy Spec: Mean Reversion with Regime Classification

**Priority:** 5
**Source:** QuantJason (algo trading fund manager)
**Transcripts:** Multiple QuantJason reels on algo trading styles, backtesting, Calmar ratio

---

## Concept

Trade mean reversion (fade extended moves back to statistical norm) only when regime classification confirms a range-bound/mean-reverting market. Disable during trending/breakout regimes to avoid blowups. Portfolio allocation: 60-80% trend following, 20-40% mean reversion for cash flow.

**NOTE:** QuantJason does NOT disclose his specific algorithm rules. This spec synthesizes his framework principles with standard mean reversion techniques suitable for WolfPack.

---

## Proposed Implementation

```python
def mean_reversion_signal(candles, regime, lookback=20, threshold_atr_mult=2.0):
    """
    Generate mean reversion signals when price extends beyond N*ATR from the mean.
    
    Only active when regime is 'RANGING' or 'MEAN_REVERTING'.
    Disabled when regime is 'TRENDING' or 'BREAKOUT'.
    """
    # Gate: only trade in appropriate regime
    if regime not in ['RANGING', 'MEAN_REVERTING', 'LOW_VOL']:
        return None
    
    # Calculate the "mean" -- options:
    # 1. VWAP (intraday)
    # 2. SMA(20) or EMA(20) (multi-day)
    # 3. Bollinger Band midline
    mean_price = sma(candles.close, lookback)[-1]
    atr = average_true_range(candles, lookback)[-1]
    
    current_price = candles[-1].close
    distance_from_mean = current_price - mean_price
    
    # LONG: price is extended below mean by threshold
    if distance_from_mean < -(threshold_atr_mult * atr):
        return {
            'direction': 'LONG',
            'entry': current_price,
            'stop_loss': current_price - (1.0 * atr),  # 1 ATR below
            'take_profit': mean_price,  # Target: return to mean
            'type': 'MEAN_REVERSION',
            'distance_atr': abs(distance_from_mean / atr)
        }
    
    # SHORT: price is extended above mean by threshold
    if distance_from_mean > (threshold_atr_mult * atr):
        return {
            'direction': 'SHORT',
            'entry': current_price,
            'stop_loss': current_price + (1.0 * atr),
            'take_profit': mean_price,
            'type': 'MEAN_REVERSION',
            'distance_atr': abs(distance_from_mean / atr)
        }
    
    return None


def vwap_mean_reversion(candles_intraday, regime):
    """
    Intraday mean reversion using VWAP as the mean.
    
    Rules from Momentum trader transcript:
    - Don't buy if price > 10% above VWAP
    - Don't buy if price far above 9 EMA
    - These act as "magnets" pulling price back
    """
    if regime not in ['RANGING', 'MEAN_REVERTING']:
        return None
    
    vwap = calculate_vwap(candles_intraday)
    ema9 = ema(candles_intraday.close, 9)[-1]
    current = candles_intraday[-1].close
    
    pct_above_vwap = (current - vwap) / vwap * 100
    pct_above_ema9 = (current - ema9) / ema9 * 100
    
    # SHORT mean reversion: extended above both VWAP and EMA9
    if pct_above_vwap > 10 and pct_above_ema9 > 5:
        return {
            'direction': 'SHORT',
            'type': 'VWAP_MEAN_REVERSION',
            'target': vwap,
            'stop_loss': current * 1.02,  # 2% above
            'pct_above_vwap': pct_above_vwap,
            'pct_above_ema9': pct_above_ema9
        }
    
    # LONG mean reversion: extended below both VWAP and EMA9
    if pct_above_vwap < -10 and pct_above_ema9 < -5:
        return {
            'direction': 'LONG',
            'type': 'VWAP_MEAN_REVERSION',
            'target': vwap,
            'stop_loss': current * 0.98,
            'pct_below_vwap': abs(pct_above_vwap),
            'pct_below_ema9': abs(pct_above_ema9)
        }
    
    return None


def calmar_ratio(returns, max_drawdown):
    """
    Key metric for algorithm evaluation.
    Calmar = Annualized Return / Max Drawdown
    
    Benchmarks (QuantJason):
    - 2.0 = okay
    - 3.0 = decent (minimum for professional funds)
    - 5.0+ = excellent (suitable for leverage)
    """
    annualized_return = calculate_annualized_return(returns)
    if max_drawdown == 0:
        return float('inf')
    return annualized_return / abs(max_drawdown)


def stress_test(strategy, candles, n_simulations=10000):
    """
    Proper backtesting per QuantJason's framework.
    
    Do NOT just run one 12-month backtest -- that leads to overfitting.
    
    Steps:
    1. Run Hidden Markov Model to identify regime states
    2. Run Monte Carlo simulations (10,000+)
    3. Analyze drawdown distribution across simulations
    4. Test across different regime periods
    """
    # 1. Identify regimes using HMM
    regimes = hidden_markov_model(candles, n_states=3)  # trending, ranging, volatile
    
    # 2. Monte Carlo: shuffle trade outcomes, simulate equity curves
    base_trades = strategy.backtest(candles)
    simulated_curves = []
    
    for i in range(n_simulations):
        shuffled_trades = random_permutation(base_trades)
        equity_curve = simulate_equity(shuffled_trades)
        simulated_curves.append({
            'max_drawdown': max_drawdown(equity_curve),
            'final_equity': equity_curve[-1],
            'calmar': calmar_ratio(equity_curve, max_drawdown(equity_curve))
        })
    
    # 3. Analyze distribution
    return {
        'median_calmar': median(s['calmar'] for s in simulated_curves),
        'worst_case_drawdown': percentile(
            [s['max_drawdown'] for s in simulated_curves], 99
        ),
        'probability_of_ruin': sum(
            1 for s in simulated_curves if s['max_drawdown'] > 0.50
        ) / n_simulations,
        'confidence_profitable': sum(
            1 for s in simulated_curves if s['final_equity'] > 1.0
        ) / n_simulations
    }
```

---

## Parameter Ranges

| Parameter | Default | Min | Max | Notes |
|-----------|---------|-----|-----|-------|
| Mean calculation | SMA(20) | EMA(9) | SMA(50) | Or VWAP for intraday |
| Extension threshold | 2.0 ATR | 1.5 | 3.0 | ATR multiples from mean |
| Stop loss | 1.0 ATR | 0.5 | 1.5 | Tight -- mean reversion has defined risk |
| Take profit | Mean | 50% to mean | 100% to mean | Partial at 50%, full at mean |
| VWAP extension threshold | 10% | 5% | 15% | For intraday VWAP reversion |
| Regime gate | Required | -- | -- | NEVER trade without regime confirmation |
| Calmar minimum | 3.0 | 2.0 | 5.0 | Minimum acceptable ratio |

## Complementarity with WolfPack

- **Regime Module:** WolfPack already has regime detection. This strategy uses it as the primary gate. CRITICAL: mean reversion MUST be disabled in trending regimes.
- **Counter-Trend Diversification:** All other WolfPack strategies are trend-following. Mean reversion captures profits in ranging markets where trend strategies chop.
- **Cash Flow:** QuantJason emphasizes mean reversion produces the "best cash flow models." Higher win rate, smaller wins, steady income during range-bound periods.
- **Portfolio Balance:** QuantJason recommends 60-80% trend / 20-40% mean reversion. WolfPack should allocate capital accordingly.

## Risks

- **Blowup Risk:** Mean reversion is inherently dangerous without regime classification. A trending breakout will destroy a mean reversion position. The regime gate is not optional -- it is the strategy's survival mechanism.
- **QuantJason lost $300K in one night** from an overfitted algo. Proper stress testing (Monte Carlo, HMM) is mandatory before live deployment.
