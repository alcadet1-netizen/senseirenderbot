/* Responsive UX regression in real Chromium. No production services required. */
const assert = require("node:assert/strict");
const { pathToFileURL } = require("node:url");
const path = require("node:path");
const { chromium } = require("playwright-core");
(async () => {
  const mod = require("@sparticuz/chromium"),
    c = mod.default || mod;
  const browser = await chromium.launch({
    executablePath:
      process.env.CHROMIUM_EXECUTABLE || (await c.executablePath()),
    args: c.args,
    headless: true,
  });
  const checks = [];
  try {
    const page = await browser.newPage(),
      errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto(
      pathToFileURL(path.resolve(__dirname, "../../index.html")).href,
    );
    for (const [w, h] of [
      [280, 480],
      [280, 740],
      [320, 568],
      [375, 667],
      [390, 844],
      [568, 320],
      [667, 375],
      [740, 360],
      [812, 375],
      [844, 390],
      [768, 1024],
      [1024, 768],
      [1440, 900],
      [1280, 1600],
    ]) {
      await page.setViewportSize({ width: w, height: h });
      await page.waitForTimeout(80);
      await page.evaluate(() => neonDojo.modes.main());
      assert(await page.evaluate(() => document.querySelector(".app").inert));
      const mainAudit = await page.evaluate(() => {
        const els = [
          document.querySelector(".modeBox"),
          ...document.querySelectorAll(".modeBox>button"),
        ];
        return els.every((el) => {
          const r = el.getBoundingClientRect();
          return (
            r.x >= 0 &&
            r.y >= 0 &&
            r.right <= innerWidth + 1 &&
            r.bottom <= innerHeight + 1
          );
        });
      });
      assert(mainAudit, `main menu ${w}x${h}`);
      await page
        .getByRole("button", {
          name: "⚔ Одиночная игра · 30 уровней",
          exact: true,
        })
        .click();
      for (const act of [1, 6]) {
        await page
          .getByRole("button", { name: `Акт ${act}`, exact: true })
          .click();
        assert.equal(await page.locator(".act-tabs button").count(), 6);
        assert.equal(await page.locator(".modeBox>button").count(), 6);
        assert(
          await page.evaluate(() => {
            const box = document.querySelector(".modeBox"),
              r = box.getBoundingClientRect();
            return (
              box.scrollHeight <= box.clientHeight + 1 &&
              r.top >= 0 &&
              r.bottom <= innerHeight + 1
            );
          }),
          `campaign without scroll ${w}x${h}`,
        );
      }
      await page
        .getByRole("button", { name: "← Главное меню", exact: true })
        .click();
      await page
        .getByRole("button", { name: "∞ Свободная битва", exact: true })
        .click();
      await page.waitForTimeout(40);
      const audit = await page.evaluate(() => {
        const selectors = [
          "#arena",
          "#cards",
          "#superBtn",
          "#upgradeBtn",
          "#towerBtn",
          "#boostBtn",
          "#modeMenuBtn",
          ...Array.from({ length: 8 }, (_, i) => `.card:nth-child(${i + 1})`),
        ];
        return selectors.filter((s) => {
          const el = document.querySelector(s),
            r = el.getBoundingClientRect();
          return (
            r.width < 1 ||
            r.height < 1 ||
            r.x < 0 ||
            r.y < 0 ||
            r.right > innerWidth + 1 ||
            r.bottom > innerHeight + 1
          );
        });
      });
      assert.deepEqual(audit, [], `battle ${w}x${h}`);
      assert(
        await page.evaluate(
          () =>
            document.documentElement.scrollHeight <= innerHeight + 1 &&
            document.documentElement.scrollWidth <= innerWidth + 1,
        ),
      );
      // Navigation belongs to the resource bar, never floats over the cards.
      assert(
        await page.evaluate(() => {
          const a = document
              .querySelector("#modeMenuBtn")
              .getBoundingClientRect(),
            b = document.querySelector("#cards").getBoundingClientRect();
          return a.bottom <= b.top;
        }),
      );
      checks.push(`menu, acts, 8 cards and controls fit ${w}x${h}`);
    }
    await page.setViewportSize({ width: 568, height: 320 });
    await page.evaluate(() => {
      document.documentElement.style.setProperty("--safe-top", "48px");
      document.documentElement.style.setProperty("--safe-bottom", "20px");
      document.documentElement.style.setProperty("--safe-left", "22px");
      document.documentElement.style.setProperty("--safe-right", "22px");
      neonDojo.modes.main();
    });
    await page.waitForTimeout(80);
    assert(
      await page.evaluate(() => {
        const r = document.querySelector(".modeBox").getBoundingClientRect();
        return (
          r.top >= 48 &&
          r.bottom <= innerHeight - 20 &&
          r.left >= 22 &&
          r.right <= innerWidth - 22
        );
      }),
    );
    checks.push("menu honors four Telegram safe insets");
    await page.evaluate(() => {
      for (const edge of ["top", "bottom", "left", "right"])
        document.documentElement.style.removeProperty("--safe-" + edge);
    });
    await page
      .getByRole("button", { name: "∞ Свободная битва", exact: true })
      .click();
    await page.evaluate(() => {
      const g = neonDojo.game;
      g.summon(0);
    });
    const army = await page.evaluate(() =>
      neonDojo.game.units.units.filter((u) => u.active).map((u) => u.seed),
    );
    await page.locator("#modeMenuBtn").click();
    const before = await page.evaluate(() => [
      neonDojo.game.elapsed,
      neonDojo.game.energy,
    ]);
    await page.waitForTimeout(350);
    assert.deepEqual(
      await page.evaluate(() => [neonDojo.game.elapsed, neonDojo.game.energy]),
      before,
    );
    await page.getByRole("button", { name: /▶ Продолжить бой/ }).click();
    assert.deepEqual(
      await page.evaluate(() =>
        neonDojo.game.units.units.filter((u) => u.active).map((u) => u.seed),
      ),
      army,
    );
    checks.push("menu pauses solo and resume preserves army and resources");
    await page.evaluate(() => {
      const g = neonDojo.game;
      g.energy = 0;
      g.ui.refresh();
    });
    assert(
      await page
        .locator(".card")
        .first()
        .evaluate((el) => el.classList.contains("unaffordable")),
    );
    assert(
      await page
        .locator("[role=progressbar]")
        .first()
        .getAttribute("aria-valuemax"),
    );
    await page.locator("#modeMenuBtn").click();
    await page.keyboard.press("Escape");
    assert(await page.locator("#modeMenu").isHidden());
    checks.push("energy feedback, accessible HP, Escape resumes solo");
    await page.evaluate(() => {
      neonDojo.modes.startStage(1);
      neonDojo.game.ourHp = 0;
      neonDojo.game.update(0.05);
    });
    await page
      .getByRole("button", { name: "Повторить этап", exact: true })
      .click();
    assert.equal(await page.evaluate(() => neonDojo.modes.stage), 1);
    assert(
      await page.evaluate(
        () =>
          neonDojo.game.state === "playing" &&
          neonDojo.game.ourHp === neonDojo.game.ourMax,
      ),
    );
    checks.push(
      "defeat retries the same stage immediately with restored castles",
    );
    // Locked stages cannot be entered via the public diagnostic interface either.
    await page.evaluate(() => {
      neonDojo.modes.stage = 0;
      neonDojo.modes.unlocked = 1;
      neonDojo.modes.startStage(30);
    });
    assert.equal(await page.evaluate(() => neonDojo.modes.stage), 0);
    // Synthetic authoritative packets isolate rendering from network timing.
    await page.evaluate(() => {
      const m = neonDojo.modes,
        g = neonDojo.game;
      g.hidden = true;
      g.mode = "pvp";
      m.side = 0;
      m.stopped = false;
      const p = {
        level: 1,
        tower: 0,
        energy: 87,
        hp: 1000,
        maxHp: 1000,
        superCd: 0,
        wave: 0,
        waveCount: 0,
        charges: Array(8).fill(0),
      };
      const s = {
        players: [p, p],
        names: ["A", "B"],
        status: "playing",
        units: [
          {
            slot: 0,
            seed: 777,
            side: 0,
            kind: 0,
            x: 100,
            hp: 85,
            maxHp: 85,
            age: 1,
            moving: true,
            flash: 0,
          },
        ],
        shots: [],
        elapsed: 1,
      };
      m.apply(s);
      const first = g.units.units[0].x;
      s.units[0].x = 200;
      m.apply(s);
      const same = g.units.units[0].x;
      const energy = g.energy;
      g.update(0.05);
      window.smoothing = {
        first,
        same,
        visual: g.units.units[0].x,
        target: (200 / 960) * g.w,
        energyBefore: energy,
        energyAfter: g.energy,
      };
      s.units[0].seed = 778;
      s.units[0].x = 69;
      m.apply(s);
      window.reused = g.units.units[0].x === (69 / 960) * g.w;
      m.prompt = true;
      m.apply({ ...s, status: "ended", winner: 0, reason: "leave" });
    });
    const smooth = await page.evaluate(() => window.smoothing);
    assert.equal(smooth.first, smooth.same);
    assert(smooth.visual > smooth.first && smooth.visual < smooth.target);
    assert.equal(smooth.energyBefore, smooth.energyAfter);
    assert(await page.evaluate(() => window.reused));
    checks.push(
      "PvP interpolates visuals only; recycled slots never inherit old position",
    );
    await page
      .getByRole("heading", { name: "勝 · Победа!", exact: true })
      .waitFor();
    checks.push("PvP result replaces an open surrender confirmation");
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ passed: checks.length, checks }, null, 2));
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
