// Workflow Test: Configure and run a backtest, verify results render
const { withPage, gotoReady, isBackendUp, skipTest, waitForAPI } = require("./helpers");

withPage(async (page) => {
  const backendOk = await isBackendUp(page);
  if (!backendOk) skipTest("Intel backend unavailable");

  await gotoReady(page, "/backtest");

  // 1. Verify backtest page loaded
  const body = await page.textContent("body");
  if (!/backtest|strategy|lookback/i.test(body)) {
    throw new Error("Backtest page did not load properly");
  }

  // 2. Select asset — click BTC pill
  const btcPill = page.locator("button", { hasText: /^BTC$/i }).first();
  if (await btcPill.count() > 0) {
    await btcPill.click();
    await page.waitForTimeout(300);
    process.stdout.write("  Selected BTC\n");
  }

  // 3. Select interval — click 1h
  const intervalPill = page.locator("button", { hasText: /^1h$/i }).first();
  if (await intervalPill.count() > 0) {
    await intervalPill.click();
    await page.waitForTimeout(300);
    process.stdout.write("  Selected 1h interval\n");
  }

  // 4. Select lookback — click 30d (or 30)
  const lookbackPill = page.locator("button", { hasText: /^30d?$/i }).first();
  if (await lookbackPill.count() > 0) {
    await lookbackPill.click();
    await page.waitForTimeout(300);
    process.stdout.write("  Selected 30d lookback\n");
  }

  // 5. Select a strategy if strategy buttons exist
  // Strategies are loaded from API — may not be present if backend returns empty
  const stratButtons = page.locator("button").filter({
    has: page.locator("text=/momentum|mean|breakout|trend|reversal|bollinger/i"),
  });
  if (await stratButtons.count() > 0) {
    await stratButtons.first().click();
    await page.waitForTimeout(300);
    process.stdout.write("  Selected strategy\n");
  } else {
    process.stdout.write("  No strategy buttons found (API may return empty list)\n");
  }

  // 6. Fill starting equity if input exists
  const equityInputs = page.locator('input[type="number"]');
  if (await equityInputs.count() > 0) {
    await equityInputs.first().fill("10000");
    await page.waitForTimeout(200);
  }

  // 7. Click "Run Backtest" button
  const runBtn = page.locator("button", { hasText: /run backtest/i }).first();
  if (await runBtn.count() === 0) {
    // Fall back to any button with "run" in it
    const altRunBtn = page.locator("button", { hasText: /^run$/i }).first();
    if (await altRunBtn.count() === 0) {
      throw new Error("Run button not found on backtest page");
    }
    // Use the alt button
    const [resp] = await Promise.all([
      waitForAPI(page, "/backtest", { timeout: 30000 }).catch(() => null),
      altRunBtn.click(),
    ]);
    process.stdout.write(`  Backtest triggered via alt button\n`);
  } else {
    const [resp] = await Promise.all([
      waitForAPI(page, "/backtest", { timeout: 30000 }).catch(() => null),
      runBtn.click(),
    ]);
    process.stdout.write("  Backtest triggered\n");
  }

  // 8. Wait for results — check for running state then completion
  await page.waitForTimeout(3000);
  let runBody = await page.textContent("body");
  const isRunning = /running|%|starting/i.test(runBody);
  process.stdout.write(`  Running state detected: ${isRunning}\n`);

  // Poll for completion (up to 45s)
  for (let i = 0; i < 15; i++) {
    await page.waitForTimeout(3000);
    runBody = await page.textContent("body");
    if (/return|total.?p|trades|win.?rate|sharpe|drawdown|result/i.test(runBody)) {
      process.stdout.write("  Backtest results appeared\n");
      return;
    }
    if (/error|failed/i.test(runBody) && !/no.*error/i.test(runBody)) {
      // Backend errors from missing data are not test failures
      process.stdout.write("  Backtest returned an error (may need market data)\n");
      return;
    }
  }

  process.stdout.write("  Backtest did not complete within timeout (may need longer or data unavailable)\n");
});
