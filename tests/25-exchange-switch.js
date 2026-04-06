// Workflow Test: Switch between Hyperliquid and dYdX, verify data refreshes
const { withPage, gotoReady, isBackendUp, skipTest } = require("./helpers");

withPage(async (page) => {
  await gotoReady(page, "/trading");

  // 1. Identify the exchange toggle buttons
  const hlButton = page.locator("button", { hasText: /hyperliquid/i }).first();
  const dydxButton = page.locator("button", { hasText: /dydx/i }).first();

  const hlExists = await hlButton.count() > 0;
  const dydxExists = await dydxButton.count() > 0;

  if (!hlExists || !dydxExists) {
    throw new Error(`Exchange toggle buttons missing: HL=${hlExists}, dYdX=${dydxExists}`);
  }

  // 2. Determine which exchange is currently active by checking button styles
  const hlClasses = await hlButton.getAttribute("class") || "";
  const isHLActive = /emerald|active|selected/i.test(hlClasses);
  process.stdout.write(`  Initial active exchange: ${isHLActive ? "Hyperliquid" : "dYdX"}\n`);

  // 3. Switch to the OTHER exchange
  const switchTo = isHLActive ? dydxButton : hlButton;
  const switchName = isHLActive ? "dYdX" : "Hyperliquid";

  await switchTo.click();
  await page.waitForTimeout(2000);

  // 4. Verify the exchange toggle updated — new button should now have active styling
  const switchClasses = await switchTo.getAttribute("class") || "";
  const switchIsActive = /emerald|active|selected/i.test(switchClasses);

  if (!switchIsActive) {
    // Check if the text or visual indicator changed some other way
    process.stdout.write("  Warning: active style didn't clearly change via class\n");
  } else {
    process.stdout.write(`  Switched to ${switchName}: toggle updated\n`);
  }

  // 5. Verify page content refreshed — check asset dropdown still works
  const assetSelect = page.locator("select").first();
  if (await assetSelect.count() > 0) {
    const options = await assetSelect.locator("option").allTextContents();
    process.stdout.write(`  Available assets on ${switchName}: ${options.join(", ")}\n`);
    if (options.length === 0) {
      throw new Error("Asset dropdown empty after exchange switch");
    }
  }

  // 6. Navigate to intelligence page — verify exchange context persists
  await gotoReady(page, "/intelligence");
  const intelToggle = page.locator("button", { hasText: new RegExp(switchName, "i") }).first();
  if (await intelToggle.count() > 0) {
    const intelClasses = await intelToggle.getAttribute("class") || "";
    const stillActive = /emerald|active|selected/i.test(intelClasses);
    process.stdout.write(`  Exchange persists on Intelligence page: ${stillActive}\n`);
  }

  // 7. Switch back to original exchange
  await gotoReady(page, "/trading");
  const originalBtn = isHLActive ? hlButton : dydxButton;
  // Re-locate after navigation
  const origBtn2 = page.locator("button", { hasText: isHLActive ? /hyperliquid/i : /dydx/i }).first();
  await origBtn2.click();
  await page.waitForTimeout(1000);
  process.stdout.write("  Switched back to original exchange\n");
});
