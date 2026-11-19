import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.bot.middlewares import user_activity as activity


def test_slow_stage_reports_monotonic_duration(caplog):
    with patch.object(activity.time, 'monotonic', side_effect=[100, 101.234]), \
         caplog.at_level(logging.WARNING, logger=activity.__name__):
        with activity._timed_activity_stage('reward'):
            pass
    assert len(caplog.records) == 1
    assert caplog.records[0].message == '[USER_ACTIVITY] Slow stage=reward duration_ms=1234'


def test_fast_stage_is_quiet_and_error_propagates(caplog):
    with patch.object(activity.time, 'monotonic', side_effect=[100, 100.2]), \
         caplog.at_level(logging.WARNING, logger=activity.__name__), \
         pytest.raises(ValueError, match='original'):
        with activity._timed_activity_stage('reward'):
            raise ValueError('original')
    assert not caplog.records


@pytest.mark.asyncio
async def test_processor_still_checks_achievements_after_reward():
    order = []
    async def reward(*args):
        order.append('reward')
        return activity.RewardResult(success=True, messages_count=3)
    async def achievements(*args):
        order.append('achievements')
        return []
    processor = activity.ActivityProcessor(SimpleNamespace(), activity.ActivityConfig())
    processor._process_reward = AsyncMock(side_effect=reward)
    processor._check_achievements = AsyncMock(side_effect=achievements)
    user = SimpleNamespace(id=42, is_bot=False)
    assert await processor.process_message(user, -100, True) == []
    assert order == ['reward', 'achievements']
    processor._process_reward.assert_awaited_once_with(user, True, -100)
