// Focused event/render test; no browser or network required.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const source = fs.readFileSync('src/web/dojo/miner.js', 'utf8');
const start = source.indexOf('  function setupMagicTrail() {');
const end = source.indexOf('\n  let ambientSeeded', start);
assert.ok(start >= 0 && end > start);

function harness(pointerEvents = true) {
  const stageEvents = {}, windowEvents = {}, frames = new Map(), clears = [];
  let frameId = 0, ids = 0, rectReads = 0, strokes = 0, apiCalls = 0, resizes = 0;
  let appWidth = 400, forced = false, circleEnergy = 0;
  const ctx = {setTransform() {}, clearRect(...rect) { clears.push(rect); }, save() {}, restore() {}, beginPath() {},
    moveTo() {}, lineTo() {}, closePath() {}, arc() {}, fill() {}, fillRect() {}, drawImage() {},
    stroke() { strokes++; }, createRadialGradient() { return {addColorStop() {}}; }};
  const canvas = {_width: 0, _height: 0, getContext() { return ctx; },
    get width() { return this._width; }, set width(v) { resizes++; this._width = v; },
    get height() { return this._height; }, set height(v) { resizes++; this._height = v; }};
  const stageEl = {addEventListener(name, fn) { stageEvents[name] = fn; }, setPointerCapture() {}};
  const orb = {getBoundingClientRect() { rectReads++; return {left: 100, top: 100, width: 100, height: 100}; }};
  const app = {classList: {contains() { return true; }}, getBoundingClientRect() { rectReads++; return {left: 0, top: 0, width: appWidth, height: 800}; }};
  const motionQuery = {matches: false, addEventListener() {}};
  const document = {hidden: false, querySelectorAll() { return []; }, addEventListener() {},
    createElement() { return {width: 0, height: 0, getContext() { return ctx; }}; }};
  const window = {devicePixelRatio: 3, addEventListener(name, fn) { windowEvents[name] = fn; }};
  if (pointerEvents) window.PointerEvent = function PointerEvent() {};
  const requestAnimationFrame = fn => { frames.set(++frameId, fn); return frameId; };
  const cancelAnimationFrame = id => frames.delete(id);
  const crypto = {randomUUID() { return `circle-${++ids}`; }};
  const model = {phase: 'mining', circle_available: true, started_at: 1000, server_now: 1000};
  const api = () => { apiCalls++; return new Promise(() => {}); };
  const fn = new Function('$', 'stageEl', 'app', 'document', 'window', 'motionQuery', 'motionReduced',
    'requestAnimationFrame', 'cancelAnimationFrame', 'performance', 'crypto', 'api', 'seedAmbient',
    'model', 'activeTab', 'initData', 'energyValue', 'circleEnergyValue', 'energyMax', 'rnd', 'showToast', 'apply', 'tick', 'coin', 'pending',
    source.slice(start, end) + '\nsetupMagicTrail();');
  fn(id => id === 'magic-trail' ? canvas : id === 'orb' ? orb : {textContent: ''}, stageEl, app, document, window,
    motionQuery, () => motionQuery.matches && !forced, requestAnimationFrame, cancelAnimationFrame, {now: () => 100}, crypto, api, () => {},
    model, 'mining', () => 'signed', () => 0, () => circleEnergy, () => 100, (a, b) => (a + b) / 2, () => {}, () => {}, () => {}, String, null);
  return {stageEvents, windowEvents, frames, canvas, motionQuery, clears,
    get ids() { return ids; }, get rectReads() { return rectReads; }, get strokes() { return strokes; },
    get apiCalls() { return apiCalls; }, get resizes() { return resizes; }, setWidth(v) { appWidth = v; }, forceMotion(v) { forced = v; }, setEnergy(v) { circleEnergy = v; }};
}
const target = {closest() { return null; }};
function points(turns) {
  const result = [];
  const count = 32 * Math.abs(turns);
  for (let i = 1; i <= count; i++) {
    const angle = Math.sign(turns) * 2 * Math.PI * i / 32;
    const radius = 70 + 10 * Math.sin(angle * 3);
    result.push({clientX: 150 + radius * Math.cos(angle), clientY: 150 + radius * Math.sin(angle)});
  }
  return result;
}
const h = harness();
assert.equal(h.canvas.width, 800);
h.stageEvents.pointerdown({pointerId: 1, pointerType: 'touch', target, clientX: 220, clientY: 150});
const before = h.rectReads;
h.windowEvents.pointermove({pointerId: 1, getCoalescedEvents: () => points(2)});
assert.equal(h.ids, 2, 'both fast uneven circles must be counted');
assert.equal(h.apiCalls, 1, 'requests remain serialized');
assert.equal(h.rectReads, before, 'coalesced samples must not trigger layout reads');
const draw = [...h.frames.values()][0]; draw(150);
assert.ok(h.strokes > 0 && h.strokes <= 18, `unexpected stroke count: ${h.strokes}`);
[...h.frames.values()].at(-1)(200);
assert.ok(h.clears.some(([, , w, height]) => w > 0 && height > 0 && w < 400 && height < 800));
const oldResizes = h.resizes;
h.setWidth(420); h.windowEvents.resize(); h.windowEvents.resize();
assert.equal(h.resizes, oldResizes, 'viewport changes must not clear a canvas during a gesture');
h.windowEvents.pointerup({pointerId: 1, clientX: 220, clientY: 150});
assert.equal(h.canvas.width, 840, 'deferred resize is applied after release');
const afterResize = h.resizes; h.windowEvents.resize();
assert.equal(h.resizes, afterResize, 'unchanged size must not clear the canvas');
h.motionQuery.matches = true;
h.stageEvents.pointerdown({pointerId: 2, pointerType: 'touch', target, clientX: 220, clientY: 150});
h.windowEvents.pointermove({pointerId: 2, getCoalescedEvents: () => points(-1)});
h.windowEvents.pointerup({pointerId: 2, clientX: 220, clientY: 150});
assert.equal(h.ids, 3, 'reduced motion must still count a reverse orbit');
// Explicit opt-in re-enables the visible trail even when the OS reduces motion.
h.forceMotion(true);
const previousStrokes = h.strokes;
h.stageEvents.pointerdown({pointerId: 3, pointerType: 'touch', target, clientX: 220, clientY: 150});
h.windowEvents.pointermove({pointerId: 3, clientX: 225, clientY: 165, getCoalescedEvents() { throw Error('unsupported'); }});
for (const callback of [...h.frames.values()]) callback(150);
assert.ok(h.strokes > previousStrokes, 'manual motion opt-in and coalesced-event fallback must draw');
h.windowEvents.pointerup({pointerId: 3, clientX: 225, clientY: 165});
// A normal interactive control must remain clickable rather than starting a trail.
const controls = harness(false);
let controlPrevented = false;
controls.stageEvents.touchstart({target: {closest: () => ({disabled: false})}, cancelable: true,
  preventDefault() { controlPrevented = true; }, changedTouches: [{identifier: 1, clientX: 200, clientY: 150}]});
