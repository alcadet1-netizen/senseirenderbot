import asyncio
import zlib
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

import pytest
from aiogram.types import Message
from src.services.fly_service import FlyService, features
from src.widgets.fly import fly_html
from tests.campaign_support import FakeDB


def message(text='Интересно, как устроен этот новый виджет',mid=1,uid=7):
    return Message.model_validate(dict(message_id=mid,date=1,chat=dict(id=-100222,type='supergroup'),
        **{'from':dict(id=uid,is_bot=False,first_name='User')},text=text))


def fixture():
    db=FakeDB();clock=[datetime(2026,11,6,12,tzinfo=timezone.utc)]
    container=NS(mongo_client=NS(database=db),settings=NS(fly_reactions_enabled=True))
    service=FlyService(container,clock=lambda:clock[0],roll=lambda:0)
    return db,service,clock


@pytest.mark.asyncio
async def test_opt_in_required_and_no_financial_writes():
    db,s,_=fixture()
    assert await s.reserve(message()) is None
    await db.fly_settings.update_one({'_id':-100222},{'$set':{'enabled':True}},upsert=True)
    result=await s.reserve(message())
    assert result and len(result[1])<250
    assert not ({'users','bank','transactions','campaign_rewards'} & set(db.collections))
    assert await s.reserve(message()) is None


@pytest.mark.asyncio
async def test_novel_topic_question_and_chat_user_cooldowns():
    db,s,clock=fixture()
    await db.fly_settings.update_one({'_id':-100222},{'$set':{'enabled':True}},upsert=True)
    assert await s.reserve(message())
    clock[0]+=timedelta(minutes=16)
    assert await s.reserve(message('Давайте обсудим новую игру с интересной механикой',mid=2)) is None
    clock[0]+=timedelta(minutes=16)
    result=await s.reserve(message('Вернёмся к тому, как работает нейронная технология',mid=3,uid=8))
    assert result and result[1].endswith('?')


@pytest.mark.asyncio
async def test_concurrent_messages_only_one_reply_and_daily_limit():
    db,s,clock=fixture()
    await db.fly_settings.update_one({'_id':-100222},{'$set':{'enabled':True}},upsert=True)
    values=await asyncio.gather(*(s.reserve(message(mid=i,uid=i+20)) for i in range(10)))
    assert sum(x is not None for x in values)==1
    for i in range(1,8):
        clock[0]+=timedelta(minutes=16)
        assert await s.reserve(message('Интересно устроен виджет '+('а'*i),mid=20+i,uid=200+i))
    clock[0]+=timedelta(minutes=16)
    assert await s.reserve(message('Новый бот теперь работает заметно интереснее',mid=50,uid=500)) is None
    clock[0]+=timedelta(days=1)
    assert await s.reserve(message('Новый бот умеет что-нибудь интересное сегодня',mid=51,uid=501))


@pytest.mark.parametrize('text', ['/senseifly', 'Номер телефона 1234567 и новый бот', 'Оплата за игру не проходит сегодня',
    'Про смерть и про новую игру сегодня', 'Просто доброе утро всем участникам', 'https://example.com новый виджет'])
def test_sensitive_unknown_commands_and_links_silent(text):
    assert features(message(text)) is None


def test_widget_is_small_offline_native_and_honest():
    html=fly_html()
    assert len(html.encode())<=32768 and len(zlib.compress(html.encode(),9))<=4096
    assert 'TelegramWidget.ready()' in html and '<canvas' in html
    assert 'Sensei FLY LAB' in html
    assert 'Визуальная симуляция нейронной сети мухи' in html
    assert html.count('<button ')==1
    assert 'Запустить симуляцию нейронов' in html
    assert 'настоящего мозга' not in html
    assert 'id="stats"' not in html and 'id="why"' not in html
    assert 'draw(false);TelegramWidget.ready()' in html
    assert 'TelegramWidget.request' not in html and 'fetch(' not in html


@pytest.mark.asyncio
async def test_global_kill_switch():
    db,s,_=fixture();s.container.settings.fly_reactions_enabled=False
    assert await s.reserve(message()) is None
    assert not db.collections


@pytest.mark.asyncio
async def test_handler_native_widget_and_admin_setting():
    from src.bot.handlers.fly import command
    db,s,_=fixture()
    msg=NS(text='/senseifly',bot=NS(get_chat_member=AsyncMock()),chat=NS(id=7,type='private'),
        from_user=NS(id=7),answer=AsyncMock())
    with patch('src.bot.handlers.fly.send_native_widget',new=AsyncMock()) as send:
        await command(msg,s.container)
        assert send.call_args.kwargs['allow_queries'] is False
    msg.chat=NS(id=-100222,type='supergroup')
    msg.text='/senseifly on';msg.bot.get_chat_member.return_value=NS(status='member')
    await command(msg,s.container)
    assert await db.fly_settings.find_one({'_id':-100222}) is None
    msg.bot.get_chat_member.return_value=NS(status='administrator')
    await command(msg,s.container)
    assert (await db.fly_settings.find_one({'_id':-100222}))['enabled']


