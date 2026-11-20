// Check that the client tracks the 100-unit threshold between server refreshes.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const source = fs.readFileSync('src/web/dojo/miner.js', 'utf8');
const start = source.indexOf('  function energyMax()');
const end = source.indexOf('  function percent()', start);
assert.ok(start >= 0 && end > start);
let now = 1000000;
const model = {phase: 'mining', energy: 100, circle_energy: 100.5, energy_max: 100,
  energy_per_hour: 100, server_now: 1000};
const get = new Function('model', 'initData', 'serverNow', source.slice(start, end) +
  '\nreturn {energyMax, circleEnergyValue};');
const energy = get(model, () => 'signed', () => now);
assert.ok(energy.circleEnergyValue() >= 100);
now += 18000;
assert.equal(energy.circleEnergyValue(), 100);
now += 1;
assert.ok(energy.circleEnergyValue() < 100, 'crossing 100-unit must work without a refresh');
model.circle_energy = 40;
model.energy_max = 200;
assert.ok(energy.circleEnergyValue() < 100);
model.circle_energy = 120;
assert.ok(energy.circleEnergyValue() > 100);
console.log('Circle eligibility: precise 100-unit cap and interpolation passed.');
