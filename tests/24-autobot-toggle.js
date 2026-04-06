// Workflow Test: Auto-Bot toggle on/off and configuration
const { withPage, gotoReady, isBackendUp, skipTest, clickButton, waitForAPI } = require("./helpers");

withPage(async (page) => {
  const backendOk = await isBackendUp(page);
  if (!backendOk) skipTest("Intel backend unavailable");

  await gotoReady(page, "/auto-bot");

  // 1. Verify page loaded with Auto-Bot controls
  const body = await page.textContent("body");
  if (!/auto.?bot|auto.?trad/i.test(body)) {
    throw new Error("Auto-Bot page did not load properly");
  }

  // 2. Check initial status (Active or Paused)
  const isActive = /active/i.test(body) && !/paused/i.test(body);
  process.stdout.write(`  Initial state: ${isActive ? "Active" : "Paused"}\n`);

  // 3. Toggle the bot — click Enable or Disable
  const toggleText = isActive ? "Disable" : "Enable";
  const toggleBtn = page.locator("button", { hasText: new RegExp(`^${toggleText}$`, "i") }).first();

  if (await toggleBtn.count() === 0) {
    throw new Error(`Expected "${toggleText}" button not found`);
  }

  const [toggleResp] = await Promise.all([
    waitForAPI(page, "/auto-trader/toggle", { timeout: 10000 }),
    toggleBtn.click(),
  ]);

  if (toggleResp.status() >= 500) {
    throw new Error("Toggle auto-trader returned server error: " + toggleResp.status());
  }

  await page.waitForTimeout(1500);

  // 4. Verify status changed
  const bodyAfter = await page.textContent("body");
  const isActiveAfter = /active/i.test(bodyAfter);
  const isPausedAfter = /paused/i.test(bodyAfter);
  process.stdout.write(`  After toggle: active=${isActiveAfter}, paused=${isPausedAfter}\n`);

  // 5. Configure conviction threshold
  const convictionInput = page.locator('input[type="number"]').first();
  if (await convictionInput.count() > 0) {
    await convictionInput.fill("80");
    await page.waitForTimeout(300);

    // Click Save Config
    const saveBtn = page.locator("button", { hasText: /save/i }).first();
    if (await saveBtn.count() > 0) {
      const [configResp] = await Promise.all([
        waitForAPI(page, "/auto-trader/config", { timeout: 10000 }).catch(() => null),
        saveBtn.click(),
      ]);

      await page.waitForTimeout(1000);
      const saveBody = await page.textContent("body");
      const saved = /saved|success/i.test(saveBody);
      process.stdout.write(`  Config save: ${saved ? "confirmed" : "no confirmation seen"}\n`);
    }
  }

  // 6. Toggle back to original state
  const revertText = isActive ? "Enable" : "Disable";
  const revertBtn = page.locator("button", { hasText: new RegExp(`^${revertText}$`, "i") }).first();
  if (await revertBtn.count() > 0) {
    await Promise.all([
      waitForAPI(page, "/auto-trader/toggle", { timeout: 10000 }).catch(() => null),
      revertBtn.click(),
    ]);
    process.stdout.write("  Reverted to original state\n");
  }
});
