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
  const page = await browser.newPage({
    viewport: { width: 390, height: 844 },
    bypassCSP: true,
  });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.addInitScript(() => {
    window.Telegram = {
      WebApp: {
        initData: "signed-test",
        initDataUnsafe: { user: { id: 700000123 } },
      },
    };
  });

  let phase = "ready";
  let started = 0;
  let finish = 0;
  let balance = 12840;
  let energyMax = 100;
  let taskEnergy = 0;
  let cycleEnergyStart = 100;
  let burned = 0;
  let claimed = false;
  let burnRequestId = "";
  const calls = [];
  const boostUntil = Date.now() / 1000 + 3600;

  await page.route("**/miniapp/dojo/api/**", async (route) => {
    const action = route.request().url().split("/").pop();
    calls.push(action);
    const now = Date.now() / 1000;
    if (action === "start") {
      phase = "mining";
      started = now;
      finish = now + 9;
    }
    if (action === "collect") {
      phase = "ready";
      balance += 20;
    }
    if (action === "task") {
      balance += 10000;
      taskEnergy = 100;
      claimed = true;
    }
    if (action === "start") {
      cycleEnergyStart = energyMax + taskEnergy;
      taskEnergy = 0;
    }
    if (action === "burn") {
      const body = route.request().postDataJSON();
      burnRequestId = body.request_id || "";
      const amount = Number(body.amount) || 0;
      balance -= amount;
      burned += amount;
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
            boost_stars: 1,
            boost_percent: 50,
            boost_hours: 1,
            boost_purchased: true,
            boost_available: false,
            boost_once_per_cycle: true,
            boost_active: true,
            boost_until: boostUntil,
            boost_seconds_left: 3600,
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
          total_emitted: 1000000,
          emission_cap: 10000000000,
          emission_remaining: 9999000000,
          emission_percent: 0.01,
          burned,
          confiscated: 5000,
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
            {
              slug: "link-0123456789abcdef",
              kind: "link",
              button_label: "Запустить",
              title: "Приложение Сенсея",
              host: "app.example",
              url: "https://app.example/ref_7",
              reward_coins: 5000,
              energy_bonus: 50,
              claimed: false,
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
          ? energyMax + taskEnergy
          : phase === "ready_to_collect"
            ? 0
            : Math.max(
                0,
                energyMax +
                  taskEnergy -
                  100 * Math.max(0, (Math.min(now, finish) - started) / 3600),
              ),
      energy_max: energyMax,
      energy_start: energyMax + taskEnergy,
      task_energy_pending: taskEnergy,
      energy_per_hour: 100,
      base_rate: 15,
      current_rate: 15,
      pickaxe_level: 0,
      energy_purchases: 0,
      auto_collect: false,
      boost_until: boostUntil,
      boost_active: true,
      boost_seconds_left: 3600,
      boost_percent: 50,
      cycle_seconds: 10800,
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
  assert.equal(await page.locator("#boot").count(), 1);
  assert.equal(await page.locator(".boot-puff").count(), 9);
  assert.equal(await page.locator(".boot-spark").count(), 20);
  assert.ok(
    await page
      .locator(".boot-art")
      .evaluate((img) => img.complete && img.naturalWidth > 0),
  );
  // The live bar starts at zero and is painted by seedBoot().
  assert.match(await page.locator("#boot-percent").textContent(), /^\d+%$/);
  const bootStarted = Number.parseInt(
    await page.locator("#boot-percent").textContent(),
    10,
  );
  if (bootStarted < 100) {
    await page.waitForFunction(
      (previous) =>
        Number.parseInt(
          document.querySelector("#boot-percent").textContent,
          10,
        ) > previous,
      bootStarted,
      { timeout: 3000 },
    );
  }
  await page.waitForFunction(
    () => document.querySelector("#boot")?.hidden,
    null,
    {
      timeout: 6000,
    },
  );
  assert.equal(await page.locator("#boot").isVisible(), false);
  await page.waitForFunction(
    () =>
      document.querySelector("#action-label").textContent === "НАЧАТЬ МАЙНИНГ",
  );
  assert.match(await page.locator("#balance").textContent(), /^12\s840$/);
  assert.ok((await page.locator(".sakura-leaf").count()) >= 9);
  assert.ok((await page.locator(".matrix-col").count()) >= 9);
  assert.equal(await page.locator("#energy").textContent(), "100 / 100");
  assert.equal(await page.locator("#status").textContent(), "СЕНСЕЙ ГОТОВ");
  assert.equal(await page.locator("#boost-pill").isVisible(), true);
  assert.match(await page.locator("#boost-pill").textContent(), /СКОРОСТЬ/);
  assert.ok(
    await page
      .locator("#app")
      .evaluate((n) => n.classList.contains("phase-ready")),
  );
  assert.equal(await page.locator("#mine-meter").isVisible(), true);
  assert.match(await page.locator("#chain-status").textContent(), /ОЖИДАНИЕ/);
  assert.equal(await page.locator("#bonus-sheet").isVisible(), false);
  assert.equal(await page.locator("#burn").isVisible(), true);
  await page.click("#bonus-open");
  assert.equal(await page.locator("#bonus-sheet").isVisible(), true);
  assert.equal(await page.locator("#bonus-open").getAttribute("aria-expanded"), "true");
  for (const selector of ["#roadmap", "#daily-open", "#chest-open"]) {
    const box = await page.locator(selector).boundingBox();
    assert.ok(Math.abs(box.width - box.height) < 1, `${selector} must be square`);
  }
  const roadmap = await page.locator(".roadmap-sticker").textContent();
  assert.match(roadmap, /ROAD MAP/);
  assert.doesNotMatch(roadmap, /AIRDROP|Q4 2026|TGE|КОГДА/);
  await page.click("#roadmap");
  assert.equal(await page.locator("#roadmap-sheet").isVisible(), true);
  const roadmapModal = await page.locator("#roadmap-sheet").textContent();
  assert.match(roadmapModal, /TGE · FINISH MINE/);
  assert.match(roadmapModal, /WHEN ALL COINS ARE MINED/);
  assert.match(roadmapModal, /10,000,000,000/);
  assert.match(roadmapModal, /DEX LISTING/);
  assert.match(roadmapModal, /PLANNED · NO DATE/);
  await page.click("#roadmap-sheet .sheet-done");
  assert.equal(await page.locator("#roadmap-sheet").isVisible(), false);
  const readyBox = await page.locator("#orb").boundingBox();
  assert.ok(readyBox.width <= 182, `orb is too wide: ${readyBox.width}`);
  assert.equal(await page.locator("#timer-face").isVisible(), false);
  assert.equal(await page.locator(".ambient-aura").count(), 1);
  assert.equal(await page.locator(".ambient-ray").count(), 1);
  assert.ok((await page.locator("#ambient-mist .ambient-puff").count()) >= 3);
  assert.ok((await page.locator("#ambient-dust .ambient-mote").count()) >= 12);
  const burnFlame = await page.locator(".burn-flame").boundingBox();
  const burnTitle = await page.locator(".burn-title").boundingBox();
  assert.ok(
    burnTitle.y >= burnFlame.y + burnFlame.height - 1,
    "BURN caption must sit below the flame",
  );
  const burnBox = await page.locator("#burn").boundingBox();
  const bonusBox = await page.locator("#bonus-open").boundingBox();
  assert.ok(burnBox.width > bonusBox.width, "BURN should be larger than BONUS");
  const readyFit = await page.evaluate(() => {
    const stage = document.querySelector(".stage");
    const action = document.querySelector("#action").getBoundingClientRect();
    const tabs = document.querySelector(".tabs").getBoundingClientRect();
    return {
      viewport: innerHeight,
      document: document.documentElement.scrollHeight,
      stage: stage.clientHeight,
      stageScroll: stage.scrollHeight,
      actionBottom: action.bottom,
      tabsTop: tabs.top,
    };
  });
  assert.ok(readyFit.document <= readyFit.viewport + 1, "page scrolls");
  assert.ok(readyFit.stageScroll <= readyFit.stage + 1, "stage scrolls");
  assert.ok(readyFit.actionBottom <= readyFit.tabsTop + 1, "orb overlaps tabs");
  await page.screenshot({ path: ".cache/miner2-ready.png" });

  await page.click("#action");
  await page.waitForFunction(
    () => document.querySelector("#app").classList.contains("phase-mining"),
    { timeout: 5000 },
  );
  const stageForTrail = await page.locator("#orb").boundingBox();
  const x = stageForTrail.x + stageForTrail.width / 2;
  const y = stageForTrail.y + stageForTrail.height / 2;
  await page.mouse.move(x - 35, y);
  await page.mouse.down();
  await page.mouse.move(x + 35, y + 15, { steps: 12 });
  await page.waitForTimeout(80);
  assert.ok(await page.locator("#magic-trail").evaluate(canvas => {
    const pixels = canvas.getContext("2d").getImageData(0, 0, canvas.width, canvas.height).data;
    for (let i = 3; i < pixels.length; i += 4) if (pixels[i] > 0) return true;
    return false;
  }), "moving while pressed should draw a trail");
  await page.mouse.up();
  await page.waitForTimeout(1000);
  assert.ok(await page.locator("#magic-trail").evaluate(canvas => {
    const pixels = canvas.getContext("2d").getImageData(0, 0, canvas.width, canvas.height).data;
    for (let i = 3; i < pixels.length; i += 4) if (pixels[i] > 0) return false;
    return true;
  }), "trail must fade after release");
  await page.emulateMedia({ reducedMotion: "reduce" });
  assert.equal(await page.locator("#magic-trail").isVisible(), false);
  await page.emulateMedia({ reducedMotion: "no-preference" });
  assert.match(
    await page.locator("#action-label").textContent(),
    /^\d\d:\d\d:\d\d$/,
  );
  const miningBox = await page.locator("#orb").boundingBox();
  assert.ok(
    Math.abs(miningBox.y - readyBox.y) < 1,
    `action button moved from ${readyBox.y} to ${miningBox.y}`,
  );
  assert.equal(await page.locator("#timer-face").isVisible(), true);
  assert.equal(await page.locator(".timer-seg").count(), 42);
  assert.ok(
    (await page.locator(".timer-seg.is-on").count()) >= 20,
    "the bespoke timer face should light its digit blades",
  );
  const timerBox = await page.locator("#timer-digits").boundingBox();
  assert.ok(
    Math.abs(
      timerBox.x + timerBox.width / 2 - (miningBox.x + miningBox.width / 2),
    ) < 1,
    "the timer must be centred in the orb",
  );
  assert.equal(await page.locator("#mine-meter").isVisible(), true);
  assert.match(
    await page.locator("#chain-status").textContent(),
    /ЦЕПОЧКА · БЛОК/,
  );
  const chainRows = page.locator("#chain-feed .chain-row");
  assert.equal(await chainRows.count(), 3);
  assert.match(await chainRows.first().textContent(), /смайнил блок/);
  assert.match(await chainRows.first().textContent(), /\d{3}….{2}/);
  assert.match(await page.locator("#chain-bpm").textContent(), /\d+ BPM/);
  assert.equal(
    await page
      .locator("#chain-feed")
      .evaluate((node) => getComputedStyle(node).overflowY),
    "hidden",
  );
  assert.equal(
    await page
      .locator("#chain-feed")
      .evaluate((node) => getComputedStyle(node).pointerEvents),
    "none",
  );
  const firstRow = await chainRows.first().textContent();
  await page.waitForTimeout(8200);
  assert.notEqual(await chainRows.first().textContent(), firstRow);
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
  assert.equal(await page.locator("#timer-face").isVisible(), false);
  await page.screenshot({ path: ".cache/miner2-done.png" });

  await page.click(".tab[data-tab='upgrades']");
  assert.equal(await page.locator("#view-upgrades").isVisible(), true);
  assert.equal(await page.locator("#view-mining").isVisible(), false);
  assert.equal(await page.locator(".upgrade-card").count(), 4);
  assert.match(
    await page.locator(".upgrade-card").nth(2).textContent(),
    /1 ⭐.*КУПЛЕНО В ЦИКЛЕ/s,
  );
  assert.equal(
    await page
      .locator(".upgrade-card")
      .nth(2)
      .locator(".upgrade-buy")
      .isDisabled(),
    true,
  );
  assert.match(
    await page.locator(".upgrade-card").nth(2).textContent(),
    /АКТИВЕН/,
  );
  assert.match(
    await page.locator(".upgrade-card").first().textContent(),
    /10 ⭐/,
  );
  await page.screenshot({ path: ".cache/miner2-upgrades.png" });
  await page.click(".tab[data-tab='bank']");
  assert.equal(await page.locator("#view-bank").isVisible(), true);
  assert.match(await page.locator("#bank-supply").textContent(), /1\s000\s000/);
  assert.match(await page.locator("#bank-burned").textContent(), /^0 Coin$/);
  assert.match(
    await page.locator("#bank-confiscated").textContent(),
    /5\s000 Coin/,
  );
  assert.ok(
    (await page.evaluate(
      () =>
        document.querySelector("#bank-progress").getBoundingClientRect().width,
    )) > 0,
    "emission bar should be visible even at a tiny percentage",
  );
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
  await page.waitForFunction(() => window.__sharedMessage === "prep-7", {
    timeout: 3000,
  });
  assert.equal(await page.evaluate(() => window.__sharedMessage), "prep-7");
  await page.screenshot({ path: ".cache/miner2-referrals.png" });
  await page.click(".tab[data-tab='profile']");
  assert.equal(await page.locator("#view-profile").isVisible(), true);
  assert.match(
    await page.locator("#profile-balance").textContent(),
    /^12\s840 Coin$/,
  );
  assert.doesNotMatch(
    await page.locator("#view-profile").textContent(),
    /как в чате/i,
  );
  await page.screenshot({ path: ".cache/miner2-profile.png" });

  await page.click(".tab[data-tab='tasks']");
  assert.equal(await page.locator("#view-tasks").isVisible(), true);
  assert.equal(await page.locator(".task-card").count(), 2);
  assert.match(
    await page.locator(".task-card:not(.is-link)").textContent(),
    /10\s000 Coin/,
  );
  assert.match(
    await page.locator(".task-card:not(.is-link)").textContent(),
    /\+100 энергии/,
  );
  const linkCard = page.locator(".task-card.is-link");
  assert.match(await linkCard.textContent(), /Приложение Сенсея/);
  assert.match(await linkCard.textContent(), /Запустить/);
  assert.equal(
    await linkCard.locator(".task-link").getAttribute("href"),
    "https://app.example/ref_7",
  );
  await page.screenshot({ path: ".cache/miner2-tasks.png" });
  await page.click(".task-card:not(.is-link) .task-claim");
  await page.waitForFunction(() =>
    document.querySelector(".task-card").classList.contains("claimed"),
  );
  assert.match(
    await page.locator(".task-card:not(.is-link)").textContent(),
    /Награда получена/,
  );
  assert.equal(await page.locator("#energy").textContent(), "0 / 100");
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
  assert.equal(await page.locator("#energy").textContent(), "200 / 100");
  assert.match(await page.locator("#toast").textContent(), /\+20 SenseiCoin/);
  await page.waitForFunction(
    () =>
      document.querySelector("#action-label").textContent === "НАЧАТЬ МАЙНИНГ",
  );

  await page.click("#burn");
  assert.equal(await page.locator("#burn-sheet").isVisible(), true);
  assert.match(
    await page.locator("#burn-sheet").textContent(),
    /СЖЕЧЬ ЭМИССИЮ/,
  );
  assert.match(await page.locator("#burn-sheet").textContent(), /TGE/);
  await page.fill("#burn-amount", "1000");
  assert.equal(await page.locator("#burn-preview").textContent(), "1\u00a0000");
  await page.click("#burn-confirm");
  await page.waitForFunction(() =>
    /^21\s860$/.test(document.querySelector("#balance").textContent),
  );
  assert.equal(await page.locator("#burn-sheet").isVisible(), false);
  assert.match(await page.locator("#toast").textContent(), /Сожжено/);
  assert.match(burnRequestId, /^[A-Za-z0-9_-]{8,64}$/);
  assert.deepEqual(errors, []);
  // EN must translate the loading screen too (key parity is enforced by the
  // RU data-i18n strings, so a missing entry would leak Russian here).
  await page.evaluate(() => localStorage.setItem("sensei_dojo_language", "en"));
  await page.reload({ waitUntil: "domcontentloaded" });
  await page.waitForFunction(
    () => document.querySelector("#boot")?.hidden,
    null,
    {
      timeout: 6000,
    },
  );
  assert.equal(await page.locator("#boot-status").textContent(), "LOADING…");
  assert.equal(
    await page.locator("#boot-track").getAttribute("aria-label"),
    "Loading SenseiCoin",
  );
  assert.equal(await page.evaluate(() => document.documentElement.lang), "en");
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
            "burn",
          ].includes(action),
      )
      .slice(0, 3),
    ["state", "start", "state"],
  );
  console.log(
    "Miner checks passed: energy, start, 3h countdown, tabs, rules, collect and balance.",
  );
  await browser.close();
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
