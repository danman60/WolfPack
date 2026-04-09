"""Price-precision utilities.

Rounding prices to a fixed 2 decimals is correct for BTC/ETH ($thousands) but
catastrophically wrong for sub-dollar assets like DOGE ($0.09): a 3.5% stop-loss
on DOGE at entry $0.08991 computes to $0.09306, but `round(0.09306, 2)` = 0.09,
which collapses the SL to effectively at-entry. That's how a DOGE short ended
up with entry=0.08991, stop_loss=0.09, take_profit=0.09 (all the same) and lost
$342 before any stop could fire.

Use `round_price()` for anything that is a market price (entry, stop, take
profit, trailing stop, current price). Dollar-value amounts like equity, pnl,
fees should still use `round(x, 2)` — that's just dollars-and-cents precision.
"""


def round_price(price: float) -> float:
    """Round a market price to magnitude-appropriate precision.

    Precision thresholds (each keeps roughly 5 significant digits):
        >= 1000   -> 2 decimals (BTC, ETH in USD)
        >= 100    -> 3 decimals
        >= 1      -> 5 decimals
        >= 0.01   -> 6 decimals (DOGE, XRP range)
        <  0.01   -> 8 decimals (SHIB, PEPE range)
    """
    if price <= 0:
        return price
    if price >= 1000:
        return round(price, 2)
    if price >= 100:
        return round(price, 3)
    if price >= 1:
        return round(price, 5)
    if price >= 0.01:
        return round(price, 6)
    return round(price, 8)
