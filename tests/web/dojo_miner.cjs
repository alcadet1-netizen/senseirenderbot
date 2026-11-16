// Проверка трёх фаз майнера с подменой API; нужен локальный сервер.
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
  let balance = 1000;
  let calls = [];
  await page.route("**/miniapp/dojo/api/**", async (route) => {
    const url = route.request().url();
    const action = url.split("/").pop();
    calls.push(action);
    const now = Date.now() / 1000;
    if (action === "kick") {
      phase = "mining";
      started = now;
      finish = now + 5;
    }
    if (action === "collect") {
      phase = "ready";
      balance += 120;
    }
    if (phase === "mining" && now >= finish) phase = "ready_to_collect";
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
        progress:
          phase === "mining"
            ? Math.max(0, Math.min(1, (now - started) / (finish - started)))
            : phase === "ready_to_collect"
              ? 1
              : 0,
        mined: 120,
      },
    });
  });

  await page.goto(process.env.DOJO_URL || "http://127.0.0.1:8080/miniapp/dojo");
  await page.waitForFunction(() =>
    document.querySelector("#action").textContent.includes("ПНУТЬ"),
  );
  assert.match(await page.locator("#balance").textContent(), /^1\s000$/);
  assert.equal(
    await page.locator("#action").getAttribute("class"),
    "primary kick",
  );
  await page.screenshot({ path: ".cache/miner-ready.png" });

  await page.click("#action");
  await page.waitForFunction(
    () => document.querySelector("#frame").classList.contains("mode-kicking"),
    { timeout: 4000 },
  );
  await page.screenshot({ path: ".cache/miner-kick.png" });
  await page.waitForFunction(
    () => document.querySelector("#frame").classList.contains("mode-mining"),
    { timeout: 8000 },
  );
  await page.screenshot({ path: ".cache/miner-mining.png" });

  await page.waitForFunction(
    () => document.querySelector("#action").textContent.includes("ЗАБРАТЬ"),
    { timeout: 10000 },
  );
  assert.equal(await page.locator("#timer").textContent(), "00:00:00");
  await page.screenshot({ path: ".cache/miner-done.png" });

  await page.click("#action");
  await page.waitForFunction(() =>
    /^1\s120$/.test(document.querySelector("#balance").textContent),
  );
  assert.match(await page.locator("#toast").textContent(), /\+120 SenseiCoin/);
  await page.waitForTimeout(1800);
  assert.equal(
    await page.locator("#action").getAttribute("class"),
    "primary kick",
  );
  assert.deepEqual(errors, []);
  assert.deepEqual(calls.slice(0, 3), ["state", "kick", "state"]);
  console.log(
    "Miner checks passed: ready, kick animation, 8h countdown, collect, balance and all three visuals.",
  );
  await browser.close();
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
