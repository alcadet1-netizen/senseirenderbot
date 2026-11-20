// Exercise the same collect/refresh handlers used by the Mini App without Telegram.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const js = fs.readFileSync('src/web/dojo/miner.js', 'utf8');
const calls = [];
let reads = 0;
const context = vm.createContext({
  initData: () => 'signed', render() {}, showToast() {},
  async api(action) {
    calls.push(action);
    if (action === 'collect') throw Error('response lost after commit');
    if (++reads === 1) throw Error('offline');
    return {phase: 'ready', balance: 118};
  },
});
vm.runInContext(`let pending = null, verifyCollection = false, stateRevision = 0;
  let needsEntry = false, sessionEnded = false;
  let model = {phase:'ready_to_collect', balance:100};
  function apply(state) { model = state; }
  ${js.slice(js.indexOf('  async function refresh('), js.indexOf('  function celebrate('))}
  this.inspect = () => ({verifyCollection, phase:model.phase, balance:model.balance});`, context);
(async () => {
  await Promise.all([context.collect(), context.collect()]);
  assert.equal(context.inspect().verifyCollection, true);
  await context.refresh();
  assert.equal(context.inspect().verifyCollection, false);
  assert.equal(context.inspect().phase, 'ready');
  assert.equal(context.inspect().balance, 118);
  assert.deepEqual(calls, ['collect', 'state', 'state']);
  console.log('Lost receipt: double tap sends one collect; retry reads server state.');
})().catch(error => { console.error(error); process.exitCode = 1; });
