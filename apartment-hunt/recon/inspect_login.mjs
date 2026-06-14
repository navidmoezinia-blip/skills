import { chromium } from 'playwright';
const b = await chromium.launch({ headless: true });
const ctx = await b.newContext({ ignoreHTTPSErrors: true, locale: 'en-US',
  userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36' });
const p = await ctx.newPage();
await p.goto('https://www.facebook.com/login', { waitUntil: 'domcontentloaded', timeout: 30000 });
await p.waitForTimeout(2500);
const buttons = await p.$$eval('button, [role="button"], input[type="submit"]', els =>
  els.slice(0,20).map(e => ({ tag: e.tagName, type: e.getAttribute('type'), name: e.getAttribute('name'),
    id: e.id||null, testid: e.getAttribute('data-testid'), aria: e.getAttribute('aria-label'),
    text: (e.innerText||e.value||'').trim().slice(0,40) })));
const inputs = await p.$$eval('input', els => els.map(e => ({ name: e.getAttribute('name'), type: e.getAttribute('type'), id: e.id||null })));
console.log(JSON.stringify({ url: p.url(), inputs, buttons }, null, 2));
await b.close();
