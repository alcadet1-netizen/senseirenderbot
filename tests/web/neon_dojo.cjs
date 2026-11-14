/* Регрессия автономного прототипа в настоящем Chromium.
 * Без изменений зависимостей бота:
 *   npm install --prefix /tmp/neon-qa playwright
 *   /tmp/neon-qa/node_modules/.bin/playwright install chromium
 *   NODE_PATH=/tmp/neon-qa/node_modules node tests/web/neon_dojo.cjs
 * Либо задайте CHROMIUM_EXECUTABLE для уже установленного браузера.
 * Прототип index.html этих пакетов не требует.
 */
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
  let executablePath = process.env.CHROMIUM_EXECUTABLE;
  let args = ["--no-sandbox", "--disable-dev-shm-usage"];
  // В некоторых CI Chromium поставляется как npm-пакет с готовым бинарником.
  if (!executablePath) {
    try {
      const mod = require("@sparticuz/chromium");
      const packaged = mod.default || mod;
      executablePath = await packaged.executablePath();
      args = packaged.args;
    } catch {
      /* Обычная установка Playwright использует собственный Chromium. */
    }
  }
  const browser = await chromium.launch({
    executablePath,
    args,
    headless: true,
  });
  const errors = [],
    requests = [];
  const file = pathToFileURL(path.resolve(__dirname, "../../index.html")).href;
  const checks = [];
  try {
    const page = await browser.newPage({
      viewport: { width: 1024, height: 820 },
      deviceScaleFactor: 2,
    });
    page.on("pageerror", (e) => errors.push(e.message));
    page.on("request", (request) => {
      if (/^https?:/.test(request.url())) requests.push(request.url());
    });
    await page.goto(file);
    checks.push(
      ...(await page.evaluate(() => {
        const { game: g, CONFIG: C, SaveSystem, ParticlePool } = neonDojo,
          passed = [];
        function ok(value, name) {
          if (!value) throw Error(name);
          passed.push(name);
        }
        g.level = 1;
        g.coins = 120;
        g.newBattle();
        g.energy = 87;
        g.summon(0);
        ok(
          g.energy === 81 && g.units.count[0] === 1,
          "призыв списывает энергию",
        );
        g.summon(0);
        ok(g.units.count[0] === 1, "карточка не призывается дважды");
        g.newBattle();
        g.reserve[0] = true;
        g.energy = 100;
        g.summon(0);
        ok(
          g.units.count[0] === 0 && g.energy === 100,
          "резерв нельзя обойти горячей клавишей",
        );
        g.reserve[0] = false;
        for (let level = 1; level < 6; level++) {
          g.energy = C.levels[level - 1].cap;
          ok(
            g.upgrade() && g.level === level + 1,
            "доступен апгрейд " + (level + 1),
          );
        }
        g.newBattle();
        const before = g.elapsed;
        g.advance(0.1);
        ok(
          Math.abs(g.elapsed - before - 0.1) < 1e-6,
          "10 FPS не замедляют симуляцию вдвое",
        );
        const beforeStall = g.elapsed;
        g.advance(10);
        ok(
          g.elapsed - beforeStall < 0.201,
          "ограничено наверстывание после зависания",
        );
        g.ui.help();
        const paused = g.elapsed,
          energy = g.energy,
          bg = g.bg.time;
        g.update(0.1);
        ok(
          g.elapsed === paused && g.energy === energy,
          "меню ставит бой и экономику на паузу",
        );
        ok(g.bg.time > bg, "фон живой на тактической паузе");
        g.ui.modal.close();
        g.advance(0.1);
        ok(g.elapsed > paused, "закрытие меню продолжает бой");
        g.quality = 2;
        g.adaptQuality(20);
        ok(
          g.quality === 0 && g.canvas.width === Math.round(g.w),
          "ECO уменьшает разрешение",
        );
        g.adaptQuality(60);
        g.adaptQuality(60);
        ok(g.quality === 0, "качество не дрожит на одном хорошем окне");
        g.adaptQuality(60);
        ok(g.quality === 1, "постепенное восстановление качества");
        g.adaptQuality(60);
        g.adaptQuality(60);
        g.adaptQuality(60);
        ok(g.quality === 2, "HIGH возвращается после устойчивого FPS");
        const atlas = g.renderer.atlas;
        g.renderer.buildAtlas();
        ok(atlas === g.renderer.atlas, "атлас переиспользуется");
        const pixel = atlas
          .getContext("2d")
          .getImageData(0, 0, atlas.width, atlas.height).data;
        let nonzero = 0;
        for (let i = 3; i < pixel.length; i += 4) if (pixel[i]) nonzero++;
        ok(nonzero > 1000, "векторный атлас действительно содержит бойцов");
        const pool = new ParticlePool(8),
          first = pool.items[0];
        pool.emit(0, 0, 100, "#ff006e");
        pool.update(2);
        ok(
          pool.items.length === 8 &&
            pool.items[0] === first &&
            pool.items.every((p) => !p.active),
          "пул не растёт, объекты переиспользуются",
        );
        g.newBattle();
        g.units.spawn(0, C.cards[2]);
        g.units.spawn(1, C.enemies[0]);
        const a = g.units.units.find((u) => u.active && u.side === 0),
          b = g.units.units.find((u) => u.active && u.side === 1);
        g.units.fire(a, b, 10);
        const shot = g.units.shots.find((p) => p.active),
          hp = b.hp;
        b.seed++;
        g.units.update(0.01);
        ok(
          !shot.active && b.hp === hp,
          "стрела не поражает переиспользованный слот",
        );
        g.newBattle();
        g.units.spawn(0, C.cards[0]);
        g.units.spawn(1, C.enemies[0]);
        const ally = g.units.units.find((u) => u.active && u.side === 0),
          enemy = g.units.units.find((u) => u.active && u.side === 1);
        ally.x = 200;
        enemy.x = 225;
        ally.cool = 0;
        const oldHp = enemy.hp;
        g.units.update(0.05);
        ok(enemy.hp < oldHp, "ближняя атака наносит урон");
        g.energy = 100;
        g.superCd = 0;
        g.superAttack();
        ok(
          g.energy === 80 && g.superCd > 0,
          "ци тратит энергию и запускает кулдаун",
        );
        g.superAttack();
        ok(g.energy === 80, "нет повторной ци без кулдауна");
        g.newBattle();
        g.ourHp = g.ourMax = 1e8;
        for (let i = 0; i < 10000; i++) g.update(0.05);
        ok(g.enemyLevel === 5, "ИИ строит все пять уровней");
        ok(
          g.units.units.length === 96 &&
            g.units.shots.length === 80 &&
            g.fx.items.length === 320,
          "пулы неизменны после долгого боя",
        );
        g.newBattle();
        g.enemyHp = 0;
        g.update(0.01);
        ok(g.state === "won", "победа");
        g.ui.modal.close();
        g.newBattle();
        g.ourHp = 0;
        g.update(0.01);
        ok(g.state === "lost", "поражение");
        g.ui.modal.close();
        g.level = 3;
        g.coins = 321;
        g.wins = 2;
        g.persist();
        g.newBattle();
        const rect = document.querySelector("#stage").getBoundingClientRect();
        Object.assign(g.gesture, {
          live: true,
          scouted: false,
          moved: false,
          time: performance.now() - 700,
          x: rect.left + g.w - 50,
          y: rect.top + g.ground - 20,
        });
        g.ui.update(0.001);
        ok(
          g.ui.modal.open && g.gesture.scouted,
          "разведка использует реальное время, а не число кадров",
        );
        g.gesture.live = false;
        g.ui.modal.close();
        const storage = new SaveSystem(),
          original = Storage.prototype.setItem;
        let writes = 0;
        Storage.prototype.setItem = function (...args) {
          writes++;
          return original.apply(this, args);
        };
        try {
          storage.save(g);
          storage.save(g);
          ok(
            writes === 1,
            "нет повторных синхронных записей одинакового прогресса",
          );
        } finally {
          Storage.prototype.setItem = original;
        }
        g.persist();
        return passed;
      })),
    );
    await page.reload();
    assert.equal(await page.evaluate(() => neonDojo.game.level), 3);
    assert.equal(await page.evaluate(() => neonDojo.game.coins), 321);
    checks.push("мета-прогресс переживает file:// перезагрузку");
    for (const [width, height] of [
      [280, 740],
      [375, 812],
      [768, 900],
      [1024, 820],
      [812, 375],
    ]) {
      await page.setViewportSize({ width, height });
      await page.waitForTimeout(80);
      assert(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      );
      checks.push(`без горизонтального переполнения ${width}×${height}`);
    }
    // Действия настоящего указателя, а не прямой вызов игровых методов.
    await page.setViewportSize({ width: 375, height: 812 });
    await page.evaluate(() => {
      let g = neonDojo.game;
      g.level = 1;
      g.reserve.fill(false);
      g.newBattle();
      g.energy = 100;
    });
    await page.locator("#upgradeBtn").click();
    await page.locator("#modalAction").click();
    assert.equal(await page.evaluate(() => neonDojo.game.level), 2);
    checks.push("кнопка и подтверждение апгрейда работают");
    await page.evaluate(() => {
      neonDojo.game.superCd = 0;
      neonDojo.game.energy = 90;
    });
    const rect = await page.locator("#arena").boundingBox();
    await page.mouse.move(rect.x + rect.width / 2, rect.y + rect.height * 0.7);
    await page.mouse.down();
    await page.mouse.move(rect.x + rect.width / 2, rect.y + rect.height * 0.3, {
      steps: 5,
    });
    await page.mouse.up();
    assert.equal(await page.evaluate(() => neonDojo.game.waveCount), 1);
    checks.push("свайп вверх вызывает ци");
    const card = await page.locator(".card").first().boundingBox();
    await page.mouse.move(card.x + card.width * 0.9, card.y + 40);
    await page.mouse.down();
    await page.mouse.move(card.x + 1, card.y + 40, { steps: 5 });
    await page.mouse.up();
    assert(await page.evaluate(() => neonDojo.game.reserve[0]));
    await page.locator(".card").first().click();
    assert.equal(await page.evaluate(() => neonDojo.game.reserve[0]), false);
    checks.push("свайп в резерв и возврат тапом");
    // Хранилище запрещено: игра всё равно запускается, без диалогов браузера.
    const blocked = await browser.newPage();
    blocked.on("pageerror", (e) => errors.push(e.message));
    await blocked.addInitScript(() =>
      Object.defineProperty(window, "localStorage", {
        get() {
          throw new DOMException("Denied", "SecurityError");
        },
      }),
    );
    await blocked.goto(file);
    assert(
      await blocked.evaluate(() => {
        neonDojo.game.persist();
        return !neonDojo.game.save.ok && neonDojo.game.state === "playing";
      }),
    );
    checks.push("запуск при запрещённом localStorage");
    const broken = await browser.newPage();
    broken.on("pageerror", (e) => errors.push(e.message));
    await broken.addInitScript(() =>
      localStorage.setItem("hedgehog-neon-v31", "{broken"),
    );
    await broken.goto(file);
    assert.equal(await broken.evaluate(() => neonDojo.game.level), 1);
    checks.push("повреждённое сохранение не ломает игру");
    assert.deepEqual(errors, []);
    assert.deepEqual(requests, []);
    checks.push("нет pageerror и внешних HTTP-запросов");
    console.log(JSON.stringify({ passed: checks.length, checks }, null, 2));
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
