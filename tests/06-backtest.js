// Test: Backtest page loads with strategy config and run button
const { withPage, gotoReady } = require("./helpers");

withPage(async (page) => {
  await gotoReady(page, "/backtest");
  const body = await page.textContent("body");

  if (!/backtest/i.test(body)) throw new Error("Backtest heading missing");
  if (!/strategy/i.test(body)) throw new Error("Strategy section missing");

  const buttons = await page.$$eval("button", (els) => els.map((b) => b.textContent.trim()));
  const hasRun = buttons.some((t) => /run|start|backtest|execute/i.test(t));
  if (!hasRun) throw new Error("No run button. Buttons: " + buttons.join(", "));
});
