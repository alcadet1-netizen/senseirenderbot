from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from pymongo.errors import DuplicateKeyError
from src.bot.handlers.boss_commands import sensei_boss, render_boss_caption
from src.services.boss_reward_service import award_boss_gram
from src.core.constants import BOSSES


@pytest.mark.asyncio
@pytest.mark.parametrize('status,allowed',[('administrator',True),('creator',True),('member',False)])
async def test_chat_admin_launches_random_boss_for_one_hour(status,allowed):
    message=NS(chat=NS(id=-100,type='supergroup'),from_user=NS(id=7),answer=AsyncMock(),
        bot=NS(get_chat_member=AsyncMock(return_value=NS(status=status))))
    container=NS(boss_service=NS())
    with patch('src.bot.handlers.boss_commands.launch_boss',new_callable=AsyncMock) as launch:
        await sensei_boss(message,NS(args='1'),container,NS())
    if allowed:
        launch.assert_awaited_once()
        assert launch.call_args.args[1]==-100 and launch.call_args.args[2] in BOSSES
        assert launch.call_args.kwargs['duration']==1
    else: launch.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('args',['nan','inf','0','-1','25','oops'])
async def test_bad_duration_does_not_start(args):
    message=NS(chat=NS(id=-100,type='supergroup'),from_user=NS(id=7),answer=AsyncMock(),
        bot=NS(get_chat_member=AsyncMock(return_value=NS(status='administrator'))))
    with patch('src.bot.handlers.boss_commands.launch_boss',new_callable=AsyncMock) as launch:
        await sensei_boss(message,NS(args=args),NS(boss_service=NS()),NS())
    launch.assert_not_awaited()


def payout_fixture(reserved=1,confirmed=True,duplicate=False):
    receipts=NS(insert_one=AsyncMock(side_effect=DuplicateKeyError('duplicate') if duplicate else None),update_one=AsyncMock())
    db=NS(boss_xrocket_rewards=receipts,boss_state=NS(update_one=AsyncMock(return_value=NS(modified_count=reserved))))
    c=NS(mongo_client=NS(database=db),boss_service=NS(get_reward_settings=AsyncMock(return_value={'pool_limit':1})),
         xrocket_service=NS(transfer=AsyncMock(return_value=confirmed)))
    return c,db,receipts


@pytest.mark.asyncio
@pytest.mark.parametrize('reserved,confirmed,expected',[(1,True,'confirmed'),(1,False,'needs_review'),(0,True,'pool_exhausted')])
async def test_durable_award_reserves_before_external_transfer(reserved,confirmed,expected):
    c,db,r=payout_fixture(reserved,confirmed)
    result=await award_boss_gram(c,{'start_time':100,'battle_id':'battle'},7,.01,'cb:1')
    assert result==expected
    key=r.insert_one.call_args.args[0]['_id']
    assert len(key)==20
    if reserved:
        c.xrocket_service.transfer.assert_awaited_once_with(7,'GRAM',.01,transfer_id=key,raise_rejection=True)
    else: c.xrocket_service.transfer.assert_not_awaited()
    assert r.update_one.call_args.args[1]['$set']['status']==expected
    assert db.boss_state.update_one.call_args.args[1]=={'$inc':{'gram_reserved':.01}}


@pytest.mark.asyncio
async def test_duplicate_reward_never_attempts_transfer_again():
    c,db,r=payout_fixture(duplicate=True)
    assert await award_boss_gram(c,{'start_time':100},7,.01,'cb:1')=='duplicate'
    db.boss_state.update_one.assert_not_awaited()
    c.xrocket_service.transfer.assert_not_awaited()


def test_boss_caption_is_short_and_states_bonus_is_not_guaranteed():
    bid=next(iter(BOSSES));b=BOSSES[bid]
    text=render_boss_caption(dict(boss_id=bid,hp=b['hp'],max_hp=b['hp'],hits={},battle_log=[]))
    assert len(text)<1024 and 'не гарантия' in text and 'уровень 5+' in text


