from unittest.mock import AsyncMock
import ast
from pathlib import Path

import pytest
from aiogram import Bot, Dispatcher
from aiogram.types import Update
from src.bot.middlewares.removed_music import RemovedMusicMiddleware, RETIRED


@pytest.mark.asyncio
@pytest.mark.parametrize('text', ['найти песню', 'НАЙТИ', '  найти трек', 'найди песню',
    '/music', '/music@Senseigame_bot трек', '!find трек', '.mus трек', '/m трек', '/музыка'])
async def test_retired_invocations_never_reach_any_message_handler(text):
    dp=Dispatcher();dp.update.outer_middleware(RemovedMusicMiddleware())
    handler=AsyncMock()
    @dp.message()
    async def incoming(message): await handler(message)
    session=AsyncMock();bot=Bot('123456:TEST',session=session)
    event=Update.model_validate(dict(update_id=1,message=dict(message_id=1,date=1,
        chat=dict(id=7,type='private'),**{'from':dict(id=7,is_bot=False,first_name='User')},text=text)))
    await dp.feed_update(bot,event)
    handler.assert_not_awaited();session.assert_not_called()
    await dp.storage.close()


@pytest.mark.parametrize('text',['Хочу найти ответ', 'найтись', '/donate', '/senseifly', 'Ежа', 'Привет'])
def test_ordinary_conversation_and_other_commands_unchanged(text):
    assert RETIRED.match(text) is None


def test_router_and_help_no_longer_reference_music():
    source=Path('src/bot/handlers/__init__.py').read_text()
    assert 'music_router' not in source
    assert 'src.bot.handlers.music' not in source
    assert '/music' not in Path('src/core/visuals.py').read_text()
    ast.parse(source)
