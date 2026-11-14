// Telegram SDK contract mock, not a real Telegram client. Same dependencies as neon_dojo.cjs.
const assert = require("node:assert/strict");
const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");
let chromium;
try {
  ({ chromium } = require("playwright"));
} catch {
  ({ chromium } = require("playwright-core"));
}
(async () => {
  let executablePath = process.env.CHROMIUM_EXECUTABLE,
    args = ["--no-sandbox"];
  if (!executablePath) {
    try {
      const m = require("@sparticuz/chromium"),
        c = m.default || m;
      executablePath = await c.executablePath();
      args = c.args;
    } catch {}
  }
  const server = http.createServer((req, res) => {
    res.setHeader("Content-Type", "text/html");
    res.end(fs.readFileSync(path.resolve(__dirname, "../../index.html")));
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const browser = await chromium.launch({
    executablePath,
    args,
    headless: true,
  });
  try {
    const page = await browser.newPage(),
      errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.route("https://telegram.org/js/telegram-web-app.js", (route) =>
      route.fulfill({
        contentType: "application/javascript",
        body: `
      window.calls=[];window.handlers={};
      window.Telegram={WebApp:{initData:'mock-only',viewportStableHeight:700,
        ready(){calls.push('ready')},expand(){calls.push('expand')},
        isVersionAtLeast(v){return true},requestFullscreen(){calls.push('fullscreen')},disableVerticalSwipes(){calls.push('swipes-off')},
        safeAreaInset:{top:24,bottom:8,left:0,right:0},contentSafeAreaInset:{top:48,bottom:20,left:0,right:12},
        setHeaderColor(c){calls.push(c)},setBackgroundColor(c){calls.push(c)},
        onEvent(n,f){handlers[n]=f;if(n==='viewportChanged')window.viewportCallback=f},close(){calls.push('close')},
        BackButton:{show(){calls.push('back')},onClick(f){window.backCallback=f}},
        HapticFeedback:{impactOccurred(t){calls.push(t)}}}};
    `,
      }),
    );
    await page.goto(`http://127.0.0.1:${server.address().port}/miniapp/dojo`);
    await page.waitForFunction(() => window.calls?.includes("ready"));
    await page.getByRole("button", {name:"∞ Свободная битва", exact:true}).click();
    assert(
      await page.evaluate(
        () => calls.includes("expand") && calls.includes("back"),
      ),
    );
    assert.equal(
      await page.evaluate(() =>
        document.documentElement.style.getPropertyValue("--vh"),
      ),
      "700px",
    );
    assert(
      await page.evaluate(
        () => calls.includes("fullscreen") && calls.includes("swipes-off"),
      ),
    );
    assert.equal(
      await page.evaluate(() =>
        document.documentElement.style.getPropertyValue("--safe-top"),
      ),
      "72px",
    );
    assert.equal(
      await page.evaluate(() =>
        document.documentElement.style.getPropertyValue("--safe-bottom"),
      ),
      "28px",
    );
    await page.evaluate(() => {
      Telegram.WebApp.viewportStableHeight = 680;
      handlers.fullscreenChanged();
    });
    assert.equal(
      await page.evaluate(() =>
        document.documentElement.style.getPropertyValue("--vh"),
      ),
      "680px",
    );
    await page.evaluate(() => handlers.fullscreenFailed());
    assert.equal(await page.evaluate(() => neonDojo.game.state), "playing");

    await page.setViewportSize({ width: 568, height: 320 });
    await page.evaluate(() => {
      Telegram.WebApp.viewportStableHeight = 320;
      handlers.viewportChanged();
    });
    await page.waitForTimeout(80);
    assert(
      await page.evaluate(() => {
        const top = 72,
          bottom = 28;
        return (
          [
            "#fullscreenBtn",
            "#superBtn",
            "#towerBtn",
            "#upgradeBtn",
            "#boostBtn",
            ...Array.from({ length: 8 }, (_, i) => `.card:nth-child(${i + 1})`),
          ].every((s) => {
            const r = document.querySelector(s).getBoundingClientRect();
            return (
              r.top >= top &&
              r.bottom <= 320 - bottom + 1 &&
              r.left >= 0 &&
              r.right <= 568 + 1
            );
          }) && document.documentElement.scrollHeight <= 320
        );
      }),
      "safe-area padding must not hide controls or any card on a small fullscreen phone",
    );
    await page.evaluate(() => {
      neonDojo.game.ui.help();
      backCallback();
    });
    assert.equal(await page.evaluate(() => neonDojo.game.ui.modal.open), false);
    await page.evaluate(() => {
      neonDojo.game.vibrate();
      backCallback();
    });
    assert(
      await page.evaluate(
        () => calls.includes("light") && calls.includes("close"),
      ),
    );
    assert.deepEqual(errors, []);
    const fallback = await browser.newPage();
    fallback.on("pageerror", (e) => errors.push(e.message));
    await fallback.route("https://telegram.org/**", (route) => route.abort());
    await fallback.goto(
      `http://127.0.0.1:${server.address().port}/miniapp/dojo`,
    );
    assert.equal(await fallback.evaluate(() => neonDojo.game.state), "playing");
    assert.deepEqual(errors, []);
    const legacy = await browser.newPage();
    legacy.on("pageerror", (e) => errors.push(e.message));
    await legacy.route("https://telegram.org/js/telegram-web-app.js", (route) =>
      route.fulfill({
        contentType: "application/javascript",
        body: `window.legacyRequests=0;window.Telegram={WebApp:{initData:'old-client-mock',ready(){},expand(){},isVersionAtLeast(){return false},requestFullscreen(){legacyRequests++;throw Error('unsupported')}}}`,
      }),
    );
    await legacy.goto(`http://127.0.0.1:${server.address().port}/miniapp/dojo`);
    await legacy.waitForFunction(() => window.Telegram?.WebApp?.initData);
    assert.equal(await legacy.evaluate(() => legacyRequests), 0);
    assert.equal(await legacy.evaluate(() => neonDojo.game.state), "playing");
    assert.deepEqual(errors, []);
    console.log(
      "PASS: SDK ready/expand/fullscreen, swipe handling, safe insets, fullscreen events/failure, BackButton, haptic, legacy and SDK-failure fallbacks (mock only)",
    );
  } finally {
    await browser.close();
    await new Promise((resolve) => server.close(resolve));
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
