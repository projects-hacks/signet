import { chromium } from "playwright";
const b = await chromium.launch();
const page = await b.newPage({ viewport: { width: 1280, height: 1100 }, deviceScaleFactor: 2 });
const errs = [];
page.on("pageerror", e => errs.push(e.message));

await page.goto("http://127.0.0.1:8822/verify/", { waitUntil: "networkidle" });
await page.waitForSelector(".sample-chip");

// 1: doctored sample -> Reading table's disagreeing row must be red, labels human
await page.click(".sample-chip:nth-of-type(2)");
await page.waitForFunction(() => document.querySelector(".brand-field input")?.value.length > 0);
await page.click('button[type="submit"]');
await page.waitForFunction(() => /FLAGGED|CERTIFIED/.test(document.body.innerText), null, { timeout: 180000 });
await page.waitForTimeout(2000);
const cross = page.locator('.reading-table tr[data-agrees="false"] .reading-verdict');
console.log("disagree rows:", await cross.count());
console.log("cross colour:", await cross.first().evaluate(el => getComputedStyle(el).color));
console.log("field label:", await page.locator('.reading-table tr[data-agrees="false"] .reading-field').first().innerText());
const reading = await page.locator(".reading").boundingBox();
await page.screenshot({ path: "/tmp/fix-reading.png", clip: { x: reading.x, y: reading.y, width: reading.width, height: Math.min(reading.height, 560) } });

// 2: genuine sample -> then revisit the doctored entry; its image must still live
await page.click(".sample-chip:first-of-type").catch(async () => {
  // chips hidden once a result is shown; re-fetch through the API path instead
});
