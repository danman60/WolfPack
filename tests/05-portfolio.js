// Test: Portfolio page loads with equity, positions, trade history
const { withPage, gotoReady } = require("./helpers");

withPage(async (page) => {
  await gotoReady(page, "/portfolio");
  const body = await page.textContent("body");

  if (!/portfolio/i.test(body)) throw new Error("Portfolio heading missing");
  if (!/equity|value|balance/i.test(body)) throw new Error("No equity section");
  if (!/position/i.test(body)) throw new Error("No positions section");
  if (!/trade|history/i.test(body)) throw new Error("No trade history section");
});
