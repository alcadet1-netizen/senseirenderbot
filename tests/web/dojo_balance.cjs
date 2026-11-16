// Ускоренная проверка проходимости: не человеческий win-rate и не FPS-тест.
const assert = require("node:assert/strict");
const { chromium } = require("playwright-core");
(async () => {
  const mod = require("@sparticuz/chromium"),
    bin = mod.default || mod;
  const b = await chromium.launch({
    executablePath: await bin.executablePath(),
    args: bin.args,
    headless: true,
  });
  const p = await b.newPage();
  await p.goto(process.env.DOJO_URL || "http://127.0.0.1:8080/miniapp/dojo");
  const results = await p.evaluate(() => {
    const results = [];
    for (let seed = 1; seed <= 3; seed++) {
      let state = seed;
      const old = Math.random;
      Math.random = () =>
        (state = (state * 1664525 + 1013904223) >>> 0) / 4294967296;
      game.start();
      game.sound.on = false;
      let steps = 0;
      for (; steps < 45000 && ["game", "shop"].includes(game.state); steps++) {
        if (game.state === "shop") {
          game.shopWait = 0;
          while (
            game.coins >= CONFIG.cost.warrior &&
            game.player.army < CONFIG.maxArmy
          )
            game.buy("warrior");
          while (game.coins >= CONFIG.cost.damage && game.player.damage < 23)
            game.buy("damage");
          if (game.coins >= CONFIG.cost.speed) game.buy("speed");
          game.waves.next();
          game.state = "game";
          continue;
        }
        const boss = game.enemies.find(
          (e) => e.type === "boss" && e.warning > 0,
        );
        const bolt = game.hazards.find(
          (e) => e.y > 600 && Math.abs(e.targetX - game.player.x) < 50,
        );
        const close = game.enemies
          .filter((e) => !e.dead)
          .sort((a, b) => b.y - a.y)[0];
        const pickup = game.pickups.find((e) => e.y > 650 && e.y < 800);
        if (bolt) game.player.target = bolt.targetX < 270 ? 430 : 110;
        else if (boss) game.player.target = boss.attackX < 270 ? 430 : 110;
        else if (pickup) game.player.target = pickup.x;
        else if (close) game.player.target = close.x;
        game.update(0.02);
      }
      results.push({
        seed,
        result: game.state,
        wave: game.waves.index + 1,
        kills: game.kills,
        lives: game.player.lives,
        army: game.player.army,
        seconds: steps * 0.02,
      });
      Math.random = old;
    }
    game.state = "pause";
    return results;
  });
  // "На грани": all three optimised runs must reach the final wave, at least
  // one must win, and at least one must fall — a full sweep means the game
  // became too easy again, an early death means it is unwinnable.
  for (const r of results) assert.equal(r.wave, 5, JSON.stringify(r));
  const wins = results.filter((r) => r.result === "victory").length;
  assert.ok(wins >= 1, "no seed can win: " + JSON.stringify(results));
  assert.ok(wins < results.length, "too easy: " + JSON.stringify(results));
  console.log(results);
  await b.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
