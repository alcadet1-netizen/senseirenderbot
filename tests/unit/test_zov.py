from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.bot.handlers import zov


def member(uid, status='member', bot=False, present=True):
    return NS(status=status, is_member=present, user=NS(id=uid, is_bot=bot, username=None, full_name='A < B'))


def test_target_in_group_never_uses_other_main_chat():
    with patch.object(zov, 'settings', NS(main_chat_id=-100)):
        for kind, expected in [('supergroup', -200), ('group', -200), ('private', -100)]:
            assert zov.target(NS(chat=NS(type=kind, id=-200))) == expected


@pytest.mark.asyncio
async def test_call_without_private_start_or_game_profile():
    async def rows():
        for uid in [1, 2, 2, 3, 4, 5]:
            yield {'user_id': uid}
    roster = Mock(find=Mock(return_value=rows()))
    rewards = AsyncMock(return_value=False)
    container = NS(mongo_client=NS(database=NS(chat_user_activities=roster)), economy_service=NS(distribute_zov_reward=rewards))
    bot = NS(get_chat_administrators=AsyncMock(return_value=[member(1, 'administrator'), member(7, bot=True)]),
             get_chat_member=AsyncMock(side_effect=[member(2), member(3, 'left'), member(4, 'restricted', present=False), member(5, bot=True)]),
             send_message=AsyncMock())
    await zov._run(bot, container, -100)
    roster.find.assert_called_once_with({'chat_id': -100}, {'user_id': 1})
    notice, summary = bot.send_message.await_args_list
    assert notice.args[0] == -100 and notice.args[1].count('tg://user?id=') == 2
    assert 'id=1"' in notice.args[1] and 'id=2"' in notice.args[1] and 'A &lt; B' in notice.args[1]
    assert 'упомянуто: 2' in summary.args[1] and 'бонусов: 0' in summary.args[1]
    assert rewards.await_count == 2