assert.equal(controlPrevented, false, 'touch fallback must not hijack active controls');
assert.equal(controls.frames.size, 0);
// A WebView without Pointer Events must still draw and recognize circles.
const legacy = harness(false);
let prevented = 0;
const touchEvent = (x, y) => ({target, cancelable: true, preventDefault() { prevented++; },
  changedTouches: [{identifier: 9, clientX: x, clientY: y}]});
legacy.stageEvents.touchstart(touchEvent(220, 150));
for (const p of points(1)) legacy.windowEvents.touchmove(touchEvent(p.clientX, p.clientY));
legacy.windowEvents.touchend(touchEvent(220, 150));
assert.equal(legacy.ids, 1, 'touch fallback must count an orbit');
assert.ok(prevented > 0 && legacy.frames.size > 0, 'touch fallback must draw and suppress page scrolling');
console.log('Trail: pointer, touch fallback, fast circles, resize and batched drawing passed.');

// The visual trail remains active even when other motion effects are disabled.
const disabled = harness();
disabled.motionQuery.matches = true;
disabled.stageEvents.pointerdown({pointerId: 41, pointerType: 'touch', target, clientX: 220, clientY: 150});
disabled.windowEvents.pointermove({pointerId: 41, getCoalescedEvents: () => points(1)});
for (const callback of [...disabled.frames.values()]) callback(150);
assert.ok(disabled.strokes > 0, 'trail must remain visible when effects are off');
assert.equal(disabled.ids, 1, 'circles still work with effects off');
disabled.windowEvents.pointerup({pointerId: 41, clientX: 220, clientY: 150});

for (const [energy, expected] of [[120, 0], [100, 0], [99.5, 1], [1, 1], [0, 1]]) {
  const current = harness(); current.setEnergy(energy);
  current.stageEvents.pointerdown({pointerId: 1, pointerType: 'touch', target, clientX: 220, clientY: 150});
  current.windowEvents.pointermove({pointerId: 1, getCoalescedEvents: () => points(1)});
  current.windowEvents.pointerup({pointerId: 1, clientX: 220, clientY: 150});
  assert.equal(current.ids, expected, `circle eligibility at ${energy} energy`);
}
