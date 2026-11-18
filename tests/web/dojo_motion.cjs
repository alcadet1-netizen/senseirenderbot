const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const bootstrap = fs.readFileSync('src/web/dojo/motion.js', 'utf8');
const source = fs.readFileSync('src/web/dojo/miner.js', 'utf8');
const html = fs.readFileSync('src/web/dojo/index.html', 'utf8');
const css = fs.readFileSync('src/web/dojo/style.css', 'utf8');
assert.ok(html.indexOf('/miniapp/dojo/motion.js') < html.indexOf('/miniapp/dojo/style.css'));
assert.match(css, /html\.motion-reduced \.boot-art/);
assert.doesNotMatch(css, /html\.motion-reduced \.magic-trail/);
const header = html.split('<header class="top">')[1].split('</header>')[0];
assert.ok(header.includes('class="lang-switch"') && header.includes('id="motion-setting"'));
assert.equal((html.match(/id="motion-setting"/g) || []).length, 1);
assert.match(css, /\.motion-setting\[aria-pressed="true"\]/);
assert.match(css, /\.motion-setting\[aria-pressed="false"\]/);

function setup(saved, osReduced, storageBlocked = false) {
  let stored = saved, seeded = 0, events = 0;
  const classes = new Set();
  const document = {documentElement: {classList: {toggle(name, state) {
    if (state) classes.add(name); else classes.delete(name);
  }}}};
  const localStorage = {getItem() { if (storageBlocked) throw Error('blocked'); return stored; },
    setItem(_key, value) { if (storageBlocked) throw Error('blocked'); stored = value; }};
  const query = {matches: osReduced};
  const window = {matchMedia: () => query, dispatchEvent() { events++; }};
  const button = {textContent: '', setAttribute(name, value) { this[name] = value; }};
  const context = {document, localStorage, window, Event: class Event {},
    $: () => button, t: s => s, seedAmbient: () => { seeded++; }};
  vm.createContext(context);
  vm.runInContext(bootstrap, context);
  const start = source.indexOf('  const motionQuery = window.matchMedia');
  const end = source.indexOf('  const MATRIX_GLYPHS', start);
  assert.ok(start >= 0 && end > start);
  vm.runInContext(source.slice(start, end) + '\nthis.motion = {motionReduced, changeMotionPreference, paintMotionControl};', context);
  return {classes, button, query, motion: context.motion, get stored() { return stored; },
    get seeded() { return seeded; }, get events() { return events; }};
}
for (const osReduced of [false, true]) {
  const h = setup(null, osReduced);
  assert.ok(!h.classes.has('motion-reduced'), 'new installs animate from the loading screen');
  assert.equal(h.motion.motionReduced(), false);
  h.motion.paintMotionControl();
  assert.equal(h.button.textContent, 'EFFECT · ON');
  assert.equal(h.button['aria-label'], 'Эффекты: включены');
  assert.equal(h.button['aria-pressed'], 'true');
  h.motion.changeMotionPreference();
  assert.equal(h.stored, 'off');
  assert.equal(h.classes.has('motion-reduced'), true);
  assert.equal(h.motion.motionReduced(), true);
  assert.equal(h.button.textContent, 'EFFECT · OFF');
  assert.equal(h.button['aria-label'], 'Эффекты: выключены');
  assert.equal(h.button['aria-pressed'], 'false');
  h.motion.changeMotionPreference();
  assert.equal(h.stored, 'full');
  assert.equal(h.motion.motionReduced(), false);
  assert.ok(h.seeded >= 1 && h.events === 2);
}
const remembered = setup('auto', true);
assert.equal(remembered.classes.has('motion-reduced'), true, 'preserve explicit system choice before first paint');
assert.equal(remembered.motion.motionReduced(), true);
remembered.query.matches = false;
assert.equal(remembered.motion.motionReduced(), false, 'system choice follows preference changes');
assert.equal(setup('full', true).classes.has('motion-reduced'), false);
assert.equal(setup('off', false).classes.has('motion-reduced'), true, 'saved off disables motion even without OS reduced motion');
assert.equal(setup(null, true, true).classes.has('motion-reduced'), false, 'blocked storage still animates');
console.log('Motion: initial boot preference, OS setting, saved choice and control passed.');
