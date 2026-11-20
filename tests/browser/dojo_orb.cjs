// Run with playwright-core installed and CHROMIUM_PATH set to a Chromium executable.
const { chromium } = require('playwright-core');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const html = fs.readFileSync('src/web/dojo/index.html', 'utf8')
  .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, '')
  .replace(/<link\b[^>]*>/gi, '');
const css = fs.readFileSync('src/web/dojo/style.css', 'utf8');
(async () => {
  const browser = await chromium.launch({executablePath: process.env.CHROMIUM_PATH, headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage']});
  const page = await browser.newPage();
  for (const [width, height] of [[320,480],[320,568],[360,640],[375,667],[390,844],[430,932],[1024,768]]) {
    await page.setViewportSize({width, height});
    await page.setContent(html);
    await page.addStyleTag({content: css + '\n*, *::before, *::after { animation: none !important; transition: none !important; }'});
    for (const phase of ['ready', 'mining']) for (const boost of [false, true]) for (const label of ['НАЧАТЬ МАЙНИНГ', 'START MINING']) {
      const result = await page.evaluate(({phase, boost, label}) => {
        const app = document.getElementById('app'), action = document.getElementById('action');
        app.classList.remove('phase-ready', 'phase-mining'); app.classList.add('phase-' + phase);
        action.classList.toggle('is-timer', phase === 'mining');
        document.getElementById('timer-face').hidden = phase !== 'mining';
        document.getElementById('timer-digits').textContent = '00:59:56';
        document.getElementById('action-label').textContent = label;
        document.getElementById('orb-sub').textContent = '3 ЧАСА · 18 COIN';
        const energy = document.querySelector('.energy'); energy.classList.toggle('is-empty', boost);
        document.querySelector('.boost-pill').hidden = !boost;
        const rect = el => { const r = el.getBoundingClientRect(); return {x:r.x,y:r.y,w:r.width,h:r.height}; };
        return {button: rect(action), digits: rect(document.getElementById('timer-digits')),
          faceDisplay: getComputedStyle(document.getElementById('timer-face')).display,
          label: rect(document.getElementById('action-label'))};
      }, {phase, boost, label});
      const {button:b, digits:d} = result;
      const name = `${width}x${height} ${phase} boost=${boost} ${label}`;
      assert.ok(Math.abs(b.w-b.h)<1, `${name}: button is not round`);
      assert.ok(b.w>=120, `${name}: button too small: ${b.w}`);
      if (phase === 'mining') {
        assert.ok(Math.abs((d.x+d.w/2)-(b.x+b.w/2))<1, `${name}: clock horizontally off centre`);
        assert.ok(Math.abs((d.y+d.h/2)-(b.y+b.h/2))<1, `${name}: clock vertically off centre`);
        assert.ok(d.w<=b.w, `${name}: clock overflows`);
      } else {
        assert.equal(result.faceDisplay, 'none', `${name}: hidden clock visible`);
        assert.ok(result.label.x >= b.x && result.label.x+result.label.w <= b.x+b.w, `${name}: label overflows`);
      }
    }
  }
  await browser.close(); console.log('Dojo orb geometry passed');
})().catch(error => {console.error(error); process.exitCode=1;});
