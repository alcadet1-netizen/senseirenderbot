const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('src/web/dojo/miner.js', 'utf8');
const start = source.indexOf('  function renderBank()');
const end = source.indexOf('  function paintReferralLink()', start);
assert.ok(start > 0 && end > start);
const nodes = {};
const $ = id => nodes[id] ||= {style: {}, classList: {toggle() {}}, attrs: {}, setAttribute(k, v) { this.attrs[k] = v; }};
const milestones = [25, 50, 75, 100].map(value => ({dataset: {milestone: value}, classList: {toggle(k, v) { this[k] = v; }}}));
let resolveApi;
const context = {$, document: {querySelectorAll: () => milestones}, Math, Number, String, Date,
  coin: x => String(x), coinExact: x => String(Math.round(x * 100) / 100), locale: () => 'en-US',
  t: (s, vars = {}) => s.replace(/\{(\w+)\}/g, (_, k) => vars[k]), initData: () => 'signed',
  showToast() {}, api: () => new Promise((resolve, reject) => { resolveApi = {resolve, reject}; })};
vm.createContext(context);
vm.runInContext('let bank = null, bankBusy = false, bankLoadFailed = false;\n' + source.slice(start, end) + '\nthis.renderBank = renderBank; this.loadBank = loadBank; this.setBank = b => bank = b;', context);
const data = {total_emitted: 971011837, emission_cap: 10000000000, emission_remaining: 9028988163,
  total_supply: 970615473, bank_balance: 968485634, circulation: 2129839, burned: 29978566,
  confiscated: 482064, holders: 272, snapshot_at: 1730000000};
(async () => {
  context.setBank(data); context.renderBank();
  assert.equal($('bank-warning').hidden, false);
  assert.equal($('bank-warning-title').textContent, 'Обнаружено расхождение');
  assert.match($('bank-warning-delta').textContent, /396364/);
  assert.equal($('bank-mined-label').textContent, '971011837 Coin');
  assert.equal($('bank-progress').style.width, '9.71011837%');
  assert.equal(milestones[0].classList['is-reached'], false);
  context.setBank({...data, total_emitted: 2500000000, total_supply: 2500000000}); context.renderBank();
  assert.equal($('bank-warning').hidden, true);
  assert.equal(milestones[0].classList['is-reached'], true);
  context.setBank({...data, total_emitted: 2499999999, total_supply: 2499999999}); context.renderBank();
  assert.equal(milestones[0].classList['is-reached'], false);
  context.setBank({...data, emission_cap: 100, total_emitted: 101, total_supply: 101}); context.renderBank();
  assert.equal($('bank-warning-title').textContent, 'Превышен лимит');
  const request = context.loadBank(true);
  assert.equal($('bank-refresh').disabled, true);
  assert.match($('bank-refresh-status').textContent, /Загружаем/);
  resolveApi.reject(new Error('failed')); await request;
  assert.equal($('bank-refresh').disabled, false);
  assert.match($('bank-refresh-status').textContent, /Не удалось/);
  const retry = context.loadBank(true); resolveApi.resolve(data); await retry;
  assert.match($('bank-refresh-status').textContent, /Снимок данных/);
  console.log('Bank: discrepancy, exact milestone, loading, retry and snapshot passed.');
})().catch(error => { console.error(error); process.exit(1); });
