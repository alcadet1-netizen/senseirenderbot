"""Задания подписки /dojo: дефолтный канал, проверка, выплата и админ-команды."""
import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.bot.handlers.dojo_tasks_admin import (
    cmd_task_add,
    cmd_task_link,
    parse_add_args,
    parse_link_args,
)
from src.services.dojo_miner_service import DojoMinerService
from src.services.dojo_task_service import (
    DEFAULT_ENERGY,
    DEFAULT_REWARD,
    DojoTaskService,
    link_slug,
    normalize_link_url,
    normalize_username,
)
from src.services.hedgehog_service import GameError
from tests.unit.test_hedgehog_game import Collection


class Cursor:
    def __init__(self, items):
        self.items = list(items)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.items:
            raise StopAsyncIteration
        return self.items.pop(0)


class Tasks(Collection):
    def find(self, query):
        return Cursor(
            copy.deepcopy(doc)
            for doc in self.docs.values()
            if self.matches(doc, query)
        )

    async def insert_one(self, doc):
        if doc['_id'] in self.docs:
            raise RuntimeError('duplicate')
        self.docs[doc['_id']] = copy.deepcopy(doc)

    async def delete_one(self, query):
        for key, doc in list(self.docs.items()):
            if self.matches(doc, query):
                del self.docs[key]
                return



def service(status='member', payout=None):
    db = SimpleNamespace(dojo_tasks=Tasks(), dojo_task_claims=Tasks())
    economy = SimpleNamespace(
        process_game_win=AsyncMock(
            return_value=payout if payout is not None else {
                'success': True, 'new_coins': 20_000,
            }
        )
    )
    bot = SimpleNamespace(
        get_chat_member=AsyncMock(return_value=SimpleNamespace(status=status)),
    )
    container = SimpleNamespace(
        mongo_client=SimpleNamespace(database=db),
        economy_service=economy,
        bot=bot,
    )
    return container, DojoTaskService(container), economy, bot


def test_normalize_username_accepts_links_and_handles():
    assert normalize_username('@SenseiDurova') == 'SenseiDurova'
    assert normalize_username('https://t.me/SenseiDurova/') == 'SenseiDurova'
    assert normalize_username('t.me/SenseiDurova') == 'SenseiDurova'
    assert normalize_username('bad name') == ''
    assert normalize_username('@1bad') == ''


@pytest.mark.asyncio
async def test_default_senseidurova_task_has_requested_reward():
    _, tasks, _, _ = service()
    items = await tasks.list_tasks(7)
    assert len(items) == 1
    assert items[0]['username'] == 'SenseiDurova'
    assert items[0]['reward_coins'] == DEFAULT_REWARD == 10_000
    assert items[0]['energy_bonus'] == DEFAULT_ENERGY == 100
    assert items[0]['claimed'] is False


@pytest.mark.asyncio
async def test_claim_checks_subscription_pays_once_and_adds_energy():
    _, tasks, economy, bot = service()
    result = await tasks.claim(7, 'senseidurova')
    assert result['reward_coins'] == 10_000
    assert result['energy_bonus'] == 100
    assert result['new_coins'] == 20_000
    economy.process_game_win.assert_awaited_once()
    assert economy.process_game_win.await_args.kwargs['coins'] == 10_000
    assert 'SenseiDurova' in economy.process_game_win.await_args.kwargs['description']
    bot.get_chat_member.assert_awaited_once_with('@SenseiDurova', 7)
    assert await tasks.energy_bonus_total(7) == 100
    with pytest.raises(GameError, match='уже получена'):
        await tasks.claim(7, 'senseidurova')
    items = await tasks.list_tasks(7)
    assert items[0]['claimed'] is True
    assert economy.process_game_win.await_count == 1


@pytest.mark.asyncio
async def test_claim_sends_the_one_time_energy_charge_to_the_miner():
    container, tasks, _, _ = service()
    miner = SimpleNamespace(apply_task_energy=AsyncMock(return_value=True))
    container.dojo_miner_service = miner
    result = await tasks.claim(7, 'senseidurova')
    assert result['energy_bonus'] == 100
    miner.apply_task_energy.assert_awaited_once_with(
        7, 100, '7:senseidurova')


@pytest.mark.asyncio
async def test_unsubscribed_user_cannot_claim():
    _, tasks, economy, _ = service(status='left')
    with pytest.raises(GameError, match='подпишись'):
        await tasks.claim(7, 'senseidurova')
    economy.process_game_win.assert_not_awaited()
    assert await tasks.energy_bonus_total(7) == 0


