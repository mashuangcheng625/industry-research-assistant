#!/usr/bin/env bash
set -u
REPO="/home/xiaoma/projects/大模型项目/llm-application-portfolio/industry-research-assistant"
cd "$REPO"

# Kill any leftover processes on our ports
kill $(lsof -t -i:8000 2>/dev/null) 2>/dev/null || true
kill $(lsof -t -i:5183 2>/dev/null) 2>/dev/null || true
sleep 1

# Start backend
cd "$REPO/backend"
PYTHONPATH=app ../.venv/bin/python -m uvicorn app_main:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!
echo "Backend PID=$BACKEND_PID"

# Start frontend
cd "$REPO/frontend"
npm run dev -- --host 127.0.0.1 --port 5183 &
FRONTEND_PID=$!
echo "Frontend PID=$FRONTEND_PID"

# Wait for backend
for i in $(seq 1 30); do
  curl -s -o /dev/null http://127.0.0.1:8000/health/live && break
  sleep 1
done
curl -s -o /dev/null -w "Backend ready: %{http_code}\n" http://127.0.0.1:8000/health/live

# Wait for frontend
for i in $(seq 1 30); do
  curl -s -o /dev/null http://127.0.0.1:5183/ && break
  sleep 1
done
curl -s -o /dev/null -w "Frontend ready: %{http_code}\n" http://127.0.0.1:5183/

# Take screenshots
echo "Starting screenshots..."
cd "$REPO"
mkdir -p docs/screenshots

npx playwright install chromium 2>/dev/null
node << 'NODEEOF'
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  // Login first
  await page.goto('http://localhost:5183/login', { waitUntil: 'networkidle' });
  await page.fill('input[id="username"]', 'admin');
  await page.fill('input[id="password"]', 'admin123');
  await page.click('button[type="submit"]');
  await page.waitForTimeout(2000);

  // Navigate to demo page
  await page.goto('http://localhost:5183/demo', { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);

  // Expand all scenarios
  const buttons = await page.$$('button:has-text("查看详情")');
  for (const btn of buttons) {
    await btn.click();
    await page.waitForTimeout(500);
  }
  await page.waitForTimeout(1000);

  // Screenshot: full page
  await page.screenshot({ path: 'docs/screenshots/demo-full-page.png', fullPage: true });
  console.log('Screenshot: demo-full-page.png');

  await browser.close();
  console.log('Done');
})().catch(e => { console.error(e); process.exit(1); });
NODEEOF

# Cleanup
kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
echo "Servers stopped"
