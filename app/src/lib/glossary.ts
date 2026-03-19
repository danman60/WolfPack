/**
 * Contextual glossary — plain-English definitions for every financial term in the UI.
 * Written for someone in grade 8 who's never traded before.
 */

export interface GlossaryEntry {
  term: string;
  definition: string;
  category: GlossaryCategory;
}

export type GlossaryCategory =
  | "trading"
  | "risk"
  | "portfolio"
  | "backtest"
  | "technical"
  | "intelligence"
  | "execution"
  | "defi"
  | "exchange"
  | "charting"
  | "general";

export const CATEGORY_COLORS: Record<GlossaryCategory, string> = {
  trading: "var(--wolf-cyan)",
  risk: "var(--wolf-red)",
  portfolio: "var(--wolf-emerald)",
  backtest: "var(--wolf-purple)",
  technical: "var(--wolf-blue)",
  intelligence: "var(--wolf-amber)",
  execution: "var(--wolf-cyan)",
  defi: "var(--wolf-purple)",
  exchange: "var(--wolf-emerald)",
  charting: "var(--wolf-blue)",
  general: "var(--wolf-cyan)",
};

export const CATEGORY_LABELS: Record<GlossaryCategory, string> = {
  trading: "Trading",
  risk: "Risk",
  portfolio: "Portfolio",
  backtest: "Backtest",
  technical: "Indicators",
  intelligence: "AI Intel",
  execution: "Execution",
  defi: "DeFi",
  exchange: "Exchange",
  charting: "Charts",
  general: "General",
};

