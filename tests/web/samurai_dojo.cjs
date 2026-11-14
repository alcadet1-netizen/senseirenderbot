/* Новые механики и реальные спрайты. Запуск/зависимости: neon_dojo.cjs. */
"use strict";
const assert = require("node:assert/strict");
const path = require("node:path");
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
    const page = await browser.newPage({
        viewport: { width: 1280, height: 900 },
        deviceScaleFactor: 2,
      }),
      errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto(
      pathToFileURL(path.resolve(__dirname, "../../index.html")).href,
    );
    const checks = await page.evaluate(() => {
      const { game: g, CONFIG: C } = neonDojo,
        checks = [];
      const ok = (value, label) => {
        if (!value) throw Error(label);
        checks.push(label);
      };
      g.hidden = true;
      ok(
        !/ёж|тюлен|игол/i.test(document.body.innerText),
        "нет старой звериной тематики в интерфейсе",
      );
      ok(
        C.cards.length === 8 &&
          g.charges.length === 8 &&
          g.reserve.length === 8,
        "восьмая карточка без потери старых семи",
      );
      // Старый формат сохраняется: не сбрасываем накопленный прогресс при рескине.
      const key = g.save.key;
      localStorage.setItem(
        key,
        JSON.stringify({
          version: 1,
          level: 4,
          coins: 321,
          wins: 5,
          skin: 2,
          reserve: [false, true],
        }),
      );
      let legacy = g.save.load();
      ok(
        legacy.level === 4 &&
          legacy.coins === 321 &&
          legacy.wins === 5 &&
          legacy.tower === 0,
        "миграция старого прогресса без сброса",
      );
      g.level = 1;
      g.tower = 0;
      g.newBattle();
      g.energy = 1000;
      ok(
        !g.upgradeTower() && g.tower === 0 && g.energy === 1000,
        "гарнизон требует уровень додзё",
      );
      g.level = 2;
      g.energy = 74;
      ok(
        !g.upgradeTower() && g.energy === 74,
        "недостаточно энергии на гарнизон",
      );
      g.energy = 100;
      ok(
        g.upgradeTower() && g.tower === 1 && g.energy === 25,
        "первая площадка стоит 75 энергии",
      );
      g.level = 6;
      g.energy = 1000;
      g.upgradeTower();
      g.upgradeTower();
      ok(
        g.tower === 3 && g.energy === 300 && !g.upgradeTower(),
        "все три улучшения с точным списанием и ограничением",
      );
      g.persist();
      ok(g.save.load().tower === 3, "гарнизон сохраняется");
      g.newBattle();
      ok(g.tower === 3, "гарнизон остаётся в следующем бою");
      g.tower = 0;
      g.level = 3;
      g.newBattle();
      g.energy = 100;
      g.charges[7] = C.cards[7].cd;
      g.summon(7);
      let flyer = g.units.units.find((u) => u.active);
      ok(
        flyer.flying && flyer.y < g.ground - 30 && g.energy === 70,
        "Куноичи призывается за 30 энергии и действительно летает",
      );
      ok(g.units.spawn(0, C.cards[0]), "наземный и воздушный входы независимы");
      g.newBattle();
      g.units.spawn(0, C.cards[7]);
      flyer = g.units.units.find((u) => u.active);
      flyer.x = 450;
      flyer.age = 1;
      g.units.spawn(1, C.enemies[0]);
      let enemy = g.units.units.find((u) => u.active && u.side === 1);
      enemy.x = 470;
      enemy.age = 1;
      const hp = flyer.hp;
      for (let i = 0; i < 120; i++) g.units.update(1 / 60);
      ok(flyer.hp === hp, "мечник не поражает воздушную цель");
      ok(enemy.hp < enemy.maxHp, "Куноичи атакует наземную цель сюрикенами");
      g.newBattle();
      g.units.spawn(0, C.cards[7]);
      flyer = g.units.units.find((u) => u.active);
      flyer.x = 450;
      flyer.age = 1;
      g.units.spawn(1, C.enemies[2]);
      enemy = g.units.units.find((u) => u.active && u.side === 1);
      enemy.x = 510;
      enemy.age = 1;
      enemy.cool = 0;
      for (let i = 0; i < 120; i++) g.units.update(1 / 60);
      ok(flyer.hp < flyer.maxHp, "лучник контрит воздух настоящим снарядом");
      g.newBattle();
      g.tower = 1;
      g.units.spawn(1, C.enemies[4]);
      enemy = g.units.units.find((u) => u.active);
      enemy.x = 135;
      enemy.age = 1;
      g.units.updateTowers(2);
      let shots = g.units.shots.filter((p) => p.active);
      ok(
        shots.length === 1 && shots[0].target === enemy,
        "гарнизон выбирает воздушную цель",
      );
      g.units.updateTowers(0.1);
      ok(
        g.units.shots.filter((p) => p.active).length === 1,
        "гарнизон соблюдает кулдаун",
      );
      let old = enemy.hp;
      for (let i = 0; i < 60; i++) g.units.update(1 / 60);
      ok(enemy.hp < old, "стрела гарнизона попадает по цели");
      g.newBattle();
      g.tower = 0;
      g.units.spawn(1, C.enemies[0]);
      enemy = g.units.units.find((u) => u.active);
      enemy.x = 90;
      g.units.updateTowers(10);
      ok(
        !g.units.shots.some((p) => p.active),
        "без улучшения башня не стреляет",
      );
      g.tower = 3;
      enemy.x = g.w - 100;
      g.units.updateTowers(10);
      ok(
        !g.units.shots.some((p) => p.active),
        "гарнизон не простреливает всю арену",
      );
      const atlas = g.renderer.atlas,
        dpr = g.renderer.atlasDpr,
        size = 112 * dpr,
        ctx = atlas.getContext("2d");
      function hash(frame, row) {
        const a = ctx.getImageData(frame * size, row * size, size, size).data;
        let n = 0;
        for (let i = 0; i < a.length; i++) n = (Math.imul(n, 31) + a[i]) | 0;
        return n;
      }
      ok(
        hash(0, 0) !== hash(5, 0) && hash(0, 0) !== hash(11, 0),
        "отдельные реальные позы ожидания, бега и атаки",
      );
      ok(
        new Set(Array.from({ length: 16 }, (_, row) => hash(0, row))).size ===
          16,
        "все восемь ролей и обе команды имеют разные спрайты",
      );
      const pixels = ctx.getImageData(0, 0, atlas.width, atlas.height).data;
      const alpha = (x, y) =>
        pixels[(Math.round(y) * atlas.width + Math.round(x)) * 4 + 3];
      let bleed = false;
      for (let row = 0; row < 16; row++)
        for (let frame = 0; frame < 14; frame++) {
          const x = frame * size,
            y = row * size;
          for (let i = 0; i < size; i++)
            if (
              alpha(x + i, y) > 0 ||
              alpha(x + i, y + size - 1) > 0 ||
              alpha(x, y + i) > 0 ||
              alpha(x + size - 1, y + i) > 0
            )
              bleed = true;
        }
      ok(
        !bleed,
        "все 224 спрайта помещаются в свои ячейки без обрезки и затекания",
      );
      const face = ctx.getImageData(55 * dpr, 43 * dpr, 1, 1).data;
      ok(
        face[0] < 80 && face[1] < 80 && face[2] < 80 && face[3] > 240,
        "у модели чёрная маска-голова по референсу",
      );
      g.newBattle();
      g.units.spawn(0, C.cards[7]);
      g.units.spawn(1, C.enemies[0]);
      const thrower = g.units.units.find((u) => u.active && u.side === 0),
        victim = g.units.units.find((u) => u.active && u.side === 1);
      g.units.fire(thrower, victim, 1);
      ok(
        g.units.shots.find((p) => p.active).style === 1,
        "куноичи выпускает отдельный спрайт сюрикена",
      );
      g.level = 6;
      g.tower = 0;
      g.energy = 1000;
      g.ui.refresh();
      ok(
        !document.querySelector("#upgradeBtn").disabled,
        "гарнизон доступен и на максимальном додзё",
      );
      return checks;
    });
    // Настоящий клик по дополнительному улучшению внутри старого диалога.
    await page.locator("#upgradeBtn").click();
    await page.locator("#towerAction").click();
    assert.equal(await page.evaluate(() => neonDojo.game.tower), 1);
    checks.push("гарнизон покупается кнопкой в существующем меню додзё");
    await page.locator("#closeModal").click();
    for (const [width, height] of [
      [280, 740],
      [375, 812],
      [768, 900],
      [1024, 820],
      [812, 375],
    ]) {
      await page.setViewportSize({ width, height });
      await page.waitForTimeout(60);
      assert(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      );
      // Восьмая карточка достижима в том же скроллере и не уехала за экран.
      await page.locator(".card").nth(7).scrollIntoViewIfNeeded();
      const card = await page.locator(".card").nth(7).boundingBox();
      assert(card.x >= 0 && card.x + card.width <= width + 1);
      checks.push(`адаптивность и доступность Куноичи ${width}x${height}`);
    }
    await page.setViewportSize({ width: 375, height: 812 });
    await page.waitForTimeout(60);
    await page.evaluate(() => {
      document.querySelector("#cards").scrollLeft = 0;
      neonDojo.game.reserve.fill(false);
    });
    const drag = await page.locator(".card").nth(4).boundingBox();
    await page.mouse.move(drag.x + drag.width / 2, drag.y + 40);
    await page.mouse.down();
    await page.mouse.move(35, drag.y + 40, { steps: 12 });
    await page.mouse.up();
    assert(
      await page.evaluate(
        () => document.querySelector("#cards").scrollWidth <= document.querySelector("#cards").clientWidth + 1,
      ),
    );
    assert(await page.evaluate(() => neonDojo.game.reserve.every((v) => !v)));
    checks.push("вся колода видима без прокрутки; длинный свайп не убирает бойца в резерв");
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ passed: checks.length, checks }, null, 2));
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
