// Optional real-browser coverage. Run with playwright-core and @sparticuz/chromium.
const assert = require('node:assert/strict');
const path = require('node:path');
const { chromium } = require('playwright-core');

(async () => {
  const mod = require('@sparticuz/chromium');
  const bin = mod.default || mod;
  const browser = await chromium.launch({executablePath: await bin.executablePath(), args: bin.args, headless: true});
  try {
    for (const viewport of [{width:320,height:568}, {width:360,height:640},
      {width:390,height:844}, {width:768,height:1024}, {width:844,height:390}, {width:1440,height:900}]) {
      const page = await browser.newPage({viewport, reducedMotion: 'reduce'});
      const errors = [], calls = [], assets = [];
      let phase = 'lobby';
      page.on('pageerror', e => errors.push(e.message));
      await page.addInitScript(() => {
        window.Telegram = {WebApp: {initData: 'signed-test', initDataUnsafe: {user: {id: 7}}}};
      });
      await page.route('**/*', async route => {
        const url = new URL(route.request().url());
        if (url.hostname !== 'dojo.test') return route.abort();
        if (url.pathname.includes('/assets/')) assets.push(url.pathname);
        if (url.pathname.includes('/api/')) {
          const action = url.pathname.split('/').pop();
          calls.push({action, body: route.request().postDataJSON()});
          if (action === 'vs_rooms') return route.fulfill({json:{rooms:[
            {token:'1', owner_name:'Очень длинное имя соперника без переполнения', bet:500, seconds:240},
            {token:'2', owner_name:'sensei_hero', bet:1000, seconds:240} ]}});
          if (action === 'vs_state' || action === 'vs_commit') {
            let state = {phase};
            if (phase === 'fight' || phase === 'finished') state = {
              phase, id:17, side:0, round:2, seconds:90, bet:500, winner:true,
              names:['Сэнсэй с очень длинным именем', 'Ниндзя'], hits:[1,0],
              moves: action === 'vs_commit' ? {attack:'hit_l',dodge:'dodge_r'} : {}};
            if (phase === 'invited' || phase === 'waiting') state = {phase, chat:'Игровой чат', bet:500, seconds:60};
            return route.fulfill({json:state});
          }
          const now = Date.now()/1000;
          return route.fulfill({json:{phase:'ready',server_now:now,balance:12840,reward:90,next_reward:90,
            energy:100,energy_max:100,energy_per_hour:100,base_rate:75,current_rate:75,
            cycle_seconds:10800,progress:0,progress_percent:0}});
        }
        const file = url.pathname.replace(/^\/miniapp\/dojo\/?/, '') || 'index.html';
        return route.fulfill({path:path.join('src/web/dojo',file)});
      });
      await page.goto('https://dojo.test/miniapp/dojo');
      // No arena image or full-size canvas is allocated before the dialog opens.
      assert.equal(await page.locator('.vs-fighter .vs-ninja').count(), 0);
      assert.equal(await page.locator('.vs-bg').getAttribute('src'), null);
      assert.equal(await page.locator('.vs-trail-canvas').evaluate(el => el.width * el.height), 1);
      assert.equal(assets.some(p => /ninja-sensei-[12]|dojo-temple-bg/.test(p)), false);
      await page.locator('#vs-open').evaluate(el => el.click());
      await page.waitForFunction(() => document.querySelectorAll('.vs-room').length === 2);
      assert.equal(await page.locator('.vs-fighter .vs-ninja').count(), 2);
      assert.equal(await page.locator('#vs-controls').isVisible(), false);
      assert.equal(await page.locator('[data-bet="500"]').getAttribute('aria-pressed'), 'true');
      await page.locator('[data-bet="1000"]').click();
      assert.equal(await page.locator('#vs-bet').inputValue(), '1000');
      assert.equal(await page.locator('#vs-room-bet').textContent(), '1000');
      assert.equal(await page.locator('[data-bet="1000"]').getAttribute('aria-pressed'), 'true');
      const layout = await page.evaluate(() => {
        const d = document.querySelector('#vs-dialog');
        const nodes = [...d.querySelectorAll('#vs-bet, .vs-bet-presets button, #vs-send, .vs-room, .vs-room-action, #vs-room-create')];
        const rect = d.getBoundingClientRect();
        return {viewport: innerWidth, dialog: rect.toJSON(), scrollWidth: d.scrollWidth, clientWidth: d.clientWidth,
          elements: nodes.map(n => ({name:n.className || n.id, rect:n.getBoundingClientRect().toJSON()}))};
      });
      assert.ok(layout.dialog.left >= 0 && layout.dialog.right <= viewport.width, JSON.stringify(layout));
      assert.ok(layout.scrollWidth <= layout.clientWidth + 1, JSON.stringify(layout));
      for (const item of layout.elements) {
        assert.ok(item.rect.left >= layout.dialog.left - 1 && item.rect.right <= layout.dialog.right + 1, JSON.stringify(item));
      }
      assert.ok((await page.locator('#vs-send').boundingBox()).height >= 43);
      assert.ok((await page.locator('#vs-room-create').boundingBox()).height >= 44);
      // The fight screen preserves the two-choice / single-submit protocol.
      await page.locator('#vs-close').click();
      await page.waitForFunction(() => !document.querySelector('.vs-bg').hasAttribute('src'));
      assert.equal(await page.locator('.vs-fighter .vs-ninja').count(), 0);
      assert.equal(await page.locator('.vs-trail-canvas').evaluate(el => el.width * el.height), 1);
      phase = 'fight';
      await page.locator('#vs-open').evaluate(el => el.click());
      await page.locator('#vs-controls:not([hidden])').waitFor();
      assert.equal(await page.locator('#vs-lobby').isVisible(), false);
      await page.locator('[data-vs="hit_l"]').click();
      assert.equal(await page.locator('#vs-commit').isDisabled(), true);
      await page.locator('[data-vs="dodge_r"]').click();
      assert.equal(await page.locator('#vs-commit').isEnabled(), true);
      assert.equal(await page.locator('[data-vs="hit_l"]').getAttribute('aria-pressed'), 'true');
      await page.locator('#vs-commit').click();
      await page.waitForFunction(() => document.querySelector('#vs-controls').hidden);
      const commit = calls.filter(x => x.action === 'vs_commit');
      assert.equal(commit.length, 1);
      assert.equal(commit[0].body.attack, 'hit_l');
      assert.equal(commit[0].body.dodge, 'dodge_r');
      if (viewport.width === 390) {
        for (const extra of ['invited', 'waiting', 'finished']) {
          await page.locator('#vs-close').click();
          await page.waitForFunction(() => !document.querySelector('#vs-dialog').open);
          phase = extra;
          await page.locator('#vs-open').evaluate(el => el.click());
          await page.waitForFunction(expected => document.querySelector('#vs-dialog').dataset.phase === expected, extra);
          assert.equal(await page.locator('#vs-accept').isVisible(), extra === 'invited');
          assert.equal(await page.locator('#vs-rematch').isVisible(), extra === 'finished');
          assert.equal(await page.locator('#vs-lobby').isVisible(), false);
          assert.equal(await page.locator('#vs-controls').isVisible(), false);
        }
      }
      assert.deepEqual(errors, []);
      await page.close();
      console.log(`Arena ${viewport.width}x${viewport.height}: layout, lifecycle and fight actions passed.`);
    }
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
