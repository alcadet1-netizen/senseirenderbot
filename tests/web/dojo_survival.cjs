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
    if (process.env.DOJO_CANVAS)
      await page.route("**/renderer.js", (route) => route.abort());
    await page.goto(
      process.env.DOJO_URL || "http://127.0.0.1:8080/miniapp/dojo",
    );
    if (!process.env.DOJO_CANVAS)
      await page.waitForFunction(() => !!window.dojoRenderer);
    await page.click("#play");
    assert.equal(await page.evaluate(() => game.state), "game");
    await page.keyboard.down("ArrowRight");
    await page.waitForFunction(() => game.player.x > 300);
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
        game.player.damage !== CONFIG.damage + 2 ||
        !game.player.shuriken ||
        game.slow <= 0
      )
        throw Error("pickup effects");
    });
    for (let wave = 0; wave < 5; wave++) {
      await page.evaluate(() => {
        const w = game.waves;
        w.spawned = w.spec.count;
        w.crateSpawned = true;
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
        await page.click('[data-buy="warrior"]');
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
    // Новые механики проверяются без подмены формулы урона.
    await page.evaluate(() => {
      game.start();
      game.state = "game";
      const p = game.player;
      p.x = p.target = 270;
      if (document.querySelector("#dash") || typeof p.dash !== "undefined")
        throw Error("dash remains");
      game.enemies = [];
      p.update(0.01, game);
      if (!game.shots.length) throw Error("no fire at wave start");
      const emptyShot = game.shots[0],
        startY = emptyShot.y;
      emptyShot.update(0.1, game);
      if (emptyShot.dead || emptyShot.y >= startY)
        throw Error("idle shot does not fly");
      game.shots = [];
      p.cooldown = 0;
      const far = new Enemy(CONFIG.waves[0]);
      far.y = -15;
      game.enemies = [far];
      p.update(0.01, game);
      if (!game.shots.some((s) => s.target === far))
        throw Error("far enemy not targeted");
      game.start();
      const e = new Enemy(CONFIG.waves[0]);
      e.x = 270;
      e.y = 600;
      game.enemies = [e];
      const hp = e.hp;
      game.player.update(0.01, game);
      if (e.hp !== hp || !game.shots.length)
        throw Error("instant damage instead of projectile");
      for (let i = 0; i < 80; i++)
        for (const shot of game.shots) if (!shot.dead) shot.update(0.01, game);
      if (!e.dead) throw Error("projectiles do not land");
      for (let i = 0; i < 5; i++) {
        const foe = new Enemy(CONFIG.waves[0]);
        foe.hit(999, game);
      }
      if (game.combo < 5 || !game.coins) throw Error("combo rewards");
      game.comboTime = 0.01;
      game.update(0.02);
      if (game.combo !== 0) throw Error("combo never expires");
      game.start();
      const b = new Boss(CONFIG.waves[2]);
      b.y = 500;
      game.enemies = [b];
      game.waves.timer = 999;
      for (let i = 0; i < 6000 && !b.dead && game.state === "game"; i++) {
        game.player.target =
          b.warning > 0 ? (b.attackX < 270 ? 430 : 110) : b.x;
        game.update(0.02);
      }
      if (!b.dead)
        throw Error(
          "boss cannot be defeated with default army/range, hp=" + b.hp,
        );
      game.state = "pause";
    });
    await page.evaluate(() => {
      if (project(400, 100).scale >= project(400, 750).scale)
        throw Error("missing depth scale");
      if (
        Math.abs(project(400, 100).x - 270) >=
        Math.abs(project(400, 750).x - 270)
      )
        throw Error("missing vanishing point");
      game.start();
      const caster = new Enemy(CONFIG.waves[1], "shaman");
      caster.y = 350;
      caster.castTimer = 0;
      caster.update(0.01, game);
      if (caster.castWarning <= 0) throw Error("shaman telegraph");
      caster.castWarning = 0.001;
      caster.update(0.01, game);
      if (game.hazards.length !== 1) throw Error("shaman projectile");
      const l = new Boss(CONFIG.waves[4]);
      l.y = 400;
      l.warning = 0.001;
      l.attackX = 270;
      l.summonTimer = 0;
      l.update(0.01, game);
      if (
        l.kind !== "lich" ||
        game.hazards.length !== 4 ||
        game.enemies.filter((e) => e.type === "skeleton").length !== 2
      )
        throw Error("distinct lich attacks");
      const count = game.player.army;
      const bolt = new EnemyBolt(
        game.player.x,
        game.player.y - 1,
        game.player.x,
      );
      bolt.update(3, game);
      if (game.player.army !== count - 1) throw Error("enemy spell damage");
      game.start();
      game.ui.hide();
    });
    const rect = await page.locator("#game").boundingBox();
    const projected = await page.evaluate(() => project(400, CONFIG.playerY));
    await page.mouse.click(
      rect.x + (projected.x / 540) * rect.width,
      rect.y + (projected.y / 960) * rect.height,
    );
    assert.ok(
      Math.abs((await page.evaluate(() => game.player.target)) - 400) < 2,
      "inverse perspective pointer",
    );
    await page.evaluate(() => {
      game.start();
      const before = game.player.army;
      const gate = new RecruitGate(game.player.x, CONFIG.playerY, 1);
      gate.update(0.01, game);
      if (!gate.dead || game.player.army !== before + 1)
        throw Error("gate recruitment");
      gate.update(0.01, game);
      if (game.player.army !== before + 1) throw Error("gate collected twice");
      game.player.army = CONFIG.maxArmy;
      const capped = new RecruitGate(game.player.x, CONFIG.playerY, 3);
      capped.update(0.01, game);
      if (game.player.army !== CONFIG.maxArmy) throw Error("gate cap");
      const missed = new RecruitGate(110, CONFIG.playerY, 1);
      game.player.x = 430;
      missed.update(2, game);
      if (!missed.dead) throw Error("missed gate lifetime");
      const crate = new SupplyCrate(CONFIG.waves[0]),
        coins = game.coins,
        damage = game.player.damage;
      crate.hit(CONFIG.crateHp - 1, game);
      if (crate.dead || crate.hp !== 1) throw Error("crate HP");
      crate.hit(1, game);
      crate.hit(999, game);
      if (
        !crate.dead ||
        game.coins !== coins + 25 ||
        game.player.damage !== damage + 1
      )
        throw Error("crate reward once");
      game.start();
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
      game.enemies = [];
      const types = ["normal", "skeleton", "armored", "fast", "shaman"];
      for (let i = 0; i < 32; i++) {
        const foe = new Enemy(CONFIG.waves[2], types[i % 5]);
        foe.x = 120 + (i % 6) * 60;
        foe.y = 40 + Math.floor(i / 6) * 85;
        game.enemies.push(foe);
      }
      const boss = new Boss(CONFIG.waves[4]);
      boss.x = 270;
      boss.y = 270;
      game.enemies.push(boss);
      const crate = new SupplyCrate(CONFIG.waves[4]);
      crate.x = 420;
      crate.y = 540;
      game.enemies.push(crate);
      game.gates = [];
      for (let i = 0; i < 7; i++)
        game.gates.push(new RecruitGate(110, 80 + i * 93, 1));
      game.waves.index = 4;
      game.ui.toastTime = 0;
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
