// Test: Intelligence page loads with 4 agent sections and run trigger
const { withPage, expectText, gotoReady } = require("./helpers");

withPage(async (page) => {
  await gotoReady(page, "/intelligence");
  await expectText(page, ["Quant", "Snoop", "Sage", "Brief"], "Agent sections");

  const buttons = await page.$$eval("button", (els) => els.map((b) => b.textContent.trim()));
  const hasRun = buttons.some((t) => /run|trigger|analyze|launch/i.test(t));
  if (!hasRun) throw new Error("No run/trigger button found. Buttons: " + buttons.join(", "));
});
