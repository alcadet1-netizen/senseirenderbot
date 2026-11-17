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
  let energyMax = 100;
  let claimed = false;
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
      balance += 20;
    }
    if (action === "task") {
      balance += 10000;
      energyMax = 200;
      claimed = true;
    }
    if (phase === "mining" && now >= finish) phase = "ready_to_collect";
    const progress =
      phase === "mining"
        ? Math.max(0, Math.min(1, (now - started) / (finish - started)))
        : phase === "ready_to_collect"
          ? 1
          : 0;
    if (action === "upgrades") {
      await route.fulfill({
        json: {
          upgrades: {
            pickaxe_level: 0,
            pickaxe_max: 100,
            pickaxe_rate: 15,
            pickaxe_next_rate: 25,
            pickaxe_stars: 10,
            energy_purchases: 0,
            energy_max_purchases: 100,
            energy_bonus: 0,
            energy_stars: 50,
            base_energy: 100,
            auto_collect: false,
            auto_stars: 1000,
          },
        },
      });
      return;
    }
    if (action === "bank") {
      await route.fulfill({
        json: {
          bank_balance: 900000,
          circulation: 100000,
          total_supply: 1000000,
          users: 42,
        },
      });
      return;
    }
    if (action === "share") {
      await route.fulfill({ json: { prepare_id: "prep-7", expires_at: 123 } });
      return;
    }
    if (action === "referrals") {
      await route.fulfill({
        json: {
          link: "https://t.me/Senseigame_bot?start=ref_7",
          level: 1,
          earned: 125.5,
          levels: [
            { level: 1, count: 3, active: 2 },
            { level: 2, count: 1, active: 1 },
            { level: 3, count: 0, active: 0 },
          ],
          rank: {
            title: "Новичок",
            emoji: "🥋",
            progress: 42,
            next: { title: "Ученик", required: 5 },
          },
          bonus: {
            eligible: true,
            paid: false,
            activity_days: 1,
            paid_upgrade: false,
          },
          members: [{ username: "student", active: true }],
        },
      });
      return;
    }
    if (action === "tasks") {
      await route.fulfill({
        json: {
          tasks: [
            {
              slug: "senseidurova",
              username: "SenseiDurova",
              title: "SenseiDurova",
              url: "https://t.me/SenseiDurova",
              reward_coins: 10000,
              energy_bonus: 100,
              claimed,
            },
          ],
        },
      });
      return;
    }
    const state = {
      phase,
      server_now: now,
      balance,
      reward: 20,
      next_reward: 20,
      energy:
        phase === "ready"
          ? energyMax
          : Math.max(
              0,
              energyMax -
                100 * Math.max(0, (Math.min(now, finish) - started) / 3600),
            ),
      energy_max: energyMax,
      energy_start: energyMax,
      energy_per_hour: 100,
      base_rate: 15,
      current_rate: 15,
      pickaxe_level: 0,
      energy_purchases: 0,
      auto_collect: false,
      cycle_seconds: 14400,
      started_at: started || null,
      finish_at: finish || null,
      remaining_ms: phase === "mining" ? Math.max(0, (finish - now) * 1000) : 0,
      progress,
      mined: 20,
    };
    if (action === "task") {
      Object.assign(state, {
        task: {
          slug: "senseidurova",
          username: "SenseiDurova",
          title: "SenseiDurova",
          url: "https://t.me/SenseiDurova",
          reward_coins: 10000,
          energy_bonus: 100,
          claimed: true,
        },
        reward_coins: 10000,
        energy_bonus: 100,
      });
    }
    await route.fulfill({ json: state });
  });

  await page.goto(process.env.DOJO_URL || "http://127.0.0.1:8080/miniapp/dojo");
  await page.waitForFunction(
    () =>
      document.querySelector("#action-label").textContent === "НАЧАТЬ МАЙНИНГ",
  );
  assert.match(await page.locator("#balance").textContent(), /^12\s840$/);
  assert.ok((await page.locator(".sakura-leaf").count()) >= 9);
  assert.ok((await page.locator(".matrix-col").count()) >= 9);
  assert.equal(await page.locator("#energy").textContent(), "100 / 100");
  assert.equal(await page.locator("#status").textContent(), "СЕНСЕЙ ГОТОВ");
  assert.ok(
    await page
      .locator("#app")
      .evaluate((n) => n.classList.contains("phase-ready")),
  );
  assert.equal(await page.locator("#mine-meter").isVisible(), true);
  assert.match(await page.locator("#chain-status").textContent(), /ОЖИДАНИЕ/);
  const roadmap = await page.locator(".roadmap-sticker").textContent();
  assert.match(roadmap, /ROAD MAP/);
  assert.match(roadmap, /AIRDROP/);
  assert.match(roadmap, /Q4 2026/);
  assert.match(roadmap, /TGE/);
  assert.match(roadmap, /КОГДА ВСЕ МОНЕТЫ ДОБЫТЫ/);
  await page.click("#roadmap");
  assert.equal(await page.locator("#roadmap-sheet").isVisible(), true);
  const roadmapModal = await page.locator("#roadmap-sheet").textContent();
  assert.match(roadmapModal, /TGE · FINISH MINE/);
  assert.match(roadmapModal, /WHEN ALL COINS ARE MINED/);
  assert.match(roadmapModal, /10,000,000,000/);
  await page.click("#roadmap-sheet .sheet-done");
  assert.equal(await page.locator("#roadmap-sheet").isVisible(), false);
  const readyBox = await page.locator("#orb").boundingBox();
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
  const miningBox = await page.locator("#orb").boundingBox();
  assert.ok(
    Math.abs(miningBox.y - readyBox.y) < 1,
    `action button moved from ${readyBox.y} to ${miningBox.y}`,
  );
  assert.equal(await page.locator("#mine-meter").isVisible(), true);
  assert.match(
    await page.locator("#chain-status").textContent(),
    /ЦЕПОЧКА · БЛОК/,
  );
  assert.match(
    await page.locator("#chain-line").textContent(),
    /HASH 0x[0-9a-f]+/,
  );
  assert.match(
    await page.locator("#chain-line").textContent(),
    /PULSE \d+ BPM/,
  );
  assert.equal(await page.locator(".orb-orbit").count(), 2);
  assert.ok((await page.locator(".mining-particles i").count()) >= 14);
  await page.screenshot({ path: ".cache/miner2-mining.png" });

  await page.waitForFunction(
    () =>
      document.querySelector("#action-label").textContent.includes("ЗАБРАТЬ"),
    { timeout: 12000 },
  );
  assert.equal(
    await page.locator("#status").textContent(),
    "ЦИКЛ ЗАВЕРШЁН · 100%",
  );
  assert.equal(await page.locator("#energy").textContent(), "0 / 100");
  assert.match(await page.locator("#chain-status").textContent(), /БЛОК ГОТОВ/);
  const doneBox = await page.locator("#orb").boundingBox();
  assert.ok(Math.abs(doneBox.y - readyBox.y) < 1);
  await page.screenshot({ path: ".cache/miner2-done.png" });

  await page.click(".tab[data-tab='upgrades']");
  assert.equal(await page.locator("#view-upgrades").isVisible(), true);
  assert.equal(await page.locator("#view-mining").isVisible(), false);
  assert.equal(await page.locator(".upgrade-card").count(), 3);
  assert.match(
    await page.locator(".upgrade-card").first().textContent(),
    /10 ⭐/,
  );
  await page.screenshot({ path: ".cache/miner2-upgrades.png" });
  await page.click(".tab[data-tab='bank']");
  assert.equal(await page.locator("#view-bank").isVisible(), true);
  assert.match(await page.locator("#bank-supply").textContent(), /1\s000\s000/);
  await page.screenshot({ path: ".cache/miner2-bank.png" });
  await page.click(".tab[data-tab='referrals']");
  assert.equal(await page.locator("#view-referrals").isVisible(), true);
  await page.waitForFunction(() =>
    document.querySelector("#ref-link").textContent.includes("t.me"),
  );
  assert.match(await page.locator("#ref-link").textContent(), /start=ref_7/);
  assert.equal(await page.locator("#ref-share").isVisible(), true);
  assert.match(await page.locator("#ref-share").textContent(), /ПОДЕЛИТЬСЯ/);
  await page.evaluate(() => {
    window.__shareUrl = "";
    window.Telegram.WebApp.openTelegramLink = (url) => {
      window.__shareUrl = url;
    };
  });
  await page.click("#ref-share");
  assert.match(
    await page.evaluate(() => window.__shareUrl),
    /^https:\/\/t\.me\/share\/url\?url=/,
  );
  await page.evaluate(() => {
    window.__sharedMessage = "";
    window.Telegram.WebApp.shareMessage = (id, callback) => {
      window.__sharedMessage = id;
      callback && callback(true);
    };
  });
  await page.click("#ref-share");
  assert.equal(await page.evaluate(() => window.__sharedMessage), "prep-7");
  await page.screenshot({ path: ".cache/miner2-referrals.png" });
  await page.click(".tab[data-tab='profile']");
  assert.equal(await page.locator("#view-profile").isVisible(), true);
  assert.match(
    await page.locator("#profile-balance").textContent(),
    /^12\s840 Coin$/,
  );
  await page.screenshot({ path: ".cache/miner2-profile.png" });

  await page.click(".tab[data-tab='tasks']");
  assert.equal(await page.locator("#view-tasks").isVisible(), true);
  assert.equal(await page.locator(".task-card").count(), 1);
  assert.match(await page.locator(".task-card").textContent(), /10\s000 Coin/);
  assert.match(await page.locator(".task-card").textContent(), /\+100 энергии/);
  await page.screenshot({ path: ".cache/miner2-tasks.png" });
  await page.click(".task-claim");
  await page.waitForFunction(() =>
    document.querySelector(".task-card").classList.contains("claimed"),
  );
  assert.match(
    await page.locator(".task-card").textContent(),
    /Награда получена/,
  );
  assert.equal(await page.locator("#energy").textContent(), "0 / 200");
  await page.waitForFunction(() =>
    /^22\s840$/.test(document.querySelector("#balance").textContent),
  );
  await page.screenshot({ path: ".cache/miner2-tasks-claimed.png" });
  await page.click(".tab[data-tab='mining']");

  await page.click("#info");
  assert.equal(await page.locator("#sheet").isVisible(), true);
  await page.waitForTimeout(450);
  await page.screenshot({ path: ".cache/miner2-rules.png" });
  await page.click(".sheet-done");
  assert.equal(await page.locator("#sheet").isVisible(), false);

  await page.click("#action");
  await page.waitForFunction(() =>
    /^22\s860$/.test(document.querySelector("#balance").textContent),
  );
  assert.equal(await page.locator("#energy").textContent(), "200 / 200");
  assert.match(await page.locator("#toast").textContent(), /\+20 SenseiCoin/);
  await page.waitForFunction(
    () =>
      document.querySelector("#action-label").textContent === "НАЧАТЬ МАЙНИНГ",
  );
  assert.deepEqual(errors, []);
  assert.deepEqual(
    calls
      .filter(
        (action) =>
          ![
            "tasks",
            "task",
            "upgrades",
            "bank",
            "buy",
            "referrals",
            "share",
          ].includes(action),
      )
      .slice(0, 3),
    ["state", "start", "state"],
  );
  console.log(
    "Miner checks passed: energy, start, 4h countdown, tabs, rules, collect and balance.",
  );
  await browser.close();
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
