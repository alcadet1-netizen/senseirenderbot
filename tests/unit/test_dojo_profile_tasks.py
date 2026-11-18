from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest
from pymongo.errors import DuplicateKeyError

from src.services.dojo_profile_tasks import DojoProfileTasks, NAME_TASK, BIO_TASK, has_referral
from src.services.hedgehog_service import GameError


@pytest.mark.parametrize('bio,expected', [
    ('Моя ссылка https://t.me/SenseiBot?start=ref_7', True),
    ('t.me/SenseiBot?startapp=ref_7', True),
    ('https://t.me/SenseiBot?start=ref_70', False),
    ('https://t.me/OtherBot?start=ref_7', False),
    ('https://evil.t.me/SenseiBot?start=ref_7', False),
    ('https://evil.example/?next=https://t.me/SenseiBot?start=ref_7', False),
    ('https://t.me/SenseiBot?start=ref_7.fake', False),
    ('https://t.me/SenseiBot?start=ref_7@evil.example', False),
    ('https://t.me/SenseiBot?start=ref_7&start=ref_9', False),
    ('https://t.me/SenseiBot?start=ref_7#wrong', False),
    ('', False), (None, False),
])
def test_exact_own_referral_link(bio, expected):
    assert has_referral(bio, 'SenseiBot', 7) is expected


def setup(monkeypatch, *, name='SENSEI user', bio='', bank=True, existing=False):
    async def tx(mongo, callback):
        return await callback('tx')
    monkeypatch.setattr('src.services.dojo_profile_tasks.transaction', tx)
    claims = NS(find_one=AsyncMock(return_value={'_id': 'existing'} if existing else None), insert_one=AsyncMock())
    db = NS(dojo_task_claims=claims,
        users=NS(find_one=AsyncMock(return_value={'id': 7, 'coins': 100}), update_one=AsyncMock()),
        bank=NS(update_one=AsyncMock(return_value=NS(matched_count=int(bank)))),
        transactions=NS(insert_one=AsyncMock()))
    bot = NS(get_chat=AsyncMock(return_value=NS(first_name=name, last_name='', username='', bio=bio)),
             get_me=AsyncMock(return_value=NS(username='SenseiBot')))
    return DojoProfileTasks(NS(mongo_client=NS(database=db), bot=bot)), db, bot


@pytest.mark.asyncio
@pytest.mark.parametrize('slug,bio', [(NAME_TASK, ''), (BIO_TASK, 'https://t.me/SenseiBot?start=ref_7')])
async def test_reward_verifies_telegram_and_is_atomic(slug, bio, monkeypatch):
    service, db, bot = setup(monkeypatch, bio=bio)
    result = await service.claim(7, slug)
    assert result['reward_coins'] == 1000 and result['new_coins'] == 1100
    assert result['task']['claimed'] is True
    bot.get_chat.assert_awaited_once_with(7)
    for call in (db.dojo_task_claims.find_one, db.dojo_task_claims.insert_one,
                 db.users.find_one, db.users.update_one, db.bank.update_one, db.transactions.insert_one):
        assert call.await_args.kwargs['session'] == 'tx'
    assert db.dojo_task_claims.insert_one.await_args.args[0]['_id'] == f'7:{slug}:{service.day()}'
    assert db.bank.update_one.await_args.args[1] == {'$inc': {'coins': -1000}}


