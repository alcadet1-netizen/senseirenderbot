// Focused event/render test; no browser or network required.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const source = fs.readFileSync('src/web/dojo/miner.js', 'utf8');
const start = source.indexOf('  function setupMagicTrail() {');
const end = source.indexOf('\n  function seedAmbient()', start);
assert.ok(start >= 0 && end > start);
const handlers = {};
const frames = new Map();
let frameId = 0, ids = 0, rectReads = 0, strokes = 0, apiCalls = 0;
const clears = [];
const ctx = {
  setTransform() {}, clearRect(...rect) { clears.push(rect); }, save() {}, restore() {}, beginPath() {},
  moveTo() {}, lineTo() {}, closePath() {}, arc() {}, fill() {}, fillRect() {},
  drawImage() {}, stroke() { strokes++; },
  createRadialGradient() { return {addColorStop() {}}; },
};
const canvas = {width: 0, height: 0, getContext() { return ctx; }};
const stageEl = {addEventListener(name, fn) { handlers[name] = fn; }, setPointerCapture() {}};
const orb = {getBoundingClientRect() { rectReads++; return {left: 100, top: 100, width: 100, height: 100}; }};
const app = {classList: {contains() { return true; }}, getBoundingClientRect() { rectReads++; return {left: 0, top: 0, width: 400, height: 800}; }};
const motionQuery = {matches: false, addEventListener() {}};
const document = {
  hidden: false, querySelectorAll() { return []; }, addEventListener() {},
  createElement() { return {width: 0, height: 0, getContext() { return ctx; }}; },
};
const window = {devicePixelRatio: 3, addEventListener() {}};
const requestAnimationFrame = fn => { frames.set(++frameId, fn); return frameId; };
const cancelAnimationFrame = id => frames.delete(id);
const crypto = {randomUUID() { return `circle-${++ids}`; }};
const model = {phase: 'mining', circle_available: true, started_at: 1000, server_now: 1000};
const api = () => { apiCalls++; return new Promise(() => {}); };
const fn = new Function('$', 'stageEl', 'app', 'document', 'window', 'motionQuery',
  'requestAnimationFrame', 'cancelAnimationFrame', 'performance', 'crypto', 'api',
  'model', 'activeTab', 'initData', 'energyValue', 'rnd', 'showToast', 'apply', 'tick', 'coin', 'pending',
  source.slice(start, end) + '\nsetupMagicTrail();');
fn(id => id === 'magic-trail' ? canvas : id === 'orb' ? orb : {textContent: ''}, stageEl, app, document, window,
  motionQuery, requestAnimationFrame, cancelAnimationFrame, {now: () => 100}, crypto, api,
  model, 'mining', () => 'signed', () => 0, (a, b) => (a + b) / 2, () => {}, () => {}, () => {}, String, null);
assert.equal(canvas.width, 800); // retained 2x-resolution cap
const target = {closest() { return null; }};
handlers.pointerdown({pointerId: 1, pointerType: 'touch', target, clientX: 220, clientY: 150});
const before = rectReads;
const points = [];
for (let i = 1; i <= 64; i++) {
  const angle = 4 * Math.PI * i / 64;
  const radius = 70 + 10 * Math.sin(angle * 3); // intentionally uneven
  points.push({clientX: 150 + radius * Math.cos(angle), clientY: 150 + radius * Math.sin(angle)});
}
handlers.pointermove({pointerId: 1, getCoalescedEvents: () => points});
assert.equal(ids, 2, 'both fast uneven circles must be counted');
assert.equal(apiCalls, 1, 'requests remain serialized');
assert.equal(rectReads, before, 'coalesced samples must not trigger layout reads');
const draw = [...frames.values()][0];
draw(150);
assert.ok(strokes > 0 && strokes <= 12, `draw uses ${strokes} strokes, expected at most 12`);
[...frames.values()].at(-1)(200);
assert.ok(clears.some(([, , w, h]) => w > 0 && h > 0 && w < 400 && h < 800), 'only the painted area should be cleared');
handlers.pointerup({pointerId: 1, clientX: 220, clientY: 150});
motionQuery.matches = true;
handlers.pointerdown({pointerId: 2, pointerType: 'touch', target, clientX: 220, clientY: 150});
const reverse = [];
for (let i = 1; i <= 32; i++) {
  const angle = -2 * Math.PI * i / 32;
  reverse.push({clientX: 150 + 70 * Math.cos(angle), clientY: 150 + 70 * Math.sin(angle)});
}
handlers.pointermove({pointerId: 2, getCoalescedEvents: () => reverse});
handlers.pointerup({pointerId: 2, clientX: 220, clientY: 150});
assert.equal(ids, 3, 'reduced motion must still count a reverse orbit');
console.log('Trail: fast coalesced circles, bounded batched drawing, cached geometry passed.');
