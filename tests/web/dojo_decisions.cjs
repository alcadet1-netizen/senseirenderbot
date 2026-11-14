/* Clear decisions, safe restarts and authoritative pending state. Local Chromium. */
const assert = require("node:assert/strict"),
  path = require("node:path");
const { pathToFileURL } = require("node:url"),
  { chromium } = require("playwright-core");
(async () => {
  const mod = require("@sparticuz/chromium"),
    c = mod.default || mod;
  const browser = await chromium.launch({
    executablePath:
      process.env.CHROMIUM_EXECUTABLE || (await c.executablePath()),
    args: c.args,
    headless: true,
  });
  try {
    const p = await browser.newPage({ viewport: { width: 740, height: 360 } }),
      errors = [],
      checks = [];
    p.on("pageerror", (e) => errors.push(e.message));
    await p.goto(
      pathToFileURL(path.resolve(__dirname, "../../index.html")).href,
    );
    await p
      .getByRole("button", { name: "∞ Свободная битва", exact: true })
      .click();
    await p.evaluate(() => {
      const g = neonDojo.game;
      g.energy = 0;
      g.ui.refresh();
    });
    assert.match(
      await p.locator(".card .sub").first().innerText(),
      /Нужно \+6/,
    );
    assert(
      !(await p
        .locator(".card")
        .first()
        .evaluate((e) => e.classList.contains("ready"))),
    );
    await p.evaluate(() => {
      const g = neonDojo.game;
      g.energy = 87;
      g.charges[0] = 0;
      g.ui.refresh();
    });
    assert.match(await p.locator(".card .sub").first().innerText(), /Заряд/);
    await p.evaluate(() => {
      const g = neonDojo.game;
      g.units.count[0] = 48;
      g.ui.refresh();
    });
    assert.match(await p.locator(".card .sub").first().innerText(), /48 \/ 48/);
    await p.evaluate(() => {
      neonDojo.game.units.count[0] = 0;
      neonDojo.game.charges[0] = 3;
      neonDojo.game.ui.refresh();
    });
    checks.push("readiness follows energy, charge and army cap");
    const energy = await p.evaluate(() => neonDojo.game.energy);
    const card = await p.locator(".card").first().boundingBox();
    await p.mouse.move(card.x + card.width / 2, card.y + card.height / 2);
    await p.mouse.down();
    await p.waitForFunction(() => document.querySelector("#modal").open);
    await p.mouse.up();
    await p.getByRole("heading", { name: "Ронин", exact: true }).waitFor();
    assert.equal(await p.evaluate(() => neonDojo.game.units.count[0]), 0);
    assert.match(
      await p.locator("#modalBody").innerText(),
      /Не атакует воздух/,
    );
    const time = await p.evaluate(() => neonDojo.game.elapsed);
    await p.waitForTimeout(250);
    assert.equal(await p.evaluate(() => neonDojo.game.elapsed), time);
    await p.locator("#modalAction").click();
    assert((await p.evaluate(() => neonDojo.game.energy)) >= energy);
    checks.push(
      "long press inspects without summoning or spending; solo pauses",
    );
    await p.locator(".card").first().focus();
    await p.keyboard.press("F2");
    assert(await p.locator("#modal").isVisible());
    await p.locator("#modalAction").click();
    checks.push("keyboard inspection works");
    await p.evaluate(() => neonDojo.game.summon(0));
    const seed = await p.evaluate(
      () => neonDojo.game.units.units.find((u) => u.active).seed,
    );
    await p.locator("#modeMenuBtn").click();
    await p
      .getByRole("button", { name: "∞ Свободная битва", exact: true })
      .click();
    await p
      .getByRole("heading", { name: "Заменить текущий бой?", exact: true })
      .waitFor();
    await p.locator("#closeModal").click();
    assert.equal(
      await p.evaluate(
        () => neonDojo.game.units.units.find((u) => u.active).seed,
      ),
      seed,
    );
    await p
      .getByRole("button", { name: "∞ Свободная битва", exact: true })
      .click();
    await p.locator("#modalAction").click();
    assert.equal(await p.evaluate(() => neonDojo.game.units.count[0]), 0);
    checks.push(
      "cancelled replacement preserves army; confirmed replacement resets it",
    );
    await p.evaluate(() => {
      neonDojo.modes.startStage(1);
      neonDojo.game.ui.confirmRestart();
    });
    await p
      .getByRole("heading", { name: "Заменить текущий бой?", exact: true })
      .waitFor();
    await p.locator("#closeModal").click();
    checks.push("campaign restart also requires explicit confirmation");
    const boost = await p.evaluate(() => {
      const g = neonDojo.game;
      g.coins = 40;
      const CONFIG = neonDojo.CONFIG;
      for (let i = 0; i < CONFIG.cards.length; i++)
        g.charges[i] = CONFIG.cards[i].cd;
      g.boost();
      const full = g.coins;
      g.charges[1] = 0;
      g.boost();
      return { full, spent: g.coins, charge: g.charges[1] };
    });
    assert.deepEqual(boost, { full: 40, spent: 20, charge: 5 });
    checks.push(
      "boost never charges for a full deck; useful boost spends exactly 20",
    );
    // Synthetic socket: no timers/physics or fake server success, just outbound commands.
    const net = await p.evaluate(() => {
      const m = neonDojo.modes,
        g = neonDojo.game,
        sent = [];
      g.mode = "pvp";
      g.state = "playing";
      m.stopped = false;
      m.pending.clear();
      m.ws = {
        readyState: WebSocket.OPEN,
        send(raw) {
          sent.push(JSON.parse(raw));
        },
        close() {},
      };
      const energy = g.energy,
        a = m.command("summon", 0),
        b = m.command("summon", 0);
      const pending = g.ui.cardStatus(0).reason;
      const pl = {
        level: 1,
        tower: 0,
        energy: 87,
        hp: 1000,
        maxHp: 1000,
        superCd: 0,
        wave: 0,
        waveCount: 0,
        charges: [3, 12, 0, 0, 0, 0, 0, 0],
      };
      m.apply({
        players: [pl, pl],
        names: ["A", "B"],
        status: "playing",
        elapsed: 1,
        units: [],
        shots: [],
        seq: [m.seq, 0],
      });
      const cleared = !m.pending.size;
      m.command("summon", 0);
      g.ui.help();
      const help = document.querySelector("#modalBody").textContent;
      return {
        a,
        b,
        pending,
        cleared,
        count: sent.length,
        first: sent[0].seq,
        last: sent[1].seq,
        energy,
        help,
      };
    });
    assert(net.a && !net.b && net.cleared);
    assert.equal(net.count, 2);
    assert(net.last > net.first);
    assert.equal(net.pending, "Ждём сервер");
    assert.match(net.help, /меню не останавливает бой/);
    assert.match(net.help, /Резерв карточек в PvP отключён/);
    checks.push(
      "PvP duplicate tap blocked until server seq acknowledgement; mode-specific help",
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
