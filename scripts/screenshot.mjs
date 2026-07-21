import { chromium } from 'playwright';
const b = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });

// Login
await p.goto('http://localhost:5183/login', { waitUntil: 'networkidle' });
await p.fill('input[id="username"]', 'admin');
await p.fill('input[id="password"]', 'admin123');
await p.click('button[type="submit"]');
await p.waitForTimeout(2000);

// Navigate to demo
await p.goto('http://localhost:5183/demo', { waitUntil: 'networkidle' });
await p.waitForTimeout(3000);

// Expand all scenarios
const buttons = await p.$$('button:has-text("查看详情")');
for (const btn of buttons) {
  await btn.click();
  await p.waitForTimeout(500);
}
await p.waitForTimeout(1000);

// Screenshot
await p.screenshot({
  path: 'docs/screenshots/demo-full-page.png',
  fullPage: true,
});
console.log('Screenshot saved: docs/screenshots/demo-full-page.png');
await b.close();
