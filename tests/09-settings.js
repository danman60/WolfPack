// Test: Settings page loads with exchange and strategy config
const { withPage, gotoReady } = require("./helpers");

withPage(async (page) => {
  await gotoReady(page, "/settings");
  const body = await page.textContent("body");

  if (!/settings|configuration/i.test(body)) throw new Error("Settings heading missing");
  if (!/hyperliquid|dydx|exchange/i.test(body)) throw new Error("Exchange config missing");
  if (!/strategy|paper|mode/i.test(body)) throw new Error("Strategy mode missing");
});