@pytest.mark.asyncio
async def test_concurrent_start_rejection_does_not_overwrite_active_boss():
    from src.services.boss_service import BossService
    db=NS(boss_state=NS(update_one=AsyncMock(side_effect=DuplicateKeyError('active'))),
          boss_ult_cooldowns=NS(),boss_settings=NS())
    service=BossService(NS(database=db))
    with pytest.raises(ValueError,match='Бой уже'):
        await service.start_boss(next(iter(BOSSES)),duration_hours=1)
    query,update=db.boss_state.update_one.call_args.args
    assert query['_id']=='boss_state' and '$or' in query
    assert update['$set']['deadline']-update['$set']['start_time']==pytest.approx(3600,abs=.1)


@pytest.mark.asyncio
async def test_transfer_exception_retains_reserved_budget_and_marks_review():
    c,db,r=payout_fixture()
    c.xrocket_service.transfer.side_effect=TimeoutError
    assert await award_boss_gram(c,{'start_time':100},7,.01,'cb:1')=='needs_review'
    assert db.boss_state.update_one.await_count==1
    assert r.update_one.call_args.args[1]['$set']['status']=='needs_review'


@pytest.mark.asyncio
@pytest.mark.parametrize('payload,confirmed',[({'success':True},True),({'success':False},False),({},False),([],False)])
async def test_xrocket_only_explicit_success_confirms_award(payload,confirmed):
    from src.services.xrocket_service import XRocketService
    response=MagicMock(status=200)
    response.json=AsyncMock(return_value=payload)
    response.__aenter__=AsyncMock(return_value=response)
    response.__aexit__=AsyncMock(return_value=None)
    session=MagicMock()
    session.post.return_value=response
    session.__aenter__=AsyncMock(return_value=session)
    session.__aexit__=AsyncMock(return_value=None)
    with patch('src.services.xrocket_service.aiohttp.ClientSession',return_value=session):
        assert await XRocketService('test-key').transfer(7,'GRAM',.01,transfer_id='stable-id') is confirmed
    assert session.post.call_args.kwargs['json']['transferId']=='stable-id'


def test_names_cannot_inject_markup_in_boss_caption():
    bid=next(iter(BOSSES));b=BOSSES[bid]
    text=render_boss_caption(dict(boss_id=bid,hp=b['hp'],max_hp=b['hp'],
        hits={'7':{'name':'<b>&name','dmg':15}},battle_log=[]))
    assert '&lt;b&gt;&amp;name' in text


def test_boss_has_exactly_one_attack_button():
    from src.bot.handlers.boss_commands import get_boss_keyboard
    buttons=[b for row in get_boss_keyboard().inline_keyboard for b in row]
    assert len(buttons)==1
    assert buttons[0].text=='⚔️ Атака' and buttons[0].callback_data=='hit_boss'


@pytest.mark.asyncio
async def test_old_ult_button_only_explains_text_command():
    from src.bot.handlers.boss_commands import ult_boss
    callback=NS(answer=AsyncMock())
    with patch('src.bot.handlers.boss_commands.process_boss_attack',new_callable=AsyncMock) as attack:
        await ult_boss(callback)
    attack.assert_not_awaited()
    assert '/ulta' in callback.answer.call_args.args[0]


@pytest.mark.asyncio
async def test_text_ult_still_attacks_with_ult_flag():
    from src.bot.handlers.boss_commands import cmd_ult
    message=NS(delete=AsyncMock(),chat=NS(id=-100))
    container=NS(boss_service=NS(get_state=AsyncMock(return_value={'hp':100,'chat_id':-100})))
    with patch('src.bot.handlers.boss_commands.process_boss_attack',new_callable=AsyncMock) as attack:
        await cmd_ult(message,container)
    attack.assert_awaited_once_with(message,container,is_ult=True)


@pytest.mark.asyncio
async def test_text_ult_in_other_chat_is_not_deleted_or_processed():
    from src.bot.handlers.boss_commands import cmd_ult
    message=NS(delete=AsyncMock(),chat=NS(id=-200))
    container=NS(boss_service=NS(get_state=AsyncMock(return_value={'hp':100,'chat_id':-100})))
    with patch('src.bot.handlers.boss_commands.process_boss_attack',new_callable=AsyncMock) as attack:
        await cmd_ult(message,container)
    message.delete.assert_not_awaited()
    attack.assert_not_awaited()
