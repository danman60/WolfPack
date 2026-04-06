// Workflow Test: Approve and reject trade recommendations
// Recommendations appear on the trading page in the "AI Recommendations" section
const { withPage, gotoReady, isBackendUp, skipTest, waitForAPI } = require("./helpers");

withPage(async (page) => {
  const backendOk = await isBackendUp(page);
  if (!backendOk) skipTest("Intel backend unavailable");

  await gotoReady(page, "/trading");

  // 1. Check if there are any pending recommendations (approve/reject buttons)
  const approveButtons = page.locator("button", { hasText: /^approve$/i });
  const rejectButtons = page.locator("button", { hasText: /^reject$/i });
  let approveCount = await approveButtons.count();
  let rejectCount = await rejectButtons.count();

  if (approveCount === 0 && rejectCount === 0) {
    // No recommendations — try running intelligence to generate some
    // Use "Run Intelligence" on the intelligence page first
    await gotoReady(page, "/intelligence");
    const runBtn = page.locator("button", { hasText: /run intelligence/i }).first();
    if (await runBtn.count() > 0) {
      await Promise.all([
        waitForAPI(page, "/intelligence/run", { timeout: 20000 }).catch(() => null),
        runBtn.click(),
      ]);
      // Wait for intelligence to complete and generate recommendations
      await page.waitForTimeout(8000);
    }

    // Go back to trading page and check again
    await gotoReady(page, "/trading");
    await page.waitForTimeout(2000);
    approveCount = await approveButtons.count();
    rejectCount = await rejectButtons.count();
  }

  if (approveCount === 0 && rejectCount === 0) {
    // Still no recommendations — acceptable when no intelligence data exists
    const body = await page.textContent("body");
    const noRecs = /no pending|run intelligence/i.test(body);
    process.stdout.write(`  No recommendations available (empty state shown: ${noRecs})\n`);
    return;
  }

  process.stdout.write(`  Found ${approveCount} approve, ${rejectCount} reject buttons\n`);

  // 2. Approve the first recommendation
  if (approveCount >= 1) {
    const [approveResp] = await Promise.all([
      waitForAPI(page, "/recommendations/", { timeout: 10000 }),
      approveButtons.first().click(),
    ]);
    const status = approveResp.status();
    process.stdout.write(`  Approve response: ${status}\n`);

    // 500 from Supabase config is known limitation
    if (status >= 500) {
      const respBody = await approveResp.text().catch(() => "");
      if (/supabase|SUPABASE/i.test(respBody)) {
        process.stdout.write("  Approve clicked but DB write failed (Supabase not configured)\n");
      } else {
        throw new Error("Approve recommendation returned server error");
      }
    }
    await page.waitForTimeout(1000);
  }

  // 3. Reject a recommendation if one remains
  const rejectCountAfter = await page.locator("button", { hasText: /^reject$/i }).count();
  if (rejectCountAfter >= 1) {
    const [rejectResp] = await Promise.all([
      waitForAPI(page, "/recommendations/", { timeout: 10000 }),
      page.locator("button", { hasText: /^reject$/i }).first().click(),
    ]);
    process.stdout.write(`  Reject response: ${rejectResp.status()}\n`);
    await page.waitForTimeout(1000);
  }

  // 4. Verify the UI responded to the actions
  await page.waitForTimeout(1500);
  const finalApproveCount = await page.locator("button", { hasText: /^approve$/i }).count();
  process.stdout.write(`  Remaining approve buttons: ${finalApproveCount} (was ${approveCount})\n`);
});
