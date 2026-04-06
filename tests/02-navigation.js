// Test: All 8 navigation links present with correct hrefs
const { withPage, gotoReady } = require("./helpers");

withPage(async (page) => {
  await gotoReady(page, "/");

  const expected = [
    ["/", "Dashboard"],
    ["/intelligence", "Intelligence"],
    ["/trading", "Trading"],
    ["/portfolio", "Portfolio"],
    ["/backtest", "Backtest"],
    ["/auto-bot", "Auto-Bot"],
    ["/pools", "LP Pools"],
    ["/settings", "Settings"],
  ];

  const links = await page.$$eval("nav a", (els) =>
    els.map((a) => ({ href: a.getAttribute("href"), text: a.textContent.trim() }))
  );

  const missing = [];
  for (const [href, label] of expected) {
    if (!links.find((l) => l.href === href)) missing.push(`${label} (${href})`);
  }
  if (missing.length > 0) throw new Error("Missing nav links: " + missing.join(", "));
});