@pytest.mark.asyncio
async def test_middleware_strict_reply_and_ambiguous_send_not_retried():
    from src.bot.handlers.fly import FlyReactionMiddleware
    db,s,_=fixture()
    middleware=FlyReactionMiddleware(s.container)
    middleware.service=s
    event=NS(text='Интересно как устроен этот новый виджет',from_user=NS(id=7,is_bot=False),
        sender_chat=None,is_automatic_forward=False,chat=NS(id=-100222,type='supergroup'),message_id=1,
        bot=NS(),answer=AsyncMock(side_effect=TimeoutError()))
    handler=AsyncMock(return_value='handled')
    await db.fly_settings.update_one({'_id':-100222},{'$set':{'enabled':True}},upsert=True)
    with patch('src.bot.handlers.fly.group_admin_access.allowed',new=AsyncMock(return_value=True)):
        assert await middleware(handler,event,{})=='handled'
        await middleware(handler,event,{})
    event.answer.assert_awaited_once()
    assert event.answer.call_args.kwargs['reply_parameters'].allow_sending_without_reply is False
    assert (await db.fly_decisions.find_one({'_id':'-100222:1'}))['status']=='send_failed_or_unknown'


@pytest.mark.asyncio
async def test_alternating_repeats_habituate_and_recover():
    db,s,clock=fixture()
    await db.fly_settings.update_one({'_id':-100222},{'$set':{'enabled':True}},upsert=True)
    assert await s.reserve(message())
    clock[0]+=timedelta(minutes=16)
    assert await s.reserve(message('Новая игра с удивительной механикой',mid=2,uid=8))
    clock[0]+=timedelta(minutes=16)
    assert await s.reserve(message(mid=3,uid=9)) is None
    decision=await db.fly_decisions.find_one({'_id':'-100222:3'})
    assert decision['repeated'] and not decision['selected']
    clock[0]+=timedelta(hours=7)
    assert await s.reserve(message('Новая игра с удивительной механикой',mid=4,uid=10))
    assert await s.reserve(message(mid=3,uid=9)) is None  # replay stays silent after recovery


@pytest.mark.asyncio
async def test_habituation_memory_bounded():
    db,s,_=fixture()
    await db.fly_settings.update_one({'_id':-100222},{'$set':{'enabled':True}},upsert=True)
    for i in range(50):
        await s.reserve(message('Интересно устроен виджет '+str(i),mid=i,uid=i+100))
    state=await db.fly_chat_state.find_one({'_id':-100222})
    assert len(state['recent'])==32
    assert all(set(item)=={'digest','at'} for item in state['recent'])


def test_forward_hidden_link_and_unicode_normalization():
    msg=message()
    forwarded=msg.model_copy(update={'forward_origin':NS(type='user')})
    assert features(forwarded) is None
    hidden=msg.model_copy(update={'entities':[NS(type='text_link')]})
    assert features(hidden) is None
    assert features(message('Интересно как работает этот бот １２３４５６')) is None
    assert features(message('Интересно как работает этот бот ／команда')) is None


@pytest.mark.asyncio
async def test_command_reports_global_kill_switch_truthfully():
    from src.bot.handlers.fly import command
    db,s,_=fixture();s.container.settings.fly_reactions_enabled=False
    msg=NS(text='/senseifly on',bot=NS(get_chat_member=AsyncMock(return_value=NS(status='administrator'))),
        chat=NS(id=-100222,type='supergroup'),from_user=NS(id=7),answer=AsyncMock())
    await command(msg,s.container)
    assert (await db.fly_settings.find_one({'_id':-100222}))['enabled']
    assert 'Глобальный выключатель' in msg.answer.call_args.args[0]
    assert 'реплики включены' not in msg.answer.call_args.args[0]


@pytest.mark.asyncio
async def test_widget_policy_rejection_is_explained_without_retry_or_rewards(caplog):
    from src.bot.handlers.fly import command
    from src.infra.mtproto.widgets import MtprotoWidgetError
    _,s,_=fixture()
    msg=NS(text='/senseifly',bot=NS(token='123456:SECRET'),chat=NS(id=7,type='private'),
        from_user=NS(id=7),answer=AsyncMock())
    with patch('src.bot.handlers.fly.send_native_widget',new=AsyncMock(
            side_effect=MtprotoWidgetError('INPUT_MEDIA_WIDGET_NOT_ALLOWED'))) as send:
        await command(msg,s.container)
    send.assert_awaited_once()
    text=msg.answer.call_args.args[0]
    assert 'widget_policy' in text and 'Telegram отклонил' in text
    assert '/senseifly status' in text and 'Mini App' in text
    assert not any(record.exc_info for record in caplog.records)
    assert not s.db.collections


