// Test: Mobile responsiveness - no horizontal overflow, content renders
const { withPage, expectText, gotoReady } = require("./helpers");

withPage(
  async (page) => {
    await gotoReady(page, "/");
    await expectText(page, ["WolfPack"], "Branding on mobile");

    const overflow = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
    }));

    if (overflow.scrollWidth > overflow.clientWidth + 10) {
      throw new Error(`Horizontal overflow: ${overflow.scrollWidth} > ${overflow.clientWidth}`);
    }

    const body = await page.textContent("body");
    if (body.length < 50) throw new Error("Page content too short on mobile");
  },
  { viewport: { width: 375, height: 812 } }
);
