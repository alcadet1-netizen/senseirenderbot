const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('src/web/dojo/miner.js', 'utf8');
const css = fs.readFileSync('src/web/dojo/style.css', 'utf8');
const start = source.indexOf('  function paintEnergy(value)');
const end = source.indexOf('  function paintMeter()', start);
assert.ok(start > 0 && end > start);
const nodes = {};
for (const name of ['energy', 'energy-bar', 'energy-track', 'energy-card']) {
  nodes[name] = {style: {}, attrs: {}, classList: {toggle() {}},
    setAttribute(key, value) { this.attrs[key] = value; }};
}
const model = {phase: 'mining', circle_available: false};
const context = {model, energyMax: () => 100, initData: () => 'signed',
  $: id => nodes[id], t: x => x, Math, Number, String};
vm.createContext(context);
vm.runInContext(source.slice(start, end) + '\nthis.paintEnergy = paintEnergy;', context);
context.paintEnergy(99.9);
const first = Number(nodes['energy-bar'].style.transform.match(/scaleX\((.*)\)/)[1]);
assert.equal(nodes.energy.textContent, '99 / 100');
context.paintEnergy(99.8);
const second = Number(nodes['energy-bar'].style.transform.match(/scaleX\((.*)\)/)[1]);
assert.ok(second < first, 'bar drains even while the displayed integer is unchanged');
assert.equal(nodes.energy.textContent, '99 / 100');
context.paintEnergy(200);
assert.equal(nodes['energy-bar'].style.transform, 'scaleX(1)');
assert.equal(nodes.energy.textContent, '200 / 100');
assert.equal(nodes['energy-track'].attrs['aria-valuenow'], '100');
context.paintEnergy(-1);
assert.equal(nodes['energy-bar'].style.transform, 'scaleX(0)');
assert.equal(nodes['energy-card'].attrs['aria-disabled'], 'false');
model.circle_available = true;
context.paintEnergy(0.2);
assert.equal(nodes.energy.textContent, '1 / 100');
assert.equal(nodes['energy-card'].attrs['aria-disabled'], 'true');
assert.match(css, /\.phase-mining #energy-bar\s*\{\s*transition:\s*transform 0\.3s linear/);
assert.match(css, /html\.motion-reduced #energy-bar\s*\{\s*transition:\s*none/);
assert.match(css, /\.energy-track,\s*\.mine-track\s*\{\s*height:\s*3px/);
console.log('Energy meter: fractional drain, cap, empty/refill and reduced motion passed.');
