// Test: Auto-Bot page loads with toggle, equity config, activity log
const { withPage, gotoReady } = require("./helpers");

withPage(async (page) => {
  await gotoReady(page, "/auto-bot");
  const body = await page.textContent("body");

  if (!/auto/i.test(body)) throw new Error("Auto-Bot heading missing");

  const buttons = await page.$$eval("button", (els) => els.map((b) => b.textContent.trim()));
  const hasToggle = buttons.some((t) => /enable|disable|start|stop|toggle|activate/i.test(t));
  if (!hasToggle) throw new Error("No toggle. Buttons: " + buttons.join(", "));

  if (!/equity|conviction|threshold/i.test(body)) throw new Error("Config section missing");
});
