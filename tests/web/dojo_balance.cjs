/* Seeded balance smoke test, not a measurement of human win rate.
 * Usage/dependencies: neon_dojo.cjs. Results are JSON for easy comparison.
 * AI RNG is independent of particles, so results repeat between runs.
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
    });
    await page.goto(
      pathToFileURL(path.resolve(__dirname, "../../index.html")).href,
    );
    const results = await page.evaluate(() => {
      const { game: g, CONFIG: C } = neonDojo;
      g.hidden = true;
      // No UI, storage or rendering in accelerated simulation. Same combat code.
      g.ui.toast = () => {};
      g.ui.refresh = () => {};
      g.ui.result = () => {};
      g.persist = () => {};
      const results = [];
      for (const width of [350, 980])
        for (const policy of [
          "idle",
          "idlefort",
          "rush",
          "mixed",
          "air",
          "elite",
        ])
          for (let seed = 1; seed <= 3; seed++) {
            let rng = seed;
            g.random = () => {
              rng = (Math.imul(rng, 1664525) + 1013904223) >>> 0;
              return rng / 4294967296;
            };
            g.w = width;
            g.ground = 340;
            g.unitScale = width < 440 ? 0.67 : 1;
            g.flightHeight = 64 * g.unitScale;
            g.level = policy === "elite" || policy === "idlefort" ? 6 : 1;
            g.tower = policy === "idlefort" ? 3 : 0;
            g.reserve.fill(false);
            g.units.seed = 0;
            g.newBattle();
            let nextDecision = 0;
            for (let i = 0; i < 27000 && g.state === "playing"; i++) {
              if (g.elapsed >= nextDecision && !policy.startsWith("idle")) {
                nextDecision += 0.3;
                let nearby = 0,
                  count = 0;
                for (const u of g.units.units)
                  if (u.active && u.side) {
                    count++;
                    if (u.x < Math.min(250, g.w * 0.4)) nearby++;
                  }
                if (policy !== "rush") {
                  const next = C.levels[g.level];
                  if (next && g.energy >= next.cost) g.upgrade();
                  if (
                    g.level >= 2 &&
                    g.tower === 0 &&
                    nearby >= 2 &&
                    g.energy >= 75
                  )
                    g.upgradeTower();
                  if (g.energy >= 20 && (nearby >= 3 || count >= 5))
                    g.superAttack();
                }
                const saving =
                  policy !== "rush" &&
                  g.level < 6 &&
                  (g.units.count[0] >= 3 ||
                    g.energy > C.levels[g.level].cost * 0.6);
                const priority =
                  policy === "rush"
                    ? [1, 0]
                    : policy === "air"
                      ? [7, 2, 1]
                      : [3, 6, 4, 1, 2, 7, 5, 0];
                if (!saving)
                  for (const j of priority) {
                    const c = C.cards[j];
                    if (
                      // Осознанный состав: не забиваем 48 мест новичками и аурами.
                      (policy === "air" ||
                        policy === "rush" ||
                        g.units.units.filter(
                          (u) => u.active && u.side === 0 && u.kind === j,
                        ).length < [4, 2, 6, 12, 3, 3, 6, 4][j]) &&
                      (j !== 0 || g.level < 3 || policy === "rush") &&
                      g.level >= c.level &&
                      g.charges[j] >= c.cd &&
                      g.energy >= c.cost &&
                      (j !== 5 || g.elapsed >= 30)
                    )
                      g.summon(j);
                  }
              }
              g.update(1 / 30);
            }
            results.push({
              width,
              policy,
              seed,
              outcome: g.state,
              time: Math.round(g.elapsed),
              dojo: g.level,
              tower: g.tower,
              enemy: g.enemyLevel,
              ourHP: Math.round(g.ourHp),
              enemyHP: Math.round(g.enemyHp),
              kills: g.kills,
              units: [...g.units.count],
            });
          }
      return results;
    });
    for (const r of results) {
      if (r.policy.startsWith("idle"))
        assert.equal(r.outcome, "lost", "AFK must not win");
      if (r.policy === "mixed" || r.policy === "elite")
        assert.equal(r.outcome, "won", "mixed armies can finish");
      assert(
        r.units.every((n) => n <= 48),
        "pool cap",
      );
      assert(r.ourHP >= 0 && r.enemyHP >= 0, "no negative castle HP");
    }
    // A badly composed army may sustain a siege: report timeouts, never call them wins.
    console.log(
      JSON.stringify(
        { scenarios: results.length, limitSeconds: 900, results },
        null,
        2,
      ),
    );
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
