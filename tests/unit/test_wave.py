"""Wave completion, notification delivery and prize regression tests."""
import asyncio
from collections import Counter
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import SendMessage
from src.bot.handlers import wave as w


@pytest.fixture(autouse=True)
def clean_waves():
    for store in (w._active_waves, w._wave_streaks, w._wave_cooldowns,
                  w._starting_waves, w._finishing_waves):
        store.clear()
    yield
    for store in (w._active_waves, w._wave_streaks, w._wave_cooldowns,
                  w._starting_waves, w._finishing_waves):
        store.clear()


def setup_round(current=100):
    wave = dict(target=100, current=current, participants={1, 2, 3, 4},
                message_counts=Counter({'same': current}),
                user_id_counts=Counter({1: 40, 2: 30, 3: 20, 4: 10}),
                user_names={1: 'same', 2: 'same', 3: '<A&B>', 4: 'Four'},
                expires=0, message_id=50, ui_lock=asyncio.Lock())
    w._active_waves[-100] = wave
    bot = SimpleNamespace(edit_message_text=AsyncMock(), send_message=AsyncMock())
    economy = SimpleNamespace(process_game_win=AsyncMock(return_value={'success': True}),
                              _withdraw_from_bank=AsyncMock())
    return wave, bot, SimpleNamespace(economy_service=economy)


@pytest.mark.asyncio
async def test_victory_announced_once_with_single_prizes_and_no_extra_bank_debit():
    _, bot, container = setup_round()
    await asyncio.gather(w._finish_wave(bot, -100, container), w._finish_wave(bot, -100, container))
    bot.send_message.assert_awaited_once()
    text = bot.send_message.call_args.args[1]
    assert 'ВОЛНА ПОКОРЕНА' in text
    assert 'Все участники награждены' in text
    assert '2,250' in text  # 900 + 600 + 450 + 300, even with identical names
    assert '<tg-emoji' not in text and '\ufffd' not in text
    assert '&lt;A&amp;B&gt;' in text
    rewards = {c.kwargs['user_id']: c.kwargs['coins']
               for c in container.economy_service.process_game_win.call_args_list}
    assert rewards == {1: 900, 2: 600, 3: 450, 4: 300}
    container.economy_service._withdraw_from_bank.assert_not_awaited()
    assert -100 not in w._active_waves and -100 not in w._finishing_waves
    assert w._wave_streaks[-100] == 1
    assert w._wave_cooldowns[-100] > 0


@pytest.mark.asyncio
@pytest.mark.parametrize('current', [0, 50])
async def test_timeout_notifies_even_if_scoreboard_deleted(current):
    _, bot, container = setup_round(current)
    bot.edit_message_text.side_effect = RuntimeError('deleted scoreboard')
    await w._finish_wave(bot, -100, container)
    assert 'ВОЛНА ОТКАТИЛАСЬ' in bot.send_message.call_args.args[1]
    container.economy_service.process_game_win.assert_not_awaited()
    assert w._wave_streaks[-100] == 0


@pytest.mark.asyncio
async def test_markup_rejection_falls_back_to_plain_notification():
    _, bot, container = setup_round()
    bot.send_message.side_effect = [TelegramBadRequest(
        method=SendMessage(chat_id=-100, text='x'), message='invalid entities'), None]
    await w._finish_wave(bot, -100, container)
    assert bot.send_message.await_count == 2
    assert bot.send_message.call_args.kwargs['parse_mode'] is None
    assert '<b>' not in bot.send_message.call_args.args[1]
    assert '<A&B>' in bot.send_message.call_args.args[1]


@pytest.mark.asyncio
async def test_failed_prize_does_not_stop_others_or_claim_everyone_paid():
    _, bot, container = setup_round()
    container.economy_service.process_game_win.side_effect = [
        RuntimeError('DB unavailable'), {'success': False}, {'success': True}, {'success': True}]
    await w._finish_wave(bot, -100, container)
    assert container.economy_service.process_game_win.await_count == 4
    text = bot.send_message.call_args.args[1]
    assert 'Все участники награждены' not in text
    assert 'Всего роздано' not in text
    assert 'Награды требуют проверки: <b>2</b>' in text


