// Test: Dashboard loads with portfolio stats, price tickers, exchange indicator
const { withPage, expectText, gotoReady } = require("./helpers");

withPage(async (page) => {
  await gotoReady(page, "/");
  await expectText(page, ["WolfPack"], "Branding");
  await expectText(page, ["Portfolio Value", "Unrealized P&L", "Open Positions", "Watchlist"], "Stats");
  await expectText(page, ["BTC", "ETH"], "Price tickers");
  await expectText(page, ["Active:"], "Exchange indicator");
});