@pytest.mark.asyncio
async def test_group_lab_available_to_non_admin_and_uses_private_forward():
    from src.bot.handlers.fly import command
    _,s,_=fixture()
    msg=NS(text='/senseifly',bot=NS(get_chat_member=AsyncMock()),
        chat=NS(id=-100222,type='supergroup'),from_user=NS(id=7,is_bot=False),
        sender_chat=None,answer=AsyncMock())
    with patch('src.bot.handlers.fly.send_private_widget_to_chat',new=AsyncMock()) as send:
        await command(msg,s.container)
    assert send.call_args.args[2:4] == (7,-100222)
    msg.bot.get_chat_member.assert_not_awaited()
    msg.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_private_creation_failure_does_not_try_direct_group_send():
    from src.bot.native_widgets import send_private_widget_to_chat
    from src.infra.mtproto.widgets import MtprotoWidgetError
    _,s,_=fixture()
    bot=NS(forward_message=AsyncMock())
    with patch('src.bot.native_widgets.send_native_widget',new=AsyncMock(
            side_effect=MtprotoWidgetError('PEER_NOT_CACHED'))) as send:
        with pytest.raises(MtprotoWidgetError):
            await send_private_widget_to_chat(bot,s.container,7,-100222,'html')
    assert send.call_args.args[2]==7
    bot.forward_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_bot_api_forwards_only_created_message():
    from src.bot.native_widgets import send_private_widget_to_chat
    _,s,_=fixture()
    bot=NS(forward_message=AsyncMock())
    with patch('src.bot.native_widgets.send_native_widget',new=AsyncMock(return_value={'message_id':123})):
        await send_private_widget_to_chat(bot,s.container,7,-100222,'html')
    bot.forward_message.assert_awaited_once_with(chat_id=-100222,from_chat_id=7,
                                               message_id=123,protect_content=False)


def test_animation_with_readonly_browser_screen_and_full_timer_cycle():
    import json
    import shutil
    import subprocess
    if not shutil.which('node'):
        pytest.skip('Node required for browser-global regression')
    script=fly_html().split('<script>')[1].split('</script>')[0]
    harness=r'''
const vm=require('node:vm');let ops=0,timers=new Map(),id=0;
const ctx=new Proxy({}, {get:(o,k)=>k in o?o[k]:(...args)=>{
 if(args.some(v=>typeof v==='number'&&!Number.isFinite(v)))throw Error('nonfinite');ops++;
},set:(o,k,v)=>(o[k]=v,true)});
const button={disabled:false};const sandbox={Math,document:{getElementById:k=>k==='net'?{getContext:()=>ctx}:button},
 TelegramWidget:{ready:()=>{}},setInterval:fn=>{timers.set(++id,fn);return id;},clearInterval:k=>timers.delete(k)};
Object.defineProperty(sandbox,'screen',{value:{width:300},writable:false});
vm.createContext(sandbox);vm.runInContext(INPUT,sandbox);
if(timers.size!==0||ops<600)throw Error('blank boot/autoplay');
button.onclick();button.onclick();if(timers.size!==1)throw Error('duplicate timers');
const first=sandbox.v.slice();const x=sandbox.projected[0].x;
for(let i=0;i<359;i++){for(const fn of [...timers.values()])fn();}
if(timers.size!==0||button.disabled||sandbox.frame!==360)throw Error('did not stop');
if(!sandbox.v.some((v,i)=>v!==first[i])||x===sandbox.projected[0].x)throw Error('static');
button.onclick();if(timers.size!==1||sandbox.frame!==1)throw Error('restart failed');
console.log(JSON.stringify({nodes:sandbox.v.length,particles:sandbox.pts.length}));
'''.replace('INPUT',json.dumps(script))
    result=subprocess.run(['node','-e',harness],capture_output=True,text=True,timeout=30,check=True)
    assert json.loads(result.stdout)=={'nodes':20000,'particles':600}


@pytest.mark.asyncio
async def test_fly_caption_is_not_hedgehog():
    from src.bot.handlers.fly import command
    _,s,_=fixture()
    msg=NS(text='/senseifly',bot=NS(),chat=NS(id=7,type='private'),answer=AsyncMock())
    with patch('src.bot.handlers.fly.send_native_widget',new=AsyncMock()) as send:
        await command(msg,s.container)
    assert send.call_args.kwargs['caption']=='Sensei FLY LAB'
