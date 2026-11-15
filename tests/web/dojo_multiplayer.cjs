/* Real local WebSockets + two Chromium clients; Telegram API/SDK are mocks.
 * PYTHON=.venv/bin/python NODE_PATH=... node tests/web/dojo_multiplayer.cjs
 */
const assert = require("node:assert/strict"),
  crypto = require("node:crypto"),
  path = require("node:path");
const { spawn } = require("node:child_process");
const { chromium } = require("playwright-core");
function signed(id) {
  const data = {
    auth_date: String(Math.floor(Date.now() / 1000)),
    user: JSON.stringify({ id, first_name: "Игрок " + id }),
  };
  const secret = crypto
    .createHmac("sha256", "WebAppData")
    .update("123456:local-test-only")
    .digest();
  data.hash = crypto
    .createHmac("sha256", secret)
    .update(
      Object.keys(data)
        .sort()
        .map((k) => k + "=" + data[k])
        .join("\n"),
    )
    .digest("hex");
  return new URLSearchParams(data).toString();
}
(async () => {
  const server = spawn(
    process.env.PYTHON || "python",
    ["tests/web/dojo_test_server.py", "18764"],
    {
      cwd: path.resolve(__dirname, "../.."),
      stdio: ["ignore", "pipe", "inherit"],
    },
  );
  let browser;
  try {
    await new Promise((resolve, reject) => {
      server.stdout.on("data", (d) => {
        if (String(d).includes("Running on")) resolve();
      });
      server.on("exit", (c) => reject(Error("Fixture exit " + c)));
      setTimeout(() => reject(Error("Fixture startup timeout")), 15000).unref();
    });
    const mod = require("@sparticuz/chromium"),
      c = mod.default || mod;
    browser = await chromium.launch({
      executablePath:
        process.env.CHROMIUM_EXECUTABLE || (await c.executablePath()),
      args: c.args.filter(
        (a) =>
          !a.includes("single-process") && !a.includes("disable-web-security"),
      ),
      headless: true,
    });
    const errors = [];
    const a = await browser.newPage({ viewport: { width: 900, height: 450 } }),
      b = await browser.newPage({ viewport: { width: 740, height: 400 } });
    for (const [p, id] of [
      [a, 1],
      [b, 2],
    ]) {
      p.on("pageerror", (e) => errors.push(e.message));
      await p.addInitScript((raw) => {
        window.Telegram = {
          WebApp: {
            initData: raw,
            ready() {},
            expand() {},
            onEvent() {},
            shareMessage(id) {
              window.sharedPrepared = id;
            },
          },
        };
      }, signed(id));
    }
    const url = "http://127.0.0.1:18764/miniapp/dojo";
    await a.goto(url);
    assert.match(await a.locator("#modeMenu").innerText(), /30 уровней/);
    await a
      .getByRole("button", { name: "⚔ Одиночная игра · 30 уровней" })
      .click();
    assert.equal(await a.locator("#modeMenu button:disabled").count(), 4);
    await a.getByRole("button", { name: "⚔ 1. Ворота", exact: true }).click();
    assert.equal(await a.evaluate(() => neonDojo.modes.stage), 1);
    // Controlled victory checks progression, not player balance.
    await a.evaluate(() => {
      neonDojo.game.enemyHp = 0;
      neonDojo.game.update(0.05);
    });
    await a
      .getByRole("button", { name: "Следующий уровень", exact: true })
      .click();
    assert.equal(await a.evaluate(() => neonDojo.modes.stage), 2);
    await a.locator("#modeMenuBtn").click();
    const saved = await a.evaluate(() => {
      neonDojo.game.persist();
      return localStorage.getItem(neonDojo.game.save.key);
    });
    await a
      .getByRole("button", { name: "✉ Пригласить соперника", exact: true })
      .click();
    await a
      .getByRole("button", { name: "✉ Отправить в чат", exact: true })
      .click();
    assert.equal(await a.evaluate(() => window.sharedPrepared), "prepared");
    const room = await a.evaluate(() => neonDojo.modes.room);
    if (Number(process.env.DOJO_IDLE_TEST_SECONDS) > 0) {
      await a.waitForTimeout(Number(process.env.DOJO_IDLE_TEST_SECONDS) * 1000);
      assert(
        await a.evaluate(
          () =>
            neonDojo.modes.ws.readyState === WebSocket.OPEN &&
            neonDojo.modes.status === "waiting",
        ),
      );
    }
    // Reproduce Telegram closing/recreating the host WebView after chat sharing.
    await a.goto(url);
    await a
      .getByRole("button", { name: "↻ Вернуться в PvP-комнату", exact: true })
      .waitFor();
    await b.goto(url + "?room=" + room);
    await b
      .getByRole("button", { name: "☾ Играть за Тень", exact: true })
      .click();
    await b
      .getByRole("heading", { name: "Ожидаем создателя комнаты", exact: true })
      .waitFor();
    await a
      .getByRole("button", { name: "↻ Вернуться в PvP-комнату", exact: true })
      .click();
    await a
      .getByRole("button", { name: "☀ Играть за Рассвет", exact: true })
      .click();
    await Promise.all([
      a.waitForFunction(() => neonDojo.game.state === "playing"),
      b.waitForFunction(() => neonDojo.game.state === "playing"),
    ]);
    await a.evaluate(() => neonDojo.game.summon(0));
    await b.waitForFunction(() => neonDojo.game.units.count[1] === 1);
    await a.waitForFunction(() => neonDojo.game.units.count[0] === 1);
    assert.equal(await a.evaluate(() => neonDojo.game.level), 1);
    assert.equal(
      await a.evaluate(() => localStorage.getItem(neonDojo.game.save.key)),
      saved,
    );
    // A dialog must NOT pause the server's physics/energy.
    const elapsed = await a.evaluate(() => neonDojo.game.elapsed);
    await a.evaluate(() => neonDojo.game.ui.help());
    await a.waitForFunction((t) => neonDojo.game.elapsed > t + 0.4, elapsed);
    await a.evaluate(() => neonDojo.game.ui.modal.close());
    // Transport drop/reconnect retains identity and synchronized state.
    await b.evaluate(() => neonDojo.modes.ws.close());
    await a.waitForFunction(() => neonDojo.modes.status === "paused");
    await b.waitForFunction(() => neonDojo.game.state === "playing", null, {
      timeout: 15000,
    });
    await b.locator("#modeMenuBtn").click();
    await b
      .getByRole("button", { name: "Сдаться и выйти", exact: true })
      .click();
    await a
      .getByRole("heading", { name: "勝 · Победа!", exact: true })
      .waitFor();
    await a
      .getByRole("button", { name: "В главное меню", exact: true })
      .click();
    assert.equal(
      await a.evaluate(() => localStorage.getItem(neonDojo.game.save.key)),
      saved,
    );
    assert.deepEqual(errors, []);
    // Offline remains a single HTML and gives a clear PvP explanation.
    await a.goto(
      require("node:url").pathToFileURL(path.resolve("index.html")).href,
    );
    await a
      .getByRole("button", { name: "✉ Пригласить соперника", exact: true })
      .click();
    assert.match(
      await a.locator("#modeMenu").innerText(),
      /Одиночная кампания доступна/,
    );
    console.log(
      "PASS: menu, campaign, native share mock, host WebView reopen without room URL, waiting guest, two real WS clients, commands, reconnect, surrender, offline",
    );
  } finally {
    if (browser) await browser.close();
    server.kill();
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
