// Проверка майнера с подменой API: энергия, старт, таймер, сбор и вкладки.
const assert = require("node:assert/strict");
const { chromium } = require("playwright-core");

(async () => {
  const mod = require("@sparticuz/chromium"),
    bin = mod.default || mod;
  const browser = await chromium.launch({
    executablePath: await bin.executablePath(),
    args: bin.args,
    headless: true,
  });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.addInitScript(() => {
    window.Telegram = { WebApp: { initData: "signed-test" } };
  });

  let phase = "ready";
  let started = 0;
  let finish = 0;
  let balance = 12840;
  const calls = [];

  await page.route("**/miniapp/dojo/api/**", async (route) => {
    const action = route.request().url().split("/").pop();
    calls.push(action);
    const now = Date.now() / 1000;
    if (action === "start") {
      phase = "mining";
      started = now;
      finish = now + 5;
    }
    if (action === "collect") {
      phase = "ready";
      balance += 120;
    }
    if (phase === "mining" && now >= finish) phase = "ready_to_collect";
    const progress =
      phase === "mining"
        ? Math.max(0, Math.min(1, (now - started) / (finish - started)))
        : phase === "ready_to_collect"
          ? 1
          : 0;
    await route.fulfill({
      json: {
        phase,
        server_now: now,
        balance,
        reward: 120,
        cycle_seconds: 28800,
        started_at: started || null,
        finish_at: finish || null,
        remaining_ms:
          phase === "mining" ? Math.max(0, (finish - now) * 1000) : 0,
        progress,
        mined: 120,
      },
    });
  });

  await page.goto(process.env.DOJO_URL || "http://127.0.0.1:8080/miniapp/dojo");
  await page.waitForFunction(
    () =>
      document.querySelector("#action-label").textContent === "НАЧАТЬ МАЙНИНГ",
  );
  assert.match(await page.locator("#balance").textContent(), /^12\s840$/);
  assert.equal(await page.locator("#energy").textContent(), "100 / 100");
  assert.equal(await page.locator("#status").textContent(), "СЕНСЕЙ ГОТОВ");
  assert.ok(
    await page
      .locator("#app")
      .evaluate((n) => n.classList.contains("phase-ready")),
  );
  await page.screenshot({ path: ".cache/miner2-ready.png" });

  await page.click("#action");
  await page.waitForFunction(
    () => document.querySelector("#app").classList.contains("phase-mining"),
    { timeout: 5000 },
  );
  assert.match(
    await page.locator("#action-label").textContent(),
    /^\d\d:\d\d:\d\d$/,
  );
  await page.screenshot({ path: ".cache/miner2-mining.png" });

  await page.waitForFunction(
    () =>
      document.querySelector("#action-label").textContent.includes("ЗАБРАТЬ"),
    { timeout: 12000 },
  );
  assert.equal(await page.locator("#status").textContent(), "ЦИКЛ ЗАВЕРШЁН");
  assert.equal(await page.locator("#energy").textContent(), "0 / 100");
  await page.screenshot({ path: ".cache/miner2-done.png" });

  await page.click(".tab[data-tab='upgrades']");
  assert.equal(await page.locator("#view-upgrades").isVisible(), true);
  assert.equal(await page.locator("#view-mining").isVisible(), false);
  await page.screenshot({ path: ".cache/miner2-upgrades.png" });
  await page.click(".tab[data-tab='profile']");
  assert.equal(await page.locator("#view-profile").isVisible(), true);
  assert.match(
    await page.locator("#profile-balance").textContent(),
    /^12\s840 Coin$/,
  );
  await page.screenshot({ path: ".cache/miner2-profile.png" });
  await page.click(".tab[data-tab='mining']");

  await page.click("#info");
  assert.equal(await page.locator("#sheet").isVisible(), true);
  await page.waitForTimeout(450);
  await page.screenshot({ path: ".cache/miner2-rules.png" });
  await page.click(".sheet-done");
  assert.equal(await page.locator("#sheet").isVisible(), false);

  await page.click("#action");
  await page.waitForFunction(() =>
    /^12\s960$/.test(document.querySelector("#balance").textContent),
  );
  assert.match(await page.locator("#toast").textContent(), /\+120 SenseiCoin/);
  await page.waitForFunction(
    () =>
      document.querySelector("#action-label").textContent === "НАЧАТЬ МАЙНИНГ",
  );
  assert.deepEqual(errors, []);
  assert.deepEqual(calls.slice(0, 3), ["state", "start", "state"]);
  console.log(
    "Miner checks passed: energy, start, 8h countdown, tabs, rules, collect and balance.",
  );
  await browser.close();
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
