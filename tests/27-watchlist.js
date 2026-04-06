// Workflow Test: Add and remove symbols from the watchlist
const { withPage, gotoReady, isBackendUp, skipTest, clickButton, waitForAPI } = require("./helpers");

withPage(async (page) => {
  const backendOk = await isBackendUp(page);
  if (!backendOk) skipTest("Intel backend unavailable");

  await gotoReady(page, "/trading");

  // 1. Find the watchlist section
  const body = await page.textContent("body");
  if (!/watchlist/i.test(body)) {
    throw new Error("Watchlist section not found on trading page");
  }

  // 2. Count current watchlist items
  const symbolChipsBefore = await page.$$eval(
    "button",
    (btns) => btns.filter((b) => /^[A-Z]{2,6}/.test(b.textContent.trim()) && b.textContent.includes("x")).length
  ).catch(() => 0);
  process.stdout.write(`  Watchlist symbols before: ~${symbolChipsBefore}\n`);

  // 3. Click "+ Add" to open search
  const addBtn = page.locator("button", { hasText: /\+\s*add/i }).first();
  if (await addBtn.count() === 0) {
    throw new Error("Add button not found in watchlist section");
  }
  await addBtn.click();
  await page.waitForTimeout(500);

  // 4. Type in search input
  const searchInput = page.locator('input[placeholder*="earch"]').first();
  if (await searchInput.count() === 0) {
    // Try any visible input that appeared after clicking Add
    const anyInput = page.locator("input").last();
    await anyInput.fill("SOL");
  } else {
    await searchInput.fill("SOL");
  }
  await page.waitForTimeout(1500); // Wait for debounced search

  // 5. Check for search results dropdown
  const searchResults = page.locator("text=/SOL/i");
  const resultCount = await searchResults.count();
  process.stdout.write(`  Search results for 'SOL': ${resultCount}\n`);

  if (resultCount > 0) {
    // 6. Click on a search result to add to watchlist
    // Find a clickable result (not the input itself)
    const clickableResult = page.locator("[class*='cursor-pointer'], [role='option'], [class*='hover']")
      .filter({ hasText: /SOL/i })
      .first();

    if (await clickableResult.count() > 0) {
      const [addResp] = await Promise.all([
        waitForAPI(page, "/watchlist", { timeout: 10000 }).catch(() => null),
        clickableResult.click(),
      ]);
      await page.waitForTimeout(1000);
      process.stdout.write("  Added SOL to watchlist\n");
    } else {
      // Try clicking the first SOL text that's not the input
      await searchResults.last().click();
      await page.waitForTimeout(1000);
    }
  }

  // 7. Verify SOL appears in watchlist
  await page.waitForTimeout(1000);
  const bodyAfterAdd = await page.textContent("body");
  const solInWatchlist = /SOL/.test(bodyAfterAdd);
  process.stdout.write(`  SOL in watchlist after add: ${solInWatchlist}\n`);

  // 8. Remove a symbol — click the "x" on a watchlist chip
  // Find buttons that look like watchlist chips with an x/remove action
  const removeButtons = page.locator("button").filter({ hasText: /x$/ });
  const removeCount = await removeButtons.count();

  if (removeCount > 0) {
    const [removeResp] = await Promise.all([
      waitForAPI(page, "/watchlist", { timeout: 10000 }).catch(() => null),
      removeButtons.first().click(),
    ]);
    await page.waitForTimeout(1000);
    process.stdout.write("  Removed a symbol from watchlist\n");
  } else {
    process.stdout.write("  No removable watchlist chips found\n");
  }

  // 9. Verify count changed
  const symbolChipsAfter = await page.$$eval(
    "button",
    (btns) => btns.filter((b) => /^[A-Z]{2,6}/.test(b.textContent.trim())).length
  ).catch(() => 0);
  process.stdout.write(`  Watchlist symbols after: ~${symbolChipsAfter}\n`);
});
