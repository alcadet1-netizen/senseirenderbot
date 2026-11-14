/* Full-window landscape, visible garrison and siege deployment. See neon_dojo.cjs for setup. */
const assert = require("node:assert/strict"),
  path = require("node:path");
const { pathToFileURL } = require("node:url");
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
  const browser = await chromium.launch({
    executablePath,
    args,
    headless: true,
  });
  try {
    const page = await browser.newPage(),
      errors = [],
      checks = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto(
      pathToFileURL(path.resolve(__dirname, "../../index.html")).href,
    );
    // Startup menu now precedes the existing battlefield.
    await page.getByRole("button", {name:"∞ Свободная битва", exact:true}).click();
    for (const [width, height] of [
      [568, 320],
      [667, 375],
      [812, 375],
      [844, 390],
      [932, 430],
      [1024, 600],
      [1024, 768],
      [1440, 900],
    ]) {
      await page.setViewportSize({ width, height });
      await page.waitForTimeout(80);
      const audit = await page.evaluate(() => {
        const selectors = [
          "#stage",
          "#superBtn",
          "#upgradeBtn",
          "#towerBtn",
          "#boostBtn",
          "#fullscreenBtn",
          "#battleHelpBtn",
          "#battleResetBtn",
          ...Array.from({ length: 8 }, (_, i) => `.card:nth-child(${i + 1})`),
        ];
        return {
          scroll: [
            document.documentElement.scrollWidth,
            document.documentElement.scrollHeight,
          ],
          bad: selectors.filter((s) => {
            const r = document.querySelector(s).getBoundingClientRect();
            return (
              r.width < 1 ||
              r.height < 1 ||
              r.left < 0 ||
              r.top < 0 ||
              r.right > innerWidth + 1 ||
              r.bottom > innerHeight + 1
            );
          }),
          cardsOverflow:
            document.querySelector("#cards").scrollWidth >
            document.querySelector("#cards").clientWidth + 1,
        };
      });
      assert.deepEqual(audit.bad, [], JSON.stringify({ width, height, audit }));
      assert(audit.scroll[0] <= width && audit.scroll[1] <= height);
      assert(!audit.cardsOverflow);
      checks.push(
        `all 8 cards and combat controls fit ${width}x${height} without scrolling`,
      );
    }
    await page.setViewportSize({ width: 375, height: 812 });
    assert(await page.locator(".rotate-tip").isVisible());
    checks.push("portrait recommends rotation without blocking play");
    await page.evaluate(() => {
      window.fullscreenRequests = 0;
      document.documentElement.requestFullscreen = () => {
        fullscreenRequests++;
        return Promise.resolve();
      };
    });
    await page.locator("#rotateFullscreenBtn").click();
    assert.equal(await page.evaluate(() => fullscreenRequests), 1);
    checks.push("browser fullscreen is requested on an explicit user gesture");
    checks.push(
      ...(await page.evaluate(() => {
        const { game: g, CONFIG: C } = neonDojo,
          checks = [],
          ok = (v, label) => {
            if (!v) throw Error(label);
            checks.push(label);
          };
        g.hidden = true;
        g.level = 6;
        g.tower = 0;
        g.newBattle();
        for (let i = 0; i < 4; i++)
          ok(
            g.units.spawn(0, C.cards[0]),
            "deployment slot " + i + " accepts a unit",
          );
        g.units.spawn(1, C.enemies[0]);
        let enemy = g.units.units.find((u) => u.active && u.side === 1);
        enemy.x = 85;
        g.energy = 100;
        g.charges[0] = C.cards[0].cd;
        g.summon(0);
        ok(
          g.units.count[0] === 5 && g.energy === 94 && g.charges[0] === 0,
          "pinning the gate no longer rejects or refunds a valid summon",
        );
        const recruit = g.units.units.find((u) => u.seed === g.units.seed),
          hp = recruit.hp;
        g.units.hit(recruit, 20);
        ok(
          recruit.hp === hp - 10,
          "formation protection halves damage for a new recruit",
        );
        recruit.age = 1;
        g.units.hit(recruit, 20);
        ok(recruit.hp === hp - 30, "formation protection expires");
        for (let i = g.units.count[0]; i < 48; i++)
          g.units.spawn(0, C.cards[0]);
        g.energy = 100;
        g.charges[0] = C.cards[0].cd;
        g.summon(0);
        ok(
          g.units.count[0] === 48 &&
            g.energy === 100 &&
            g.charges[0] === C.cards[0].cd,
          "real army cap rejects without spending energy/cooldown",
        );
        g.newBattle();
        for (let i = 0; i < 5; i++) g.units.spawn(1, C.enemies[0]);
        ok(g.units.count[1] === 5, "enemy has the same rear-deployment rule");
        g.newBattle();
        for (let i = 0; i < 10; i++) g.units.spawn(0, C.cards[0]);
        for (const u of g.units.units)
          if (u.active) {
            u.x = 15;
            u.age = 1;
            u.cool = 0;
          }
        g.units.spawn(1, C.enemies[0]);
        enemy = g.units.units.find((u) => u.active && u.side === 1);
        enemy.x = 35;
        enemy.hp = 1000;
        enemy.age = 1;
        g.units.update(0.01);
        ok(
          enemy.hp === 985,
          "overlapping rear melee units cannot deal ten instant front-line attacks",
        );
        g.newBattle();
        g.units.spawn(0, C.cards[2]);
        let attacker = g.units.units.find((u) => u.active);
        attacker.x = g.w - 190;
        attacker.age = 1;
        attacker.cool = 0;
        g.units.spawn(1, C.enemies[2]);
        enemy = g.units.units.find((u) => u.active && u.side === 1);
        enemy.x = g.w - 60;
        enemy.age = 1;
        const castle = g.enemyHp;
        g.units.update(0.01);
        ok(
          g.enemyHp < castle,
          "troops behind the gate do not make the castle immune to siege damage",
        );
        g.level = 6;
        g.tower = 0;
        g.newBattle();
        g.elapsed = 240;
        ok(
          g.combatMultiplier() === 1,
          "no damage escalation before four minutes",
        );
        g.elapsed = 360;
        ok(
          g.combatMultiplier() === 1.5,
          "both teams enter a gradual late-battle escalation",
        );
        g.elapsed = 900;
        ok(
          g.combatMultiplier() === 2,
          "escalation is capped, never an automatic win",
        );
        g.newBattle();
        g.units.spawn(0, C.cards[0]);
        g.units.spawn(1, C.enemies[0]);
        const left = g.units.units.find((u) => u.active && u.side === 0),
          right = g.units.units.find((u) => u.active && u.side === 1);
        left.x = 200;
        right.x = 220;
        left.age = right.age = 1;
        left.cool = 0;
        right.cool = 1;
        right.hp = 1000;
        g.elapsed = 480;
        g.units.update(0.01);
        ok(right.hp === 970, "late-battle damage boost applies to the player");
        left.cool = 100;
        right.cool = 0;
        const playerHP = left.hp;
        g.units.update(0.01);
        ok(
          left.hp === playerHP - 24,
          "the same damage boost applies to the enemy",
        );
        g.newBattle();
        g.energy = 1000;
        g.ui.refresh();
        return checks;
      })),
    );
    await page.setViewportSize({ width: 812, height: 375 });
    await page.waitForTimeout(80);
    await page.locator("#towerBtn").click();
    assert(
      (await page.locator("#modalTitle").textContent()).includes("защита"),
    );
    for (let i = 1; i <= 3; i++) {
      await page.locator("#modalAction").click();
      assert.equal(await page.evaluate(() => neonDojo.game.tower), i);
    }
    assert.equal(await page.evaluate(() => neonDojo.game.energy), 225);
    checks.push(
      "persistent defense button opens and buys all 3 garrison upgrades with exact costs",
    );
    await page.locator("#modalAction").click();
    assert.equal(await page.evaluate(() => neonDojo.game.ui.modal.open), false);
    await page.evaluate(() => {
      neonDojo.game.level = 1;
      neonDojo.game.tower = 0;
      neonDojo.game.energy = 100;
    });
    await page.locator("#towerBtn").click();
    assert(
      (await page.locator("#modalAction").textContent()).includes("додзё 2"),
    );
    await page.locator("#modalAction").click();
    checks.push(
      "locked garrison requirement is shown in the dialog, not an invisible toast behind it",
    );
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ passed: checks.length, checks }, null, 2));
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