@pytest.mark.asyncio
async def test_failed_payout_rolls_back_claim():
    _, tasks, economy, _ = service(payout={'success': False})
    with pytest.raises(GameError, match='недоступна'):
        await tasks.claim(7, 'senseidurova')
    assert await tasks.energy_bonus_total(7) == 0
    items = await tasks.list_tasks(7)
    assert items[0]['claimed'] is False


@pytest.mark.asyncio
async def test_admin_can_add_and_disable_channels():
    _, tasks, _, _ = service()
    added = await tasks.add_task(
        '@MyChannel', 'Мой канал', -100123, 5_000, 50, created_by=1)
    assert added['slug'] == 'mychannel'
    assert added['username'] == 'MyChannel'
    items = await tasks.list_tasks(7)
    assert [item['username'] for item in items] == ['SenseiDurova', 'MyChannel']
    assert items[1]['reward_coins'] == 5_000
    assert items[1]['energy_bonus'] == 50
    assert await tasks.remove_task('@MyChannel') is True
    items = await tasks.list_tasks(7)
    assert [item['username'] for item in items] == ['SenseiDurova']
    all_tasks = await tasks.all_tasks()
    assert any(not item['active'] for item in all_tasks if item['slug'] == 'mychannel')


@pytest.mark.asyncio
async def test_disabled_default_stays_disabled():
    _, tasks, _, _ = service()
    await tasks.remove_task('senseidurova')
    assert await tasks.list_tasks(7) == []


def test_admin_parser_defaults_and_limits():
    assert parse_add_args('/task_add @SenseiDurova') == ('SenseiDurova', 10_000, 100)
    assert parse_add_args('/task_add https://t.me/MyChannel 5000 50') == (
        'MyChannel', 5000, 50)
    with pytest.raises(ValueError):
        parse_add_args('/task_add')
    with pytest.raises(ValueError):
        parse_add_args('/task_add @channel -1')
    with pytest.raises(ValueError):
        parse_add_args('/task_add @channel 1000 5000')


@pytest.mark.asyncio
async def test_admin_command_adds_channel_with_reward():
    message = SimpleNamespace(
        text='/task_add @MyChannel 5000 50',
        bot=SimpleNamespace(
            id=99,
            get_chat=AsyncMock(return_value=SimpleNamespace(
                id=-100123, title='Мой канал', type='channel')),
            get_chat_member=AsyncMock(return_value=SimpleNamespace(status='administrator')),
        ),
        from_user=SimpleNamespace(id=1),
        answer=AsyncMock(),
    )
    service_mock = SimpleNamespace(add_task=AsyncMock(return_value={
        'username': 'MyChannel', 'title': 'Мой канал',
        'reward_coins': 5000, 'energy_bonus': 50,
        'url': 'https://t.me/MyChannel',
    }))
    await cmd_task_add(message, SimpleNamespace(dojo_task_service=service_mock))
    kwargs = service_mock.add_task.await_args.kwargs
    assert kwargs['username'] == 'MyChannel'
    assert kwargs['channel_id'] == -100123
    assert kwargs['reward_coins'] == 5000
    assert kwargs['energy_bonus'] == 50
    assert '5 000' in message.answer.await_args.args[0]


@pytest.mark.asyncio
async def test_task_energy_is_pending_above_the_base_cap_not_inside_it():
    db = SimpleNamespace(
        dojo_miners=Tasks([{
            '_id': 7,
            'collected': True,
            'task_energy_pending': [{'key': '7:senseidurova', 'amount': 100}],
            'version': 1,
        }]),
        users=Collection([{'id': 7, 'coins': 500}]),
    )
    miner = DojoMinerService(
        SimpleNamespace(database=db),
        SimpleNamespace(process_game_win=AsyncMock()),
    )
    state = await miner.state(7)
    assert state['energy_max'] == 100
    assert state['energy'] == 200
    assert state['energy_start'] == 200
    assert state['task_energy_pending'] == 100
    # Two full-power hours instead of one: 15 + 15 + 3 = 33.
    assert state['reward'] == 32


def test_link_urls_are_https_and_stable():
    assert normalize_link_url('https://Example.com/ref?a=1#x') == (
        'https://example.com/ref?a=1#x')
    assert normalize_link_url('t.me/MyAppBot?start=ref_7') == (
        'https://t.me/MyAppBot?start=ref_7')
    assert normalize_link_url('www.example.com/ref') == (
        'https://www.example.com/ref')
    assert normalize_link_url('http://example.com') == ''
    assert normalize_link_url('javascript:alert(1)') == ''
    assert normalize_link_url('https://user:pass@example.com') == ''
    assert link_slug('https://Example.com/ref') == link_slug('https://example.com/ref')


