// Test: Trading page loads with chart area, order form, watchlist
const { withPage, expectText, gotoReady } = require("./helpers");

withPage(async (page) => {
  await gotoReady(page, "/trading");

  // Wait for chart canvas (dynamic import)
  await page.waitForTimeout(2000);
  const body = await page.textContent("body");
  const hasChart = (await page.$("canvas")) || /price|chart/i.test(body);
  if (!hasChart) throw new Error("No chart section found");

  const inputCount = await page.$$eval("input, select", (els) => els.length);
  if (inputCount < 1) throw new Error("No form inputs found for order entry");

  const buttons = await page.$$eval("button", (els) => els.map((b) => b.textContent.trim()));
  const hasTradeBtn = buttons.some((t) => /buy|sell|long|short|submit|place|order/i.test(t));
  if (!hasTradeBtn) throw new Error("No trade action button. Buttons: " + buttons.join(", "));

  await expectText(page, ["Watchlist"], "Watchlist section");
});
