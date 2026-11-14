// Telegram SDK contract mock, not a real Telegram client. Same dependencies as neon_dojo.cjs.
const assert = require('node:assert/strict');
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
let chromium;
try { ({chromium} = require('playwright')); } catch { ({chromium} = require('playwright-core')); }
(async () => {
  let executablePath = process.env.CHROMIUM_EXECUTABLE, args=['--no-sandbox'];
  if (!executablePath) {
    try {const m=require('@sparticuz/chromium'),c=m.default||m;executablePath=await c.executablePath();args=c.args;}catch{}
  }
  const server=http.createServer((req,res)=>{res.setHeader('Content-Type','text/html');res.end(fs.readFileSync(path.resolve(__dirname,'../../index.html')));});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const browser=await chromium.launch({executablePath,args,headless:true});
  try {
    const page=await browser.newPage(),errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.route('https://telegram.org/js/telegram-web-app.js',route=>route.fulfill({contentType:'application/javascript',body:`
      window.calls=[];
      window.Telegram={WebApp:{initData:'mock-only',viewportStableHeight:700,
        ready(){calls.push('ready')},expand(){calls.push('expand')},
        setHeaderColor(c){calls.push(c)},setBackgroundColor(c){calls.push(c)},
        onEvent(n,f){window.viewportCallback=f},close(){calls.push('close')},
        BackButton:{show(){calls.push('back')},onClick(f){window.backCallback=f}},
        HapticFeedback:{impactOccurred(t){calls.push(t)}}}};
    `}));
    await page.goto(`http://127.0.0.1:${server.address().port}/miniapp/dojo`);
    await page.waitForFunction(()=>window.calls?.includes('ready'));
    assert(await page.evaluate(()=>calls.includes('expand')&&calls.includes('back')));
    assert.equal(await page.evaluate(()=>document.documentElement.style.getPropertyValue('--vh')),'700px');
    await page.evaluate(()=>{neonDojo.game.ui.help();backCallback()});
    assert.equal(await page.evaluate(()=>neonDojo.game.ui.modal.open),false);
    await page.evaluate(()=>{neonDojo.game.vibrate();backCallback()});
    assert(await page.evaluate(()=>calls.includes('light')&&calls.includes('close')));
    assert.deepEqual(errors,[]);
    const fallback=await browser.newPage();fallback.on('pageerror',e=>errors.push(e.message));
    await fallback.route('https://telegram.org/**',route=>route.abort());
    await fallback.goto(`http://127.0.0.1:${server.address().port}/miniapp/dojo`);
    assert.equal(await fallback.evaluate(()=>neonDojo.game.state),'playing');
    assert.deepEqual(errors,[]);
    console.log('PASS: SDK ready/expand, viewport, back closes modal/app, haptic, SDK failure fallback (mock only)');
  } finally {await browser.close();await new Promise(resolve=>server.close(resolve));}
})().catch(e=>{console.error(e);process.exitCode=1});
