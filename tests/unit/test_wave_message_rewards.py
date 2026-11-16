"""The wave bonus replaces message coins locally and never changes global rates."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.services.economy_service import EconomyService
from src.services.wave_activity import active_waves


@pytest.fixture(autouse=True)
def reset_waves():
    active_waves.clear()
    yield
    active_waves.clear()


def economy():
    db = SimpleNamespace(users=AsyncMock(), transactions=AsyncMock(), bank=AsyncMock(), tickets=AsyncMock())
    service = EconomyService(SimpleNamespace(database=db))
    db.users.find_one.return_value = dict(id=7, xp=100, coins=100, messages_count=1, is_banned=False)
    service._get_total_coins_in_circulation = AsyncMock(return_value=0)
    service._get_bank_balance = AsyncMock(return_value=10000)
    service._withdraw_from_bank = AsyncMock(return_value=True)
    return service


@pytest.mark.asyncio
@pytest.mark.parametrize('state,chat_id,expected', [
    ('active', -100, 30), ('active', -200, 9), ('active', None, 9),
    ('expired', -100, 9), ('target', -100, 9), ('missing', -100, 9),
])
async def test_wave_coins_are_local_and_stop_at_deadline_or_target(state, chat_id, expected):
    if state != 'missing':
        active_waves[-100] = dict(current=100 if state == 'target' else 99,
                                  target=100, expires=99 if state == 'expired' else 101)
    service = economy()
    with patch('src.services.wave_activity.time.time', return_value=100):
        result = await service.process_message_reward(7, chat_id=chat_id)
    assert result['coins_earned'] == expected
    service._withdraw_from_bank.assert_awaited_once_with(expected)
    assert service.transactions.insert_one.call_args.args[0]['coins_change'] == expected


@pytest.mark.asyncio
async def test_boost_does_not_bypass_reward_throttle_or_ban():
    active_waves[-100] = dict(current=0, target=100, expires=float('inf'))
    service = economy()
    result = await service.process_message_reward(7, chat_id=-100, apply_rewards=False)
    assert result['coins_earned'] == 0
    service._withdraw_from_bank.assert_not_awaited()
    service.users.find_one.return_value['is_banned'] = True
    result = await service.process_message_reward(7, chat_id=-100)
    assert not result['success']
    service._withdraw_from_bank.assert_not_awaited()


@pytest.mark.asyncio
async def test_normal_halving_restored_after_wave_without_changing_xp():
    active_waves[-100] = dict(current=0, target=100, expires=float('inf'))
    service = economy()
    with patch.object(service, '_calculate_halving_multiplier', return_value=0.5):
        during = await service.process_message_reward(7, chat_id=-100)
        active_waves.pop(-100)
        after = await service.process_message_reward(7, chat_id=-100)
    assert during['coins_earned'] == 30
    assert after['coins_earned'] == 4.5
    assert during['xp_earned'] == after['xp_earned']


@pytest.mark.asyncio
async def test_activity_processor_passes_chat_context_to_real_economy():
    from aiogram.types import User
    from src.bot.middlewares.user_activity import ActivityProcessor, ActivityConfig
    active_waves[-100] = dict(current=1, target=100, expires=float('inf'))
    service = economy()
    processor = ActivityProcessor(SimpleNamespace(economy_service=service), ActivityConfig())
    user = User(id=7, is_bot=False, first_name='Player')
    with patch.object(service, 'process_message_reward', wraps=service.process_message_reward) as reward:
        result = await processor._process_reward(user, True, -100)
    assert result.success
    assert reward.call_args.kwargs['chat_id'] == -100
    service._withdraw_from_bank.assert_awaited_once_with(30)


@pytest.mark.asyncio
@pytest.mark.parametrize('success', [True, False])
async def test_finishing_round_removes_boost_before_prizes_are_paid(success):
    from collections import Counter
    from src.bot.handlers.wave import _finish_wave, _wave_cooldowns, _wave_streaks
    from src.services.wave_activity import wave_message_reward
    active_waves[-100] = dict(current=100 if success else 50, target=100,
        expires=float('inf'), participants={7}, message_counts=Counter({'Player': 100}),
        user_id_counts=Counter({7: 100}), user_names={7: 'Player'}, message_id=1)
    async def pay(**kwargs):
        assert wave_message_reward(-100) is None
        return {'success': True}
    bot = SimpleNamespace(edit_message_text=AsyncMock(), send_message=AsyncMock())
    container = SimpleNamespace(economy_service=SimpleNamespace(process_game_win=AsyncMock(side_effect=pay)))
    try:
        await _finish_wave(bot, -100, container)
        assert wave_message_reward(-100) is None
        text = bot.send_message.call_args.args[1]
        assert 'обычные награды' in text
    finally:
        _wave_cooldowns.clear()
        _wave_streaks.clear()