@pytest.mark.asyncio
async def test_worker_finishes_expired_round_without_chat_activity():
    _, bot, container = setup_round(40)
    with patch.object(w.asyncio, 'sleep', new_callable=AsyncMock):
        await w._wave_worker(bot, -100, container)
    bot.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_old_worker_cannot_touch_new_round():
    old, bot, container = setup_round(30)
    new, _, _ = setup_round(50)
    with patch.object(w.asyncio, 'sleep', new_callable=AsyncMock):
        await w._wave_worker(bot, -100, container, old)
    assert w._active_waves[-100] is new
    bot.edit_message_text.assert_not_awaited()
    bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_simultaneous_start_is_reserved_before_network_await():
    message = SimpleNamespace(chat=SimpleNamespace(id=-100), answer=AsyncMock())
    entered, release = asyncio.Event(), asyncio.Event()
    async def start(*_):
        entered.set()
        await release.wait()
    with patch.object(w, '_start_wave', side_effect=start) as mock:
        task = asyncio.create_task(w.cmd_senseiwave(message, None))
        await entered.wait()
        await w.cmd_senseiwave(message, None)
        release.set()
        await task
    assert mock.await_count == 1
    assert not w._starting_waves


@pytest.mark.asyncio
async def test_delivery_failure_still_releases_finishing_state_and_does_not_repay():
    _, bot, container = setup_round()
    bot.send_message.side_effect = RuntimeError('network offline')
    with pytest.raises(RuntimeError):
        await w._finish_wave(bot, -100, container)
    assert not w._finishing_waves
    assert -100 in w._wave_cooldowns
    await w._finish_wave(bot, -100, container)
    assert container.economy_service.process_game_win.await_count == 4


@pytest.mark.asyncio
async def test_target_message_finishes_round_and_notifies():
    wave, bot, container = setup_round(99)
    wave.update(expires=float('inf'), combo_milestone=125, container=container)
    message = SimpleNamespace(chat=SimpleNamespace(id=-100), bot=bot,
                              from_user=SimpleNamespace(id=1, username='same', first_name='Same'))
    real_create = asyncio.create_task
    tasks = []
    def track(coro):
        task = real_create(coro)
        tasks.append(task)
        return task
    with patch.object(w.asyncio, 'create_task', side_effect=track):
        await w.count_wave_message(message, container)
        await asyncio.gather(*tasks)
    assert wave['current'] == 100
    assert 'ВОЛНА ПОКОРЕНА' in bot.send_message.call_args.args[1]
    assert container.economy_service.process_game_win.await_count == 4


@pytest.mark.asyncio
async def test_command_launches_state_and_worker():
    bot = SimpleNamespace()
    anim = SimpleNamespace(message_id=50, edit_text=AsyncMock())
    message = SimpleNamespace(chat=SimpleNamespace(id=-100, type='supergroup'),
                              from_user=SimpleNamespace(id=1), bot=bot,
                              answer=AsyncMock(return_value=anim))
    settings = SimpleNamespace(admin_ids=[1])
    tasks = []
    real_create = asyncio.create_task
    def track(coro):
        task = real_create(coro)
        tasks.append(task)
        return task
    with (patch.object(w, 'settings', settings),
          patch.object(w.asyncio, 'sleep', new_callable=AsyncMock),
          patch.object(w, '_wave_worker', new_callable=AsyncMock) as worker,
          patch.object(w.asyncio, 'create_task', side_effect=track)):
        await w.cmd_senseiwave(message, None)
        await asyncio.gather(*tasks)
    state = w._active_waves[-100]
    assert state['current'] == 0
    assert state['target'] == w.WAVE_TARGET_MESSAGES
    worker.assert_awaited_once_with(bot, -100, None, state)
    assert not w._starting_waves


def test_epic_finales_use_standard_emoji_and_keep_reward_rules_clear():
    victory = w._build_victory_message(100, 100, {1}, Counter({'<Ronin>': 100}), 3, 300)
    timeout = w._build_timeout_message(50, 100, {1}, Counter({'<Ronin>': 50}))
    for text in (victory, timeout):
        assert 'ЦУНАМИ СЕНСЕЯ: ФИНАЛ' in text
        assert '<tg-emoji' not in text
        assert '\ufffd' not in text
        assert '&lt;Ronin&gt;' in text
        assert 'обычные награды восстановлены' in text
        assert len(text) < 4096
    assert 'ЗАЛ СЛАВЫ' in victory
    assert 'Финальные призы не начисляются' in timeout
    assert 'остаются у игроков' in timeout
