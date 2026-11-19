const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('src/web/dojo/miner.js', 'utf8');
const start = source.indexOf('  function bankNumber(value)');
const end = source.indexOf('  function paintReferralLink()', start);
assert.ok(start > 0 && end > start);
const nodes = {};
const $ = id => nodes[id] ||= {style: {}, classList: {toggle() {}}, attrs: {}, setAttribute(k, v) { this.attrs[k] = v; }, removeAttribute(k) { delete this.attrs[k]; }};
const milestones = [25, 50, 75, 100].map(value => ({dataset: {milestone: value}, classList: {toggle(k, v) { this[k] = v; }}}));
let resolveApi;
const context = {$, document: {querySelectorAll: () => milestones}, Math, Number, String, Date,
  coin: x => String(x), coinExact: x => String(Math.round(x * 100) / 100), locale: () => 'en-US',
  t: (s, vars = {}) => s.replace(/\{(\w+)\}/g, (_, k) => vars[k]), initData: () => 'signed',
  showToast() {}, api: () => new Promise((resolve, reject) => { resolveApi = {resolve, reject}; })};
vm.createContext(context);
vm.runInContext('let bank = null, bankBusy = false, bankRefreshQueued = false, bankLoadFailed = false;\n' + source.slice(start, end) + '\nthis.renderBank = renderBank; this.loadBank = loadBank; this.setBank = b => bank = b;', context);
const data = {total_emitted: 971011837, lifetime_issued_estimate: 1000990403, emission_cap: 10000000000, emission_remaining: 8999009597,
  total_supply: 970615473, bank_balance: 968485634, circulation: 2129839, burned: 29978566,
  confiscated: 482064, holders: 272, snapshot_at: 1730000000};
(async () => {
  context.setBank(data); context.renderBank();
  assert.equal($('bank-warning').hidden, false);
  assert.equal($('bank-warning-title').textContent, 'Обнаружено расхождение');
  assert.match($('bank-warning-delta').textContent, /396364/);
  assert.equal($('bank-mined-label').textContent, '1000990403 Coin');
  assert.equal($('bank-current-emission').textContent, '971011837 Coin');
  assert.equal($('bank-progress').style.width, '10.00990403%');
  assert.equal(milestones[0].classList['is-reached'], false);
  context.setBank({...data, lifetime_issued_estimate: 2500000000, total_emitted: 2500000000, total_supply: 2500000000}); context.renderBank();
  assert.equal($('bank-warning').hidden, true);
  assert.equal(milestones[0].classList['is-reached'], true);
  context.setBank({...data, lifetime_issued_estimate: 2499999999, total_emitted: 2499999999, total_supply: 2499999999}); context.renderBank();
  assert.equal(milestones[0].classList['is-reached'], false);
  context.setBank({...data, emission_cap: 100, total_emitted: 101, total_supply: 101}); context.renderBank();
  assert.equal($('bank-warning-title').textContent, 'Превышен лимит');
  context.setBank({...data, total_emitted: null, lifetime_issued_estimate: null, emission_cap: null, total_supply: null,
    emission_remaining: null, holders: null, burned: null}); context.renderBank();
  assert.equal($('bank-mined-label').textContent, '—');
  assert.equal($('bank-supply').textContent, '—');
  assert.equal($('bank-holders').textContent, '—');
  assert.equal($('bank-progress-percent').textContent, '—');
  assert.equal($('bank-progress-track').attrs['aria-valuetext'], 'Данные недоступны');
  assert.equal($('bank-progress-track').attrs['aria-valuenow'], undefined);
  assert.equal($('bank-warning').hidden, true);
  const request = context.loadBank(true);
  assert.equal($('bank-refresh').disabled, true);
  assert.match($('bank-refresh-status').textContent, /Загружаем/);
  resolveApi.reject(new Error('failed')); await request;
  assert.equal($('bank-refresh').disabled, false);
  assert.match($('bank-refresh-status').textContent, /Не удалось/);
  const retry = context.loadBank(true); resolveApi.resolve(data); await retry;
  assert.match($('bank-refresh-status').textContent, /Снимок данных/);
  const old = context.loadBank(true);
  const oldApi = resolveApi;
  await context.loadBank(true); // A newer request arrives while the first is in flight.
  oldApi.resolve(data); await old;
  assert.notEqual(resolveApi, oldApi, 'a forced refresh is retried after the in-flight snapshot');
  assert.equal($('bank-refresh').disabled, true);
  resolveApi.resolve({...data, total_emitted: 42, lifetime_issued_estimate: 42, total_supply: 42});
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.equal($('bank-mined-label').textContent, '42 Coin');
  assert.equal($('bank-refresh').disabled, false);
  console.log('Bank: actual values, missing data, discrepancy, refresh and snapshot passed.');
})().catch(error => { console.error(error); process.exit(1); });
