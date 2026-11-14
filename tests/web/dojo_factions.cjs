/* Clan choice, reference sprites, persistence and independent team/facing. */
const assert = require("node:assert/strict"),
  path = require("node:path");
const { pathToFileURL } = require("node:url"),
  { chromium } = require("playwright-core");
(async () => {
  const m = require("@sparticuz/chromium"),
    c = m.default || m;
  const browser = await chromium.launch({
    executablePath:
      process.env.CHROMIUM_EXECUTABLE || (await c.executablePath()),
    args: c.args,
    headless: true,
  });
  try {
    const page = await browser.newPage({
        viewport: { width: 844, height: 390 },
      }),
      errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto(
      pathToFileURL(path.resolve(__dirname, "../../index.html")).href,
    );
    await page
      .getByRole("button", { name: "☯ Клан: Рассвет", exact: true })
      .click();
    assert(await page.locator(".team-preview").isVisible());
    await page
      .getByRole("button", { name: "☾ Играть за Тень", exact: true })
      .click();
    await page
      .getByRole("button", { name: "∞ Свободная битва", exact: true })
      .click();
    assert.equal(await page.evaluate(() => neonDojo.game.faction), 1);
    assert.deepEqual(await page.locator(".card .name").allTextContents(), [
      "Тень",
      "Колдун",
      "Арбалетчик",
      "Демон",
      "Колдун · шаман",
      "Тень · убийца",
      "Берсерк",
      "Гаргулья",
    ]);
    assert.match(
      await page.locator(".faction small").first().innerText(),
      /ТЕНИ/,
    );
    assert(
      await page.evaluate(() => {
        const g = neonDojo.game;
        g.summon(0);
        g.units.spawn(1, neonDojo.CONFIG.enemies[0]);
        return g.units.units
          .filter((u) => u.active)
          .every((u) => u.team === (u.side ? 0 : 1));
      }),
    );
    // A preference change must not recolor/change an existing army on resume.
    await page.locator("#modeMenuBtn").click();
    await page
      .getByRole("button", { name: "☯ Клан: Тень", exact: true })
      .click();
    await page
      .getByRole("button", { name: "☀ Играть за Рассвет", exact: true })
      .click();
    await page
      .getByRole("button", { name: "▶ Продолжить бой", exact: true })
      .click();
    assert.equal(await page.evaluate(() => neonDojo.game.faction), 1);
    await page.locator("#modeMenuBtn").click();
    await page
      .getByRole("button", { name: "∞ Свободная битва", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Начать новый бой", exact: true })
      .click();
    assert.equal(await page.evaluate(() => neonDojo.game.faction), 0);
    await page.evaluate(() => neonDojo.modes.setTeam(1));
    await page.reload();
    assert.equal(await page.evaluate(() => neonDojo.modes.preferredFaction), 1);
    // Team chooser itself must fit compact phone windows, not just the battlefield.
    for (const [width, height] of [
      [280, 480],
      [568, 320],
      [390, 844],
    ]) {
      await page.setViewportSize({ width, height });
      await page.waitForTimeout(70);
      await page.evaluate(() => neonDojo.modes.chooseTeam(() => {}));
      assert(
        await page.evaluate(() => {
          const b = document.querySelector(".modeBox"),
            r = b.getBoundingClientRect();
          return (
            b.scrollHeight <= b.clientHeight + 1 &&
            r.top >= 0 &&
            r.bottom <= innerHeight + 1
          );
        }),
      );
    }
    // All shadow roles have separate attack/run/idle frames in the existing atlas.
    assert(
      await page.evaluate(() => {
        const r = neonDojo.game.renderer,
          a = r.atlas,
          c = a.getContext("2d"),
          tile = 112 * r.atlasDpr;
        const hash = (kind, frame) => {
          const data = c.getImageData(
            frame * tile,
            (8 + kind) * tile,
            tile,
            tile,
          ).data;
          let h = 0;
          for (let i = 0; i < data.length; i++) h = (h * 31 + data[i]) | 0;
          return h;
        };
        return Array.from(
          { length: 8 },
          (_, k) => new Set([hash(k, 0), hash(k, 5), hash(k, 11)]).size === 3,
        ).every(Boolean);
      }),
    );
    assert.deepEqual(errors, []);
    console.log(
      "PASS: faction picker, 8 shadow cards / 6 archetypes, swapped armies, resume isolation, next-battle choice, persistence, 3 chooser viewports, animated atlas",
    );
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