export const glossary: Record<string, GlossaryEntry> = {
  // ── Trading Basics ──
  long: {
    term: "Long",
    definition: "A bet that the price will go UP. You buy now, hoping to sell later at a higher price and keep the difference as profit.",
    category: "trading",
  },
  short: {
    term: "Short",
    definition: "A bet that the price will go DOWN. You borrow and sell now, hoping to buy back later at a lower price. The difference is your profit.",
    category: "trading",
  },
  leverage: {
    term: "Leverage",
    definition: "Borrowing money to make a bigger trade than you could with just your own cash. 5x leverage means a $100 trade controls $500 worth of crypto. Gains AND losses are multiplied.",
    category: "trading",
  },
  margin: {
    term: "Margin",
    definition: "The cash you put up as collateral when using leverage. Think of it as a security deposit — if the trade goes badly, this is what you lose first.",
    category: "trading",
  },
  notional: {
    term: "Notional",
    definition: "The total value your trade controls. If you put in $100 with 5x leverage, the notional value is $500 — that's how much crypto you're actually trading.",
    category: "trading",
  },
  position: {
    term: "Position",
    definition: "An active trade you currently have open. If you bought BTC, you \"have a position\" in BTC until you sell it.",
    category: "trading",
  },
  "entry-price": {
    term: "Entry Price",
    definition: "The price you paid when you opened your trade. This is your starting point — everything is measured as gain or loss from here.",
    category: "trading",
  },
  "exit-price": {
    term: "Exit Price",
    definition: "The price when you closed your trade. The difference between entry and exit price determines your profit or loss.",
    category: "trading",
  },
  "size-usd": {
    term: "Size (USD)",
    definition: "How many dollars you're putting into this trade. A bigger size means bigger potential gains but also bigger potential losses.",
    category: "trading",
  },

  // ── Risk Management ──
  "stop-loss": {
    term: "Stop Loss",
    definition: "An automatic safety net. You set a price, and if the trade drops to that level, it automatically closes to limit your losses. Like a parachute — you hope you never need it.",
    category: "risk",
  },
  "take-profit": {
    term: "Take Profit",
    definition: "The opposite of a stop loss — you set a target price, and when the trade reaches it, you automatically lock in your gains. Helps you avoid the temptation of holding too long.",
    category: "risk",
  },
  "circuit-breaker": {
    term: "Circuit Breaker",
    definition: "An emergency shutoff switch. If the system loses too much money in a day, it automatically stops all trading to prevent a catastrophic blowup. Like a fuse in an electrical panel.",
    category: "risk",
  },

  // ── Portfolio Metrics ──
  equity: {
    term: "Equity",
    definition: "Your total account value right now — starting money plus any profits, minus any losses. This is what you'd have if you closed everything.",
    category: "portfolio",
  },
  pnl: {
    term: "P&L (Profit & Loss)",
    definition: "How much money you've made or lost. Green/positive means profit, red/negative means loss. Simple as that.",
    category: "portfolio",
  },
  "unrealized-pnl": {
    term: "Unrealized P&L",
    definition: "Paper profits or losses on trades you haven't closed yet. It's not real money until you close the position — it could still go up or down.",
    category: "portfolio",
  },
  "realized-pnl": {
    term: "Realized P&L",
    definition: "Actual profits or losses from trades you've already closed. This money is locked in — it's real, not just on paper.",
    category: "portfolio",
  },
  "return-pct": {
    term: "Return %",
    definition: "Your profit or loss as a percentage of what you started with. If you started with $10,000 and now have $10,500, your return is +5%.",
    category: "portfolio",
  },
  "win-rate": {
    term: "Win Rate",
    definition: "The percentage of your trades that made money. A 60% win rate means 6 out of every 10 trades were profitable. Even 50-55% can be great if your wins are bigger than your losses.",
    category: "portfolio",
  },
  "equity-curve": {
    term: "Equity Curve",
    definition: "A chart showing your account value over time. A smooth upward line is the dream. Sharp drops (drawdowns) show periods where you were losing money.",
    category: "portfolio",
  },

  // ── Backtest Metrics ──
  "sharpe-ratio": {
    term: "Sharpe Ratio",
    definition: "Measures how good your returns are compared to the risk you took. Above 1.0 is decent, above 2.0 is great. A high number means you're getting more reward per unit of risk.",
    category: "backtest",
  },
  "max-drawdown": {
    term: "Max Drawdown",
    definition: "The biggest drop from your highest point to your lowest point. If your account went from $10,000 to $8,000 before recovering, your max drawdown is 20%. Lower is better.",
    category: "backtest",
  },
  "profit-factor": {
    term: "Profit Factor",
    definition: "Total money won divided by total money lost. A profit factor of 2.0 means you made $2 for every $1 you lost. Above 1.5 is good, above 2.0 is excellent.",
    category: "backtest",
  },
  "sortino-ratio": {
    term: "Sortino Ratio",
    definition: "Like Sharpe Ratio, but only counts the bad volatility (losses). It doesn't penalize you for upside swings — only the painful drops count against you.",
    category: "backtest",
  },
  "calmar-ratio": {
    term: "Calmar Ratio",
    definition: "Your annual return divided by your worst drawdown. Shows whether the pain of your biggest loss was worth the returns. Higher is better.",
    category: "backtest",
  },
  expectancy: {
    term: "Expectancy",
    definition: "The average amount you expect to make (or lose) per trade. Positive expectancy means the strategy makes money over time — even if individual trades lose.",
    category: "backtest",
  },
  "avg-win": {
    term: "Average Win",
    definition: "The average percentage gained on your winning trades. If your average win is +3%, that means each profitable trade typically returns about 3%.",
    category: "backtest",
  },
  "avg-loss": {
    term: "Average Loss",
    definition: "The average percentage lost on your losing trades. If average loss is -1.5%, that means each losing trade typically costs about 1.5%.",
    category: "backtest",
  },
  "avg-holding": {
    term: "Average Hold Time",
    definition: "How long you typically hold each trade, measured in candle bars. Short hold times mean quick trades, long times mean patient positions.",
    category: "backtest",
  },
  "max-consecutive": {
    term: "Max Consecutive Wins/Losses",
    definition: "The longest winning or losing streak. Even good strategies have losing streaks — knowing the worst streak helps you mentally prepare and not panic.",
    category: "backtest",
  },
  "dd-duration": {
    term: "Drawdown Duration",
    definition: "How long it took to recover from the worst loss. If your account dropped 20% and took 30 days to get back to its high, the drawdown duration is 30 days.",
    category: "backtest",
  },
  drawdown: {
    term: "Drawdown",
    definition: "How far your account has fallen from its highest point. A 10% drawdown means you're currently 10% below your best. Think of it as a \"how much am I down\" meter.",
    category: "backtest",
  },

  // ── Technical Analysis ──
  sma: {
    term: "SMA (Simple Moving Average)",
    definition: "The average price over the last N periods. SMA-20 takes the last 20 prices and averages them. Smooths out noise to show the overall trend direction.",
    category: "technical",
  },
  ema: {
    term: "EMA (Exponential Moving Average)",
    definition: "Like SMA but gives more weight to recent prices, so it reacts faster to changes. The 9 EMA is especially useful for spotting when price is overextended.",
    category: "technical",
  },
  "bollinger-bands": {
    term: "Bollinger Bands",
    definition: "Two lines drawn above and below the moving average based on volatility. When price touches the upper band, it might be overbought. Lower band = potentially oversold.",
    category: "technical",
  },
  rsi: {
    term: "RSI (Relative Strength Index)",
    definition: "A momentum score from 0 to 100. Above 70 = overbought (price might drop soon). Below 30 = oversold (price might bounce). Between 30-70 is neutral territory.",
    category: "technical",
  },
  macd: {
    term: "MACD",
    definition: "A momentum indicator that uses two moving averages. When the MACD line crosses above the signal line, it suggests upward momentum. Below = downward momentum.",
    category: "technical",
  },
  volatility: {
    term: "Volatility",
    definition: "How wildly the price swings up and down. High volatility = big price moves (exciting but risky). Low volatility = calm, steady prices. Think of it as the market's mood swings.",
    category: "technical",
  },
  "regime-detection": {
    term: "Regime Detection",
    definition: "Figuring out what \"mode\" the market is in — trending up, trending down, or going sideways (choppy). Different strategies work in different regimes.",
    category: "technical",
  },
  vwap: {
    term: "VWAP",
    definition: "Volume-Weighted Average Price — the average price weighted by how much was traded at each level. Acts like a magnet: if price is far above VWAP, it often gets pulled back down.",
    category: "technical",
  },

  // ── Intelligence System ──
  confidence: {
    term: "Confidence",
    definition: "How sure the AI agent is about its analysis, from 0% (no idea) to 100% (absolutely certain). Higher confidence means the agent found stronger evidence for its conclusion.",
    category: "intelligence",
  },
  conviction: {
    term: "Conviction",
    definition: "How strongly the system believes in a trade recommendation. A high conviction (70%+) means multiple signals align. Low conviction means mixed signals — proceed with caution.",
    category: "intelligence",
  },
  sentiment: {
    term: "Sentiment",
    definition: "The overall mood of the market — are people feeling optimistic (bullish) or pessimistic (bearish)? Measured by analyzing social media, news, and trading behavior.",
    category: "intelligence",
  },
  signals: {
    term: "Signals",
    definition: "Individual clues or indicators that suggest what the market might do next. Multiple signals pointing the same direction = stronger evidence for a trade.",
    category: "intelligence",
  },
  trend: {
    term: "Trend",
    definition: "The general direction prices are moving. An uptrend means higher highs and higher lows. A downtrend means the opposite. \"The trend is your friend\" is a classic trading saying.",
    category: "intelligence",
  },
  "risk-level": {
    term: "Risk Level",
    definition: "How dangerous the current market conditions are for trading. Low risk = good conditions. High risk = be careful or sit on the sidelines.",
    category: "intelligence",
  },
  outlook: {
    term: "Outlook",
    definition: "A forward-looking prediction about where the market is headed. Like a weather forecast, but for prices — it's an educated guess, not a guarantee.",
    category: "intelligence",
  },
  "agent-brief": {
    term: "The Brief",
    definition: "The boss agent. It reads what the Quant, Snoop, and Sage found, combines everything, and produces final trade recommendations with conviction scores.",
    category: "intelligence",
  },
  "agent-quant": {
    term: "The Quant",
    definition: "The math nerd agent. Crunches numbers, reads charts, calculates technical indicators like moving averages and RSI. Finds patterns in price data.",
    category: "intelligence",
  },
  "agent-snoop": {
    term: "The Snoop",
    definition: "The social media detective. Scans Twitter, Reddit, news sites for what people are saying about crypto. Measures the crowd's mood and excitement level.",
    category: "intelligence",
  },
  "agent-sage": {
    term: "The Sage",
    definition: "The big-picture thinker. Looks at how different markets relate to each other, macro trends, and weekly forecasts. Thinks about the \"why\" behind price moves.",
    category: "intelligence",
  },

  // ── Liquidity & Execution ──
  liquidity: {
    term: "Liquidity",
    definition: "How easily you can buy or sell without moving the price. High liquidity = lots of buyers and sellers, smooth trades. Low liquidity = your trade might push the price against you.",
    category: "execution",
  },
  "funding-rate": {
    term: "Funding Rate",
    definition: "A small fee paid between long and short traders every 8 hours to keep futures prices close to spot. Positive = longs pay shorts. Negative = shorts pay longs.",
    category: "execution",
  },
  volume: {
    term: "Volume",
    definition: "How much trading activity is happening — the total dollar amount being bought and sold. High volume confirms that price moves are supported by real interest.",
    category: "execution",
  },
  "execution-timing": {
    term: "Execution Timing",
    definition: "Finding the best moment to enter or exit a trade. Like buying concert tickets — timing matters. Some hours have more liquidity and better prices than others.",
    category: "execution",
  },
  slippage: {
    term: "Slippage",
    definition: "The difference between the price you expected and the price you actually got. Like ordering a $5 item but being charged $5.02. Happens more in fast-moving or thin markets.",
    category: "execution",
  },
  commission: {
    term: "Commission / Fees",
    definition: "The cost the exchange charges for each trade, measured in basis points (bps). 10 bps = 0.10%. On a $1,000 trade, that's $1 in fees.",
    category: "execution",
  },

  // ── DeFi / Uniswap ──
  "lp-position": {
    term: "LP Position",
    definition: "Depositing two tokens into a trading pool to earn fees from other people's trades. You become a mini market maker — providing the liquidity that traders need.",
    category: "defi",
  },
  tvl: {
    term: "TVL (Total Value Locked)",
    definition: "The total dollar value of all tokens deposited in a pool. Higher TVL generally means more trust and better trading conditions. Think of it as how much money is in the pool.",
    category: "defi",
  },
  "fee-tier": {
    term: "Fee Tier",
    definition: "The percentage charged on every trade in the pool (0.01%, 0.05%, 0.3%, or 1%). Higher fees = more income per trade but fewer trades. Stablecoin pairs usually use lower tiers.",
    category: "defi",
  },
  "fee-apr": {
    term: "Fee APR",
    definition: "The annual percentage return you'd earn from trading fees if current rates continued for a year. A 20% APR means you'd earn about 20% on your deposit per year from fees alone.",
    category: "defi",
  },
  "tick-range": {
    term: "Tick Range / Price Range",
    definition: "The price band where your liquidity is active. Concentrated liquidity means you pick a range (e.g., ETH between $2,000-$3,000). You earn fees only when the price is in your range.",
    category: "defi",
  },
  "concentrated-liquidity": {
    term: "Concentrated Liquidity",
    definition: "Instead of spreading your money across all possible prices, you focus it in a specific range. Earns more fees when price is in range, but earns nothing if price leaves your range.",
    category: "defi",
  },
  tick: {
    term: "Tick",
    definition: "A tiny price level in the Uniswap system. Think of it like marks on a ruler — each tick represents a specific price point where liquidity can be placed.",
    category: "defi",
  },
  "impermanent-loss": {
    term: "Impermanent Loss",
    definition: "A sneaky loss that happens when the prices of your deposited tokens change relative to each other. The bigger the price change, the bigger the loss. Called \"impermanent\" because it reverses if prices return to where they were.",
    category: "defi",
  },
  "collect-fees": {
    term: "Collect Fees",
    definition: "Claiming the trading fees that have accumulated in your LP position. These fees are your reward for providing liquidity — like collecting rent.",
    category: "defi",
  },

  // ── Perpetual Futures ──
  "perpetual-futures": {
    term: "Perpetual Futures",
    definition: "A type of trading contract that lets you bet on price movements without actually owning the crypto. Unlike regular futures, these never expire — you can hold them forever.",
    category: "trading",
  },

  // ── Exchange & Modes ──
  "paper-trading": {
    term: "Paper Trading",
    definition: "Practice trading with fake money. Everything works exactly like real trading, but no actual money is at risk. Perfect for testing strategies before putting real cash on the line.",
    category: "exchange",
  },
  "auto-bot": {
    term: "Auto-Bot",
    definition: "An autonomous trading robot that reads AI intelligence signals and automatically places trades when conviction is high enough. You set the rules, it executes 24/7.",
    category: "exchange",
  },
  "pending-recommendation": {
    term: "Pending Recommendation",
    definition: "A trade suggestion from the AI that's waiting for your approval. The system won't trade until you say yes — you're always in control.",
    category: "exchange",
  },

  // ── Charting ──
  candlestick: {
    term: "Candlestick",
    definition: "A chart element showing the price range for a time period. The body shows open-to-close. The wicks show the high and low. Green = price went up. Red = price went down.",
    category: "charting",
  },
  timeframe: {
    term: "Timeframe / Interval",
    definition: "How much time each candle represents. 1h = each candle is 1 hour of trading. 1d = each candle is one full day. Shorter timeframes show more detail, longer ones show the bigger picture.",
    category: "charting",
  },
  "lookback-period": {
    term: "Lookback Period",
    definition: "How far back in time to analyze. A 7-day lookback examines the last week of data. Longer lookbacks give more context but may include outdated market conditions.",
    category: "charting",
  },

  // ── Auto-Bot Specific ──
  "conviction-threshold": {
    term: "Conviction Threshold",
    definition: "The minimum confidence level required before the auto-bot will execute a trade. Set it to 80% and the bot only trades when it's at least 80% sure. Higher = fewer but safer trades.",
    category: "intelligence",
  },
  "equity-allocation": {
    term: "Equity Allocation",
    definition: "How much money you've dedicated to the auto-bot. The bot trades with this amount and won't touch the rest of your portfolio.",
    category: "portfolio",
  },
  "position-action": {
    term: "Position Action",
    definition: "A suggested change to an existing trade — like closing it, adjusting the stop loss, or taking partial profits. The AI monitors your open positions and recommends actions.",
    category: "intelligence",
  },

  // ── Prediction ──
  "prediction-accuracy": {
    term: "7-Day Accuracy",
    definition: "What percentage of the AI's predictions over the last 7 days were correct. If it predicted \"BTC up\" and BTC went up, that's a correct prediction.",
    category: "intelligence",
  },
  "prediction-vs-reality": {
    term: "Prediction vs Reality",
    definition: "A chart comparing what the AI predicted would happen versus what actually happened. Shows how well the AI's forecasts matched real price movements.",
    category: "intelligence",
  },

  // ── Market Data ──
  "change-24h": {
    term: "24h Change",
    definition: "How much the price has changed in the last 24 hours, shown as a percentage. +5% means it's 5% higher than yesterday. -3% means it dropped 3%.",
    category: "general",
  },
  "current-price": {
    term: "Current Price",
    definition: "The live market price right now — what you'd pay if you bought at this moment. Updates in real-time as trades happen.",
    category: "general",
  },

  // ── General ──
  allocation: {
    term: "Allocation",
    definition: "How you divide your money across different investments. \"10% allocation to ETH\" means 10% of your total portfolio is in Ethereum.",
    category: "general",
  },
  watchlist: {
    term: "Watchlist",
    definition: "A list of crypto assets you're keeping an eye on. Like bookmarking stocks — you haven't traded them yet, but you want to monitor their prices and signals.",
    category: "general",
  },
  symbol: {
    term: "Symbol / Ticker",
    definition: "The short code for a crypto asset. BTC = Bitcoin, ETH = Ethereum, SOL = Solana. Like how the stock market uses AAPL for Apple.",
    category: "general",
  },
  bullish: {
    term: "Bullish",
    definition: "Expecting prices to go UP. A bull charges upward with its horns. When someone says \"I'm bullish on ETH,\" they think Ethereum's price will rise.",
    category: "general",
  },
  bearish: {
    term: "Bearish",
    definition: "Expecting prices to go DOWN. A bear swipes downward with its paws. \"Bearish sentiment\" means most people think prices will fall.",
    category: "general",
  },
  neutral: {
    term: "Neutral",
    definition: "No strong opinion either way — not bullish, not bearish. The market could go up or down from here, and the signals are mixed.",
    category: "general",
  },
  "open-interest": {
    term: "Open Interest",
    definition: "The total number of active futures contracts that haven't been closed. Rising open interest means new money is flowing in. Falling OI means people are closing positions.",
    category: "execution",
  },
  correlation: {
    term: "Correlation",
    definition: "How closely two assets move together. High correlation means when BTC goes up, the other usually does too. Low or negative correlation means they move independently.",
    category: "technical",
  },
  "starting-equity": {
    term: "Starting Equity",
    definition: "The amount of money you began with. Used to calculate your total return — everything is measured as growth or decline from this starting point.",
    category: "portfolio",
  },
};
