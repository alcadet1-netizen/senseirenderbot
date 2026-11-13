import asyncio
import copy
import time
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch
from html.parser import HTMLParser

import pytest
from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest
from tests.campaign_support import FakeDB
from src.core.constants import BOSSES
from src.services.boss_service import BossService
from src.services.boss_settlement_service import settle_boss
from src.services.boss_runtime import refresh_boss
from src.bot.presenters.boss_presenter import BossPresenter


async def fixture(kind='loss'):
    db=FakeDB();mongo=NS(database=db)
    state=dict(_id='boss_state',battle_id='battle',boss_id=next(iter(BOSSES)),start_time=1,
        deadline=2, hp=0 if kind=='win' else 100,max_hp=100,is_dead=kind=='win',
        is_expired=False,hits={'7':{'name':'<A&>','dmg':60},'8':{'name':'B','dmg':40}},
        chat_id=-100,message_id=20,has_photo=False)
    if kind=='win': state['settlement_kind']='win'
    await db.boss_state.insert_one(state)
    for uid in (7,8): await db.users.insert_one(dict(id=uid,coins=1000))
    await db.bank.insert_one(dict(_id='single',coins=1000))
    service=BossService(mongo)
    container=NS(mongo_client=mongo,boss_service=service)
    return db,container


@pytest.mark.asyncio
@pytest.mark.parametrize('kind',['win','loss'])
async def test_concurrent_settlement_is_once_and_conserves_coins(kind):
    db,c=await fixture(kind)
    await asyncio.gather(*(settle_boss(c.mongo_client) for _ in range(4)))
    rows=await db.users.find({}).to_list(None)
    bank=await db.bank.find_one({'_id':'single'})
    assert sum(u['coins'] for u in rows)+bank['coins']==pytest.approx(3000)
    assert len(db.transactions.docs)==2
    state=await c.boss_service.get_state()
    assert state['settlement']['kind']==kind
    if kind=='loss':
        assert state['is_expired'] and bank['coins']==1200
    else:
        assert bank['coins']==1000-BOSSES[state['boss_id']]['coins_reward']


@pytest.mark.asyncio
async def test_failed_transaction_rolls_back_and_can_retry():
    db,c=await fixture('loss')
    insert=db.transactions.insert_one
    with patch.object(db.transactions,'insert_one',new=AsyncMock(side_effect=RuntimeError('offline'))):
        with pytest.raises(RuntimeError): await settle_boss(c.mongo_client)
    assert (await db.users.find_one({'id':7}))['coins']==1000
    assert (await db.bank.find_one({'_id':'single'}))['coins']==1000
    assert 'settlement' not in await c.boss_service.get_state()
    await settle_boss(c.mongo_client)
    assert (await db.users.find_one({'id':7}))['coins']==900


@pytest.mark.asyncio
async def test_restarted_worker_closes_expired_card_once_without_new_message():
    db,c=await fixture()
    bot=NS(edit_message_text=AsyncMock(),edit_message_caption=AsyncMock())
    await refresh_boss(bot,c)
    await refresh_boss(bot,c)
    bot.edit_message_text.assert_awaited_once()
    assert bot.edit_message_text.call_args.kwargs['reply_markup'] is None
    assert 'Штраф переведён' in bot.edit_message_text.call_args.kwargs['text']
    assert len(db.transactions.docs)==2


@pytest.mark.asyncio
async def test_rate_limit_defers_refresh_without_repeating_money():
    db,c=await fixture()
    bot=NS(edit_message_text=AsyncMock(side_effect=TelegramRetryAfter(method='editMessageText',message='flood',retry_after=30)))
    await refresh_boss(bot,c)
    await refresh_boss(bot,c)
    bot.edit_message_text.assert_awaited_once()
    assert len(db.transactions.docs)==2
    assert not (await c.boss_service.get_state()).get('card_synced')


@pytest.mark.asyncio
async def test_deleted_card_is_not_replaced_with_orphan_messages():
    db,c=await fixture()
    bot=NS(edit_message_text=AsyncMock(side_effect=TelegramBadRequest(method='editMessageText',message='message to edit not found')))
    await refresh_boss(bot,c)
    await refresh_boss(bot,c)
    bot.edit_message_text.assert_awaited_once()
    assert (await c.boss_service.get_state())['card_missing']


@pytest.mark.asyncio
async def test_stale_combat_save_cannot_reset_gram_reservations():
    db,c=await fixture()
    stale=await c.boss_service.get_state();stale['gram_reserved']=0
    await db.boss_state.update_one({'_id':'boss_state'},{'$set':{'gram_reserved':.5}})
    await c.boss_service._save_boss_state_doc(stale)
    assert (await c.boss_service.get_state())['gram_reserved']==.5


@pytest.mark.parametrize('boss_id', list(BOSSES))
def test_compact_caption_is_safe_and_shows_real_shield(boss_id):
    state=dict(boss_id=boss_id,hp=450,max_hp=1000,shield=20,max_shield=100,
               deadline=time.time()+3600,hits={str(i):{'name':'<>&'*20,'dmg':1234567} for i in range(8)})
    text=BossPresenter.render_boss_caption(state)
    assert '<pre>' not in text and '20 / 100' in text and 'UTC' in text
    class Parser(HTMLParser):
        def __init__(self): super().__init__();self.parts=[]
        def handle_data(self,data): self.parts.append(data)
    parser=Parser();parser.feed(text)
    assert len(''.join(parser.parts)) <= 1024


@pytest.mark.asyncio
async def test_win_with_empty_bank_cannot_emit_coins():
    db,c=await fixture('win')
    await db.bank.update_one({'_id':'single'},{'$set':{'coins':0}})
    await settle_boss(c.mongo_client)
    assert (await db.users.find_one({'id':7}))['coins']==1000
    assert (await c.boss_service.get_state())['settlement']['total']==0


@pytest.mark.asyncio
async def test_admin_stop_or_legacy_terminal_does_not_charge_penalty():
    db,c=await fixture()
    await db.boss_state.update_one({'_id':'boss_state'},{'$set':{'is_dead':True,'stopped_by_admin':True}})
    await settle_boss(c.mongo_client)
    assert len(db.transactions.docs)==0
    assert (await db.users.find_one({'id':7}))['coins']==1000


@pytest.mark.asyncio
async def test_unchanged_active_card_does_not_spam_telegram():
    db,c=await fixture()
    await db.boss_state.update_one({'_id':'boss_state'},{'$set':{'deadline':time.time()+3600}})
    bot=NS(edit_message_text=AsyncMock())
    await refresh_boss(bot,c,force=True)
    await refresh_boss(bot,c,force=True)
    bot.edit_message_text.assert_awaited_once()
    assert len(db.transactions.docs)==0


@pytest.mark.asyncio
async def test_newer_database_hp_not_stale_caller_snapshot_is_published():
    db,c=await fixture()
    await db.boss_state.update_one({'_id':'boss_state'},{'$set':{'deadline':time.time()+3600,'hp':5}})
    bot=NS(edit_message_text=AsyncMock())
    await refresh_boss(bot,c,force=True)
    assert '5 / 100 HP' in bot.edit_message_text.call_args.kwargs['text']


@pytest.mark.asyncio
async def test_legacy_expired_state_is_not_charged_again():
    db,c=await fixture()
    await db.boss_state.update_one({'_id':'boss_state'},{'$set':{'is_expired':True}})
    await settle_boss(c.mongo_client)
    assert len(db.transactions.docs)==0
