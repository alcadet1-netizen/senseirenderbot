// Настоящий Chromium: сцены, управление, бонусы, волны, магазин и финалы.
const { chromium } = require("playwright-core");
const assert = require("node:assert/strict");
(async () => {
  const mod = require("@sparticuz/chromium"),
    binary = mod.default || mod;
  const browser = await chromium.launch({
    executablePath: await binary.executablePath(),
    args: binary.args,
    headless: true,
  });
  try {
    const page = await browser.newPage({
      viewport: { width: 390, height: 844 },
    });
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto(
      process.env.DOJO_URL || "http://127.0.0.1:8080/miniapp/dojo",
    );
    await page.click("#play");
    assert.equal(await page.evaluate(() => game.state), "game");
    await page.keyboard.down("ArrowRight");
    await page.waitForTimeout(300);
    await page.keyboard.up("ArrowRight");
    assert.ok(await page.evaluate(() => game.player.x > 300));
    await page.click("#pause");
    assert.equal(await page.evaluate(() => game.state), "pause");
    const frozen = await page.evaluate(() => game.time);
    await page.waitForTimeout(200);
    assert.equal(await page.evaluate(() => game.time), frozen);
    await page.click("#resume");
    await page.evaluate(() => {
      for (const type of Object.keys(PICKUPS)) {
        const p = new Pickup(game.player.x, game.player.y, type);
        p.update(0.001, game);
        if (!p.dead) throw Error("pickup " + type);
      }
      if (
        game.player.army !== 7 ||
        game.player.damage !== 11 ||
        !game.player.shuriken ||
        game.slow <= 0
      )
        throw Error("pickup effects");
    });
    for (let wave = 0; wave < 5; wave++) {
      await page.evaluate(() => {
        const w = game.waves;
        w.spawned = w.spec.count;
        if (w.spec.boss) {
          w.bossSpawned = true;
          const b = new Boss(w.spec);
          b.hit(999999, game);
        }
        game.enemies = [];
        w.update(0.01);
      });
      if (wave < 4) {
        assert.equal(await page.evaluate(() => game.state), "shop");
        await page.evaluate(() => {
          game.coins = 500;
          game.shopWait = 0;
          game.showShop();
        });
        await page.click('[data-buy="hedgehog"]');
        await page.click('[data-buy="damage"]');
        await page.click('[data-buy="speed"]');
        assert.equal(await page.evaluate(() => game.coins), 300);
        await page.click("#next");
      } else assert.equal(await page.evaluate(() => game.state), "victory");
    }
    await page.click("#again");
    await page.evaluate(() => {
      game.player.lives = 0;
      game.update(0.01);
    });
    assert.equal(await page.evaluate(() => game.state), "defeat");
    await page.click("#again");
    await page.evaluate(() => {
      game.player.army = 0;
      game.update(0.01);
    });
    assert.equal(await page.evaluate(() => game.state), "defeat");
    await page.click("#again");
    await page.evaluate(() => {
      game.enemies = [new Boss(CONFIG.waves[2])];
      game.enemies[0].y = 500;
      game.enemies[0].charge = 0;
      game.update(0.01);
      game.player.x = game.enemies[0].attackX;
      game.player.target = game.player.x;
      game.enemies[0].warning = 0.001;
      game.update(0.01);
      if (game.player.army !== 4) throw Error("boss aoe");
    });
    for (const size of [
      { width: 320, height: 568 },
      { width: 390, height: 844 },
      { width: 900, height: 600 },
    ]) {
      await page.setViewportSize(size);
      const r = await page.locator("#frame").boundingBox();
      assert.ok(Math.abs(r.width / r.height - 9 / 16) < 0.01);
      assert.ok(r.height <= size.height + 1 && r.width <= size.width + 1);
    }
    await page.setViewportSize({ width: 390, height: 844 });
    await page.evaluate(() => {
      game.start();
      game.enemies = [new Enemy(CONFIG.waves[2]), new Boss(CONFIG.waves[2])];
      game.enemies[0].y = 390;
      game.enemies[1].y = 190;
      game.pickups = Object.keys(PICKUPS).map(
        (t, i) =>
          new Pickup(120 + (i % 3) * 145, 400 + Math.floor(i / 3) * 140, t),
      );
      game.state = "pause";
      game.ui.hide();
    });
    await page.screenshot({ path: ".cache/dojo-survival.png" });
    assert.deepEqual(errors, []);
    console.log(
      "Browser checks passed: five-wave flow, both losses, boss AoE, pickups, purchases, movement, pause, 3 aspect ratios.",
    );
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
