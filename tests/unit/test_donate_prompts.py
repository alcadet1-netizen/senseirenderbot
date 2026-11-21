from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

import pytest
from src.texts.donate_prompts import (DONATE_CHAT_PHRASES, DONATE_INACTIVE_PHRASES,
    get_random_donate_phrase)
from src.texts.reminders import CLASSIC_INACTIVE_PHRASES, get_inactive_reminder
from src.services.chat_activity_service import ChatActivityService
from tests.campaign_support import FakeDB


def test_prompts_are_short_factual_and_have_command():
    for text in (*DONATE_CHAT_PHRASES,*DONATE_INACTIVE_PHRASES):
        assert '/donate' in text and 'SenseiCoin' in text and 'Stars' in text
        assert len(text)<250 and '<' not in text and 'http' not in text
    assert get_random_donate_phrase() in DONATE_CHAT_PHRASES


@pytest.mark.parametrize('roll', range(5))
def test_hourly_selection_mixes_classic_and_donate_prompts(roll):
    with patch('src.texts.reminders.random.randrange', return_value=roll):
        text = get_inactive_reminder()
    assert text in (DONATE_INACTIVE_PHRASES if roll == 0 else CLASSIC_INACTIVE_PHRASES)
    assert ('/donate' in text) == (roll == 0)


@pytest.mark.asyncio
async def test_inactivity_prompt_only_after_hour_and_no_immediate_repeat():
    db=FakeDB();service=ChatActivityService(NS(database=db))
    await db.chat_activities.insert_one(dict(chat_id=-100222,last_activity=3600))
    bot=NS(get_chat=AsyncMock(return_value=NS(type='supergroup')),send_message=AsyncMock())
    with patch('src.services.chat_activity_service.group_admin_access.allowed',new=AsyncMock(return_value=True)):
        with patch('src.services.chat_activity_service.time.time',return_value=7199):
            await service._check_chats(bot)
        bot.send_message.assert_not_awaited()
        with patch('src.services.chat_activity_service.time.time',return_value=7201):
            await service._check_chats(bot)
            await service._check_chats(bot)
        bot.send_message.assert_awaited_once()
        assert bot.send_message.call_args.args[1] in CLASSIC_INACTIVE_PHRASES + DONATE_INACTIVE_PHRASES
        with patch('src.services.chat_activity_service.time.time',return_value=10800):
            await service._check_chats(bot)
        assert bot.send_message.await_count==1
        with patch('src.services.chat_activity_service.time.time',return_value=10802):
            await service._check_chats(bot)
        assert bot.send_message.await_count==2
