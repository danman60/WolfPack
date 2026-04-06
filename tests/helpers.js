// Shared test helpers for WolfPack Playwright CLI tests
const { chromium } = require("playwright");

const BASE_URL = process.argv[2] || process.env.BASE_URL || "http://localhost:3000";

async function withPage(fn, opts = {}) {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: opts.viewport || { width: 1280, height: 800 },
  });
  const page = await context.newPage();
  try {
    await fn(page, BASE_URL);
    process.stdout.write("PASS\n");
  } catch (err) {
    process.stderr.write("FAIL: " + err.message + "\n");
    process.exit(1);
  } finally {
    await browser.close();
  }
}

async function expectText(page, texts, label) {
  const body = await page.textContent("body");
  const missing = texts.filter((t) => !body.includes(t));
  if (missing.length > 0) {
    throw new Error(`${label}: missing text [${missing.join(", ")}]`);
  }
}

async function expectSelector(page, selector, label) {
  const el = await page.$(selector);
  if (!el) throw new Error(`${label}: selector not found: ${selector}`);
  return el;
}

// Navigate and wait for app to hydrate (avoids networkidle timeout from polling)
async function gotoReady(page, path) {
  await page.goto(BASE_URL + path, { waitUntil: "domcontentloaded", timeout: 15000 });
  // Wait for React hydration - nav renders on all pages
  await page.waitForSelector("nav", { timeout: 10000 });
  // Small buffer for React Query hooks to populate
  await page.waitForTimeout(1500);
}

// Check if intel backend is reachable (returns true/false)
async function isBackendUp(page) {
  try {
    const resp = await page.request.get(BASE_URL + "/intel/health", { timeout: 3000 });
    return resp.status() < 500;
  } catch {
    return false;
  }
}

// Skip test with SKIP exit code (exit 0 but print SKIP)
function skipTest(reason) {
  process.stdout.write("SKIP: " + reason + "\n");
  process.exit(0);
}

// Click a button by its visible text (case-insensitive partial match)
async function clickButton(page, text, opts = {}) {
  const btn = page.locator(`button`, { hasText: new RegExp(text, "i") }).first();
  await btn.waitFor({ state: "visible", timeout: opts.timeout || 5000 });
  await btn.click();
  return btn;
}

// Wait for a network response matching a URL pattern
async function waitForAPI(page, urlPattern, opts = {}) {
  return page.waitForResponse(
    (resp) => resp.url().includes(urlPattern),
    { timeout: opts.timeout || 15000 }
  );
}

// Fill a number input by its label text
async function fillByLabel(page, labelText, value) {
  const label = page.locator("text=" + labelText).first();
  const container = label.locator("..");
  const input = container.locator("input").first();
  await input.fill(String(value));
  return input;
}

// Get all visible button texts on the page
async function getButtonTexts(page) {
  return page.$$eval("button", (els) =>
    els.filter((b) => b.offsetParent !== null).map((b) => b.textContent.trim())
  );
}

// Assert that a response came back with a successful status
function assertOkResponse(resp, label) {
  if (!resp.ok()) {
    throw new Error(`${label}: expected 2xx, got ${resp.status()}`);
  }
}

module.exports = {
  withPage, expectText, expectSelector, gotoReady,
  isBackendUp, skipTest, clickButton, waitForAPI,
  fillByLabel, getButtonTexts, assertOkResponse, BASE_URL,
};
