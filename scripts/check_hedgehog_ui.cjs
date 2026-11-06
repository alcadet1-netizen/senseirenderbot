/* Optional real Chromium smoke test. Dependencies/artifacts stay outside Git:
 * npm install --prefix .cache/hedgehog-ui --no-audit --no-fund playwright-core@1.51.1 @sparticuz/chromium@133.0.0
 * node scripts/check_hedgehog_ui.cjs
 * Telegram SDK and API are mocked; real signatures/game accounting have Python tests.
 */
const {createRequire} = require('node:module');
const fs = require('node:fs/promises');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const cachedRequire = createRequire(path.join(root, '.cache/hedgehog-ui/package.json'));
const {chromium: playwright} = cachedRequire('playwright-core');
const chromium = cachedRequire('@sparticuz/chromium');
(async () => {
  const libs = path.join(root, '.cache/hedgehog-ui/libs');
  await fs.mkdir(libs, {recursive:true});
  const archive = await fs.readFile(path.join(root,'.cache/hedgehog-ui/node_modules/@sparticuz/chromium/bin/al2023.tar.br'));
  require('node:child_process').execFileSync('tar',['xf','-','-C',libs],{input:require('node:zlib').brotliDecompressSync(archive)});
  const executablePath = await chromium.executablePath();
  const env = {...process.env, LD_LIBRARY_PATH:path.join(libs,'lib') + ':' + (process.env.LD_LIBRARY_PATH || '')};
  const browser = await playwright.launch({env,executablePath, args: chromium.args.filter(a => a !== '--single-process'), headless: true});
  try {
    for (const success of [true, false]) {
      const page = await browser.newPage({viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true});
      const errors = [];
      page.on('pageerror', e => errors.push(e.message));
      await page.route('https://telegram.org/**', route => route.fulfill({contentType: 'text/javascript', body: `window.Telegram={WebApp:{initData:'signed-test',ready(){},expand(){},close(){},HapticFeedback:{notificationOccurred(){},impactOccurred(){}}}};`}));
      await page.route('https://mini.test/**', async route => {
        const url = new URL(route.request().url());
        if (url.pathname.includes('/api/')) {
          const start = url.pathname.endsWith('/start');
          return route.fulfill({json: start ? {state:'playing', remaining_ms:800} : {state:'done', result:{success, total_xp:60, total_coins:25, streak:success ? 9 : 0, message:success ? 'Вы погладили ежа!' : 'Вы не смогли погладить ежа! Монеты и XP остались при вас.'}, ...(success ? {image:'/miniapp/hedgehog/picture/0'} : {})}});
        }
        if (url.pathname.includes('/picture/')) {
          const dir = path.join(root, 'src/infra/storage/ega');
          const name = (await fs.readdir(dir)).find(n => /\.(png|jpe?g)$/i.test(n));
          return route.fulfill({body:await fs.readFile(path.join(dir,name)), contentType:name.endsWith('.png') ? 'image/png' : 'image/jpeg'});
        }
        const name = url.pathname.endsWith('.css') ? 'app.css' : url.pathname.endsWith('.js') ? 'app.js' : 'index.html';
        return route.fulfill({body:await fs.readFile(path.join(root,'src/web/hedgehog',name)),contentType:name.endsWith('.css') ? 'text/css' : name.endsWith('.js') ? 'text/javascript' : 'text/html'});
      });
      await page.goto('https://mini.test/miniapp/hedgehog?session=test');
      if (success) await page.screenshot({path:path.join(root,'.cache/hedgehog-ui/start.png'),fullPage:true});
      await page.locator('#play').click();
      await page.locator('#stage').tap();
      await page.locator('#result:not([hidden])').waitFor();
      assert.match(await page.locator('#result-title').innerText(), success ? /Вы погладили/ : /кактус/);
      assert.equal(await page.locator('#reward-image').isVisible(), success);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      assert.deepEqual(errors, []);
      await page.screenshot({path:path.join(root,`.cache/hedgehog-ui/${success ? 'success' : 'failure'}.png`),fullPage:true});
      await page.close();
    }
    console.log('Chromium: mobile start, pet gesture, 95% success image, 5% failure, no JS errors/overflow — OK');
  } finally { await browser.close(); }
})().catch(e => {console.error(e);process.exitCode=1;});
