const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('src/web/dojo/miner.js', 'utf8');
const start = source.indexOf('  let chainSession = "";');
const end = source.indexOf('  function paintTimerFace', start);
assert.ok(start > 0 && end > start);
function element() {
  return {children: [], dataset: {}, style: {setProperty() {}},
    classList: {toggle() {}}, setAttribute() {},
    append(...items) { this.children.push(...items); },
    appendChild(item) { this.children.push(item); },
    prepend(item) { this.children.unshift(item); },
    replaceChildren() { this.children = []; },
    get lastElementChild() { const owner = this; return {remove() { owner.children.pop(); }}; }};
}
let now = 1000000;
const nodes = {'chain-panel': element(), 'chain-status': element(),
  'chain-feed': element(), 'chain-bpm': element()};
const context = {document: {createElement: element}, $: id => nodes[id],
  initData: () => 'signed', model: {phase:'mining', started_at:1000, finish_at:5000},
  serverNow: () => now, lang: 'ru', tg: null, t: (s, fields) =>
    fields ? s.replace('{block}', fields.block) : s, coin: n => String(n),
  Date, URLSearchParams, Math, String, Number};
vm.createContext(context);
vm.runInContext(source.slice(start, end) + '\nthis.paintChain = paintChain;', context);
context.paintChain();
const first = nodes['chain-feed'].children[0].dataset.block;
now += 8000;
context.motionReduced = () => true;
context.paintChain();
const next = nodes['chain-feed'].children[0].dataset.block;
assert.notEqual(first, next, 'block feed must update with effects off');
assert.equal(nodes['chain-feed'].children.length, 3);
console.log('Chain feed: continues updating with effects off.');
