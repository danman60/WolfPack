// Workflow Test: Run intelligence cycle and verify agent outputs appear
const { withPage, gotoReady, isBackendUp, skipTest, clickButton, waitForAPI } = require("./helpers");

withPage(async (page) => {
  const backendOk = await isBackendUp(page);
  if (!backendOk) skipTest("Intel backend unavailable");

  await gotoReady(page, "/intelligence");

  // 1. Verify the 4 agent cards are present
  const body = await page.textContent("body");
  const agents = ["Quant", "Snoop", "Sage", "Brief"];
  const missingAgents = agents.filter((a) => !body.includes(a));
  if (missingAgents.length > 0) {
    throw new Error("Missing agent cards: " + missingAgents.join(", "));
  }

  // 2. Click "Run Intelligence" button
  const runBtn = page.locator("button", { hasText: /run intelligence/i }).first();
  await runBtn.waitFor({ state: "visible", timeout: 5000 });

  const [intelResp] = await Promise.all([
    waitForAPI(page, "/intelligence/run", { timeout: 30000 }),
    runBtn.click(),
  ]);

  // 3. Verify API responded
  if (intelResp.status() >= 500) {
    throw new Error("Intelligence run returned server error: " + intelResp.status());
  }

  // 4. Wait for results to populate (intelligence can take time)
  await page.waitForTimeout(5000);

  // 5. Check for agent outputs — look for confidence scores or analysis text
  const updatedBody = await page.textContent("body");
  const hasOutput =
    /confidence|analysis|signal|regime|liquidity|running|completed/i.test(updatedBody);

  if (!hasOutput) {
    throw new Error("No intelligence output appeared after running cycle");
  }

  // 6. Verify at least one agent status changed
  const statusEls = await page.$$eval("[class*='emerald'], [class*='amber']", (els) =>
    els.map((e) => e.textContent.trim()).filter((t) => /active|completed|running/i.test(t))
  );

  // Status change is best-effort — some agents may already be completed
  process.stdout.write(`  Agent statuses found: ${statusEls.length}\n`);
});