@pytest.mark.asyncio
async def test_admin_can_add_and_claim_an_app_link_without_subscription_check():
    _, tasks, economy, bot = service(status='left')
    added = await tasks.add_link(
        'https://t.me/MyAppBot?start=ref_7', 'Мой сервис', 5_000, 50,
        created_by=1)
    assert added['kind'] == 'link'
    assert added['button_label'] == 'Запустить'
    assert added['host'] == 't.me'
    assert added['slug'].startswith('link-')
    items = await tasks.list_tasks(7)
    assert [item['kind'] for item in items] == ['channel', 'link']
    claimed = await tasks.claim(7, added['slug'])
    assert claimed['reward_coins'] == 5_000
    assert claimed['task']['claimed'] is True
    assert claimed['task']['button_label'] == 'Запустить'
    economy.process_game_win.assert_awaited_once()
    assert 'launch t.me' in economy.process_game_win.await_args.kwargs['description']
    bot.get_chat_member.assert_not_awaited()
    assert await tasks.remove_task('https://t.me/MyAppBot?start=ref_7') is True
    assert [item['slug'] for item in await tasks.list_tasks(7)] == ['senseidurova']


def test_admin_link_parser_accepts_reward_energy_and_title():
    assert parse_link_args(
        '/task_link https://app.example/ref 5000 50 Мой сервис') == (
        'https://app.example/ref', 5000, 50, 'Мой сервис')
    url, reward, energy, title = parse_link_args('/task_link t.me/MyBot?start=x')
    assert url == 'https://t.me/MyBot?start=x'
    assert reward == DEFAULT_REWARD and energy == DEFAULT_ENERGY
    assert title == 't.me'


@pytest.mark.asyncio
async def test_task_link_command_adds_a_launch_button():
    message = SimpleNamespace(
        text='/task_link https://app.example/ref 2500 25 Мой сервис',
        from_user=SimpleNamespace(id=1),
        answer=AsyncMock(),
    )
    add_link = AsyncMock(return_value={
        'kind': 'link', 'title': 'Мой сервис',
        'url': 'https://app.example/ref', 'host': 'app.example',
        'reward_coins': 2500, 'energy_bonus': 25,
    })
    await cmd_task_link(message, SimpleNamespace(
        dojo_task_service=SimpleNamespace(add_link=add_link)))
    kwargs = add_link.await_args.kwargs
    assert kwargs['url'] == 'https://app.example/ref'
    assert kwargs['title'] == 'Мой сервис'
    assert kwargs['reward_coins'] == 2500 and kwargs['energy_bonus'] == 25
    text = message.answer.await_args.args[0]
    assert 'Мой сервис' in text and 'Запустить' in text


@pytest.mark.asyncio
async def test_task_add_accepts_a_referral_url_as_link():
    message = SimpleNamespace(
        text='/task_add https://app.example/ref 1000 10 Приложение',
        from_user=SimpleNamespace(id=1),
        answer=AsyncMock(),
    )
    add_link = AsyncMock(return_value={
        'kind': 'link', 'title': 'Приложение',
        'url': 'https://app.example/ref', 'host': 'app.example',
        'reward_coins': 1000, 'energy_bonus': 10,
    })
    container = SimpleNamespace(dojo_task_service=SimpleNamespace(add_link=add_link))
    await cmd_task_add(message, container)
    add_link.assert_awaited_once()


@pytest.mark.asyncio
async def test_addchance_command_passes_stable_telegram_message_key(monkeypatch):
    from src.bot.handlers.dojo_tasks_admin import cmd_addchance
    grant = AsyncMock(return_value={'amount': 10, 'username': 'Example'})
    monkeypatch.setattr('src.bot.handlers.dojo_tasks_admin.DojoDailyService', lambda mongo: SimpleNamespace(grant_admin_chests=grant))
    msg = SimpleNamespace(text='/addchance @Example 10', from_user=SimpleNamespace(id=8),
                          chat=SimpleNamespace(id=123), message_id=456, answer=AsyncMock())
    await cmd_addchance(msg, SimpleNamespace(mongo_client=object()))
    grant.assert_awaited_once_with('Example', 10, 8, '123:456')
    assert '10 сундуков' in msg.answer.call_args.args[0]


@pytest.mark.asyncio
@pytest.mark.parametrize('text', ['/addchance @Example -1', '/addchance Example 3', '/addchance @Example 100000', '/addchance @Example 1 extra'])
async def test_addchance_rejects_bad_syntax(text):
    from src.bot.handlers.dojo_tasks_admin import cmd_addchance
    msg = SimpleNamespace(text=text, answer=AsyncMock())
    await cmd_addchance(msg, SimpleNamespace())
    assert 'Использование' in msg.answer.call_args.args[0]