@pytest.mark.asyncio
async def test_fail_closed_on_missing_conditions_and_api_errors(monkeypatch):
    service, db, bot = setup(monkeypatch, name='Someone', bio='https://t.me/SenseiBot?start=ref_8')
    for slug in (NAME_TASK, BIO_TASK):
        with pytest.raises(GameError): await service.claim(7, slug)
    bot.get_chat.side_effect = TimeoutError()
    with pytest.raises(GameError, match='Не удалось проверить'):
        await service.claim(7, NAME_TASK)
    db.bank.update_one.assert_not_awaited()
    db.dojo_task_claims.insert_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_replay_duplicate_and_insufficient_bank(monkeypatch):
    service, db, _ = setup(monkeypatch, existing=True)
    with pytest.raises(GameError, match='уже получена'): await service.claim(7, NAME_TASK)
    db.bank.update_one.assert_not_awaited()
    service, db, _ = setup(monkeypatch)
    db.dojo_task_claims.insert_one.side_effect = DuplicateKeyError('duplicate')
    with pytest.raises(GameError, match='уже получена'): await service.claim(7, NAME_TASK)
    db.bank.update_one.assert_not_awaited()
    service, db, _ = setup(monkeypatch, bank=False)
    with pytest.raises(GameError, match='SenseiBank'): await service.claim(7, NAME_TASK)
    db.users.update_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_claims_are_distinct_by_task_and_utc_day(monkeypatch):
    service, db, _ = setup(monkeypatch)
    db.dojo_task_claims.find_one.side_effect = [None, {'_id': 'claimed'}]
    tasks = await service.list_tasks(7)
    assert [(t['slug'], t['claimed']) for t in tasks] == [(NAME_TASK, False), (BIO_TASK, True)]
    assert db.dojo_task_claims.find_one.await_args_list[0].args[0]['_id'] == f'7:{NAME_TASK}:{service.day()}'


@pytest.mark.asyncio
async def test_name_can_be_in_username_and_check_repeated_each_day(monkeypatch):
    service, db, bot = setup(monkeypatch, name='Player')
    bot.get_chat.return_value.username = 'pro_Sensei_1'
    monkeypatch.setattr(service, 'day', lambda: '2026-11-18')
    await service.claim(7, NAME_TASK)
    first = db.dojo_task_claims.insert_one.await_args.args[0]['_id']
    monkeypatch.setattr(service, 'day', lambda: '2026-11-19')
    bot.get_chat.return_value.username = 'ordinary'
    with pytest.raises(GameError, match='Добавь Sensei'):
        await service.claim(7, NAME_TASK)
    bot.get_chat.return_value.username = 'pro_sensei_1'
    await service.claim(7, NAME_TASK)
    second = db.dojo_task_claims.insert_one.await_args.args[0]['_id']
    assert first.endswith('2026-11-18') and second.endswith('2026-11-19')


@pytest.mark.asyncio
async def test_private_chat_unavailable_no_payment(monkeypatch):
    service, db, bot = setup(monkeypatch)
    bot.get_chat.side_effect = RuntimeError('private chat unavailable')
    with pytest.raises(GameError, match='Открой личный чат'):
        await service.claim(7, BIO_TASK)
    db.bank.update_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_signed_api_ignores_supplied_user_id(monkeypatch):
    import time
    from aiohttp import web
    from aiohttp.test_utils import TestClient, TestServer
    from src.web.dojo_app import setup_dojo
    from tests.unit.test_hedgehog_game import signed
    mock_claim = AsyncMock(return_value={'task': {'slug': NAME_TASK, 'claimed': True},
        'reward_coins': 1000, 'energy_bonus': 0, 'new_coins': 1200})
    monkeypatch.setattr('src.services.dojo_profile_tasks.DojoProfileTasks.claim', mock_claim)
    container = NS(settings=NS(bot_token='test-token', maintenance_mode=False),
        mongo_client=NS(database=NS()),
        dojo_miner_service=NS(state=AsyncMock(return_value={'phase': 'ready', 'balance': 200})),
        dojo_task_service=NS(claim=AsyncMock()))
    app = web.Application()
    setup_dojo(app, container)
    async with TestClient(TestServer(app)) as client:
        response = await client.post('/miniapp/dojo/api/task', json={
            'initData': signed(now=int(time.time())), 'slug': NAME_TASK, 'user_id': 999})
        assert response.status == 200
        assert (await response.json())['reward_coins'] == 1000
        mock_claim.assert_awaited_once_with(7, NAME_TASK)
        container.dojo_task_service.claim.assert_not_awaited()
        response = await client.post('/miniapp/dojo/api/task', json={'slug': NAME_TASK})
        assert response.status == 401
