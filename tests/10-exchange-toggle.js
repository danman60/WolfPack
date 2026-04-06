// Test: Exchange toggle is present and functional
const { withPage, gotoReady } = require("./helpers");

withPage(async (page) => {
  await gotoReady(page, "/");
  const body = await page.textContent("body");

  if (!/hyperliquid|dydx/i.test(body)) throw new Error("No exchange name displayed");

  // Find toggle elements in nav
  const toggleEls = await page.$$eval(
    "nav button, nav select, [class*=toggle], [class*=Toggle], [class*=exchange], [class*=Exchange]",
    (els) => els.map((e) => ({ tag: e.tagName, text: e.textContent.trim() }))
  );
  if (toggleEls.length === 0) throw new Error("No exchange toggle element found");

  // Click toggle and verify page doesn't break
  const toggle = await page.$("nav button, nav select, [class*=Toggle], [class*=exchange]");
  if (toggle) {
    await toggle.click();
    await page.waitForTimeout(500);
    const newBody = await page.textContent("body");
    if (!/hyperliquid|dydx/i.test(newBody)) throw new Error("Exchange name gone after toggle");
  }
});
