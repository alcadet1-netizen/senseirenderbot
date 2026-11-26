// Offline mobile Chromium: actual VS dialog, two different server outcomes and replay suppression.
const assert = require('node:assert/strict');
const path = require('node:path');
const {chromium} = require('playwright-core');
(async () => {
  const pkg = await import(require.resolve('@sparticuz/chromium'));
  const bin = pkg.default.default || pkg.default;
  const browser = await chromium.launch({executablePath: await bin.executablePath(), args: bin.args.filter(a=>a!=='--single-process')});
  try {
    for (const reduced of [false, true]) {
      const page = await browser.newPage({viewport:{width:360,height:690}, reducedMotion:reduced?'reduce':'no-preference'});
      const errors = [];
      page.on('pageerror', e => errors.push(e.message));
      await page.route('**/*', async route => {
        const url = new URL(route.request().url());
        if (url.hostname !== 'dojo.test') return route.abort();
        if (url.pathname.includes('/api/')) return route.fulfill({json:{phase:'fight', id:17, side:0, round:2,
          seconds:90, bet:300, names:['Сэнсэй','Ниндзя'], hits:[1,0], moves:{}, exchange:{round:1,strikes:[
            {attack:'hit_l',dodge:'dodge_r',hit:true}, {attack:'hit_r',dodge:'dodge_r',hit:false}]}}});
        const file = url.pathname.replace(/^\/miniapp\/dojo\/?/, '') || 'index.html';
        return route.fulfill({path:path.join('src/web/dojo',file)});
      });
      await page.goto('https://dojo.test/miniapp/dojo');
      await page.locator('#vs-open').evaluate(el=>el.click());
      assert.equal(await page.locator('.vs-fighter .vs-ninja').count(), 2);
      const read = page.locator('#vs-read');
      await page.waitForFunction(()=>!document.querySelector('#vs-read').hidden && document.querySelector('#vs-read-result').textContent==='Попадание');
      assert.equal(await page.locator('.vs-fighter.left').getAttribute('data-pose'), 'sweep');
      assert.equal(await page.locator('.vs-fighter.right').getAttribute('data-pose'), 'recoil');
      assert.equal(await read.locator('b').allTextContents().then(x=>x.join('')), '←→');
      assert.equal(await page.locator('#vs-right').getAttribute('data-health'),'1');
      await page.waitForFunction(()=>!document.querySelector('#vs-read').hidden && document.querySelector('#vs-read-result').textContent==='Уклонился!');
      assert.equal(await page.locator('.vs-fighter.right').getAttribute('data-pose'), 'kick');
      assert.equal(await page.locator('.vs-fighter.left').getAttribute('data-pose'), 'slip');
      assert.equal(await read.locator('b').allTextContents().then(x=>x.join('')), '→→');
      assert.equal(await page.locator('#vs-left').getAttribute('data-health'),'2');
      await page.locator('#vs-recap summary').click();
      assert.equal(await page.locator('#vs-recap li').count(),2);
      assert.equal(await page.locator('#vs-controls').isVisible(),true);
      assert.deepEqual(errors,[]);
      await page.close();
    }
    console.log('Mobile VS: hit, dodge, HP, recap and next-round controls passed in both motion modes.');
  } finally { await browser.close(); }
})().catch(err=>{console.error(err);process.exitCode=1;});
