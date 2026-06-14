// Live login + throttled sample scrape of FB Marketplace Galveston rentals.
// Credentials come from env (FB_USER / FB_PASS) — never hardcoded/committed.
import { chromium } from 'playwright';

const USER = process.env.FB_USER;
const PASS = process.env.FB_PASS;
const SEARCH = 'https://www.facebook.com/marketplace/galveston/propertyrentals';

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const out = {};

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({
  userAgent:
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
  viewport: { width: 1280, height: 2200 },
  locale: 'en-US',
  ignoreHTTPSErrors: true,
});
const page = await ctx.newPage();

try {
  // 1. Load login page
  await page.goto('https://www.facebook.com/login', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await sleep(1500);

  // Accept cookie banner if present (best-effort)
  try {
    const btn = await page.$('[data-cookiebanner="accept_button"], [aria-label*="Allow all"]');
    if (btn) { await btn.click(); await sleep(800); }
  } catch {}

  // 2. Fill credentials, human-paced
  await page.fill('input[name="email"]', USER, { timeout: 15000 });
  await sleep(700);
  await page.fill('input[name="pass"]', PASS, { timeout: 15000 });
  await sleep(700);
  await Promise.all([
    page.waitForLoadState('networkidle', { timeout: 30000 }).catch(() => {}),
    page.press('input[name="pass"]', 'Enter'),
  ]);
  await sleep(6000);

  out.afterLoginUrl = page.url();
  out.afterLoginTitle = await page.title();
  const body = (await page.evaluate(() => document.body?.innerText || '')).replace(/\s+/g, ' ');

  // 3. Classify outcome
  out.checkpoint = /checkpoint|two_factor|confirm your identity|enter the code|we sent|login code|two-factor|approve your login|recognize your device/i.test(out.afterLoginUrl + ' ' + body);
  out.stillLoginForm = !!(await page.$('input[name="pass"]'));
  out.wrongPassword = /password (you|that) entered is incorrect|wrong password|the password you’ve entered/i.test(body);
  out.loggedIn = !out.stillLoginForm && !out.checkpoint && /facebook\.com/.test(out.afterLoginUrl) && !/\/login/.test(out.afterLoginUrl);

  out.bodyHead = body.slice(0, 600);
  await page.screenshot({ path: 'login_result.png' });

  // 4. If logged in, do ONE gentle pass at the rentals search
  if (out.loggedIn) {
    await sleep(2000);
    await page.goto(SEARCH, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await sleep(5000);
    // gentle scroll to load a few rows
    for (let i = 0; i < 3; i++) { await page.mouse.wheel(0, 1600); await sleep(2500); }
    out.searchUrl = page.url();
    const listings = await page.$$eval('a[href*="/marketplace/item/"]', (as) => {
      const seen = new Set();
      const rows = [];
      for (const a of as) {
        const href = (a.getAttribute('href') || '').split('?')[0];
        if (seen.has(href)) continue;
        seen.add(href);
        rows.push({ href, text: (a.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 160) });
        if (rows.length >= 12) break;
      }
      return rows;
    });
    out.listingCount = listings.length;
    out.sampleListings = listings;
    await page.screenshot({ path: 'marketplace_result.png', fullPage: false });
  }
} catch (e) {
  out.error = String(e).slice(0, 500);
}

console.log(JSON.stringify(out, null, 2));
await browser.close();
