// Test: LP Pools page loads with pool browser and positions sections
const { withPage, gotoReady } = require("./helpers");

withPage(async (page) => {
  await gotoReady(page, "/pools");
  const body = await page.textContent("body");

  if (!/pool|liquidity|lp/i.test(body)) throw new Error("Pools heading missing");
  if (!/browser|position|top pools|filtered/i.test(body)) throw new Error("Pool sections missing");
});
