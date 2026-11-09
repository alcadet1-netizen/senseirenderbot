"""Execute production JS with delayed request replies, not synchronous mock taps."""
import json
import shutil
import subprocess

import pytest
from src.widgets.daily_pet import SCRIPT


def test_burst_touches_each_request_before_responses_and_out_of_order_counts():
    if not shutil.which('node'):
        pytest.skip('Node required for asynchronous native widget JS regression')
    source=SCRIPT.removeprefix('<script>').removesuffix('</script>')
    snapshot=dict(taps=0,extra_coins=0,remaining_ms=15000,state='playing')
    source=source.replace('__TOKEN__',json.dumps('owner-token')).replace('__SNAPSHOT__',json.dumps(snapshot))
    harness=r"""
const assert=require('node:assert/strict');
const vm=require('node:vm');
const elements={};
function el(id){return elements[id]??=( {textContent:'',style:{},className:''} );}
const requests=[];let now=100000;
const ctx={document:{getElementById:el,body:{}},paint:()=>{},
 Date:{now:()=>now},setInterval:()=>1,clearInterval:()=>{},
 TelegramWidget:{isForward:false,isPreview:false,ready:()=>{},openTelegramLink:()=>{},
 request:data=>new Promise((resolve,reject)=>requests.push({data,resolve,reject}))}};
vm.createContext(ctx);vm.runInContext(SOURCE,ctx);
for(let i=0;i<30;i++)ctx.touch();
assert.equal(requests.length,30,'Do not drop taps while an earlier request waits');
assert.ok(requests.every(r=>r.data==='dp:p:owner-token'));
assert.equal(ctx.frame,30,'Every touch gets immediate local feedback');
assert.equal(ctx.data.taps,0,'Do not invent confirmed taps before responses');
function reply(index,taps){requests[index].resolve({result:JSON.stringify({
 state:'playing',remaining_ms:14000,taps,extra_coins:taps*5})});}
(async()=>{
 reply(29,30);await Promise.resolve();
 reply(0,1);await Promise.resolve();
 assert.equal(ctx.data.taps,30,'Stale response must not roll back count');
 assert.equal(ctx.data.extra_coins,150);
 assert.ok(el('bonus').textContent.includes('30'));
 requests[1].reject({code:429});await Promise.resolve();
 assert.equal(ctx.data.taps,30,'Rejected request must not invent or remove rewards');
 now=116000;ctx.touch();
 assert.equal(requests.length,30,'Late touches must not renew deadline/send payout requests');
 assert.equal(ctx.ended,true);
})().catch(e=>{console.error(e);process.exitCode=1;});
""".replace('SOURCE',json.dumps(source))
    subprocess.run(['node','-e',harness],check=True,capture_output=True,text=True)


@pytest.mark.asyncio
async def test_native_burst_admitted_before_deadline_survives_database_wait():
    import asyncio
    from unittest.mock import patch
    from tests.unit.test_daily_pet import setup, issue
    db,service,_,_=setup()
    _,token=await issue(service)
    lock=service._locks[7]
    await lock.acquire()
    tasks=[]
    try:
        with patch('src.services.daily_pet_service.time.time',return_value=114.99):
            tasks=[asyncio.create_task(service.widget_action(token,7,'p',f'native:{i}')) for i in range(20)]
            # Each request reaches the lock with its trusted arrival timestamp.
            await asyncio.sleep(.05)
        with patch('src.services.daily_pet_service.time.time',return_value=116):
            lock.release()
            await asyncio.gather(*tasks)
        assert db.users.docs[7]['daily_pet']['taps']==20
        assert db.users.docs[7]['daily_pet']['deadline']==115
        with patch('src.services.daily_pet_service.time.time',return_value=116):
            await service.widget_action(token,7,'p','late')
        assert db.users.docs[7]['daily_pet']['taps']==20
    finally:
        if lock.locked(): lock.release()
        for task in tasks:
            if not task.done(): task.cancel()
