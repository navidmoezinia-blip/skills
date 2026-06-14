// Logged-out recon of FB Marketplace Galveston property rentals.
// Zero credentials. Goal: see what's reachable without login and map structure.
import { chromium } from 'playwright';

const URL = 'https://www.facebook.com/marketplace/galveston/propertyrentals';

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({
  userAgent:
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
  viewport: { width: 1280, height: 2000 },
  locale: 'en-US',
  ignoreHTTPSErrors: true,
});
const page = await ctx.newPage();

const result = { url: URL };
try {
  const resp = await page.goto(URL, { waitUntil: 'domcontentloaded', timeout: 30000 });
  result.httpStatus = resp ? resp.status() : null;
  await page.waitForTimeout(4000);
  result.finalUrl = page.url();
  result.title = await page.title();

  // Login wall signals
  const bodyText = (await page.evaluate(() => document.body?.innerText || '')).slice(0, 4000);
  result.loginWall =
    /log in|log into facebook|create new account|you must log in/i.test(bodyText);
  const emailField = await page.$('input[name="email"], input[type="email"]');
  const passField = await page.$('input[name="pass"], input[type="password"]');
  result.hasLoginForm = !!(emailField && passField);

  // Count anything that looks like a marketplace listing link
  const listingLinks = await page.$$eval('a[href*="/marketplace/item/"]', (as) =>
    as.slice(0, 10).map((a) => ({
      href: a.getAttribute('href'),
      text: (a.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 120),
    }))
  );
  result.listingLinkCount = listingLinks.length;
  result.sampleListings = listingLinks;
  result.bodyTextHead = bodyText.slice(0, 800);

  await page.screenshot({ path: 'galveston_rentals_loggedout.png', fullPage: false });
  result.screenshot = 'galveston_rentals_loggedout.png';
} catch (e) {
  result.error = String(e);
}

console.log(JSON.stringify(result, null, 2));
await browser.close();
