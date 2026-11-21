from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from aiogram.types import Message

from src.bot.middlewares.cleanup import CommandCleanupMiddleware


@pytest.mark.asyncio
@pytest.mark.parametrize('text', ['Ежа', 'ежа', 'ЕЖА', 'фарм', 'фармить', 'фарма', 'ферма', '/senseidaily', 'Ап катана', 'АП КАТАНА', '/upkatana', r'\upkatana'])
async def test_invocation_deleted_after_result_and_tombstone_recorded(text):
    event=AsyncMock(spec=Message)
    event.delete=AsyncMock()
    event.text=text
    event.from_user=SimpleNamespace(id=7,is_bot=False)
    event.chat=SimpleNamespace(id=-100222)
    event.message_id=123
    result=SimpleNamespace(message_id=124,delete=AsyncMock())
    async def handle(message,data):
        event.delete.assert_not_awaited()
        return result
    container=object()
    with patch('src.bot.middlewares.cleanup.campaign_message_deleted',new=AsyncMock()) as deleted:
        assert await CommandCleanupMiddleware()(handle,event,{'container':container}) is result
        deleted.assert_awaited_once_with(container,-100222,123)
    event.delete.assert_awaited_once()
    result.delete.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('text,is_bot', [('Как получить ежа?',False),('Ежа',True),('Доброе утро',False), ('Как работает ап катана?',False), ('Ап катана',True)])
async def test_cleanup_preserves_conversation_and_bot_result(text,is_bot):
    event=AsyncMock(spec=Message)
    event.delete=AsyncMock()
    event.text=text
    event.from_user=SimpleNamespace(id=7,is_bot=is_bot)
    handler=AsyncMock(return_value='ok')
    assert await CommandCleanupMiddleware()(handler,event,{})=='ok'
    event.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_delete_rights_does_not_remove_or_fail_result():
    event=AsyncMock(spec=Message)
    event.delete=AsyncMock()
    event.text='Ежа'
    event.from_user=SimpleNamespace(id=7,is_bot=False)
    event.delete.side_effect=RuntimeError('not enough rights')
    handler=AsyncMock(return_value='result kept')
    with patch('src.bot.middlewares.cleanup.campaign_message_deleted',new=AsyncMock()) as deleted:
        assert await CommandCleanupMiddleware()(handler,event,{})=='result kept'
        deleted.assert_not_awaited()


@pytest.mark.asyncio
async def test_katana_trigger_kept_if_handler_cannot_send_response():
    event = AsyncMock(spec=Message)
    event.delete = AsyncMock()
    event.text = 'Ап катана'
    event.from_user = SimpleNamespace(id=7, is_bot=False)
    with pytest.raises(RuntimeError, match='delivery failed'):
        await CommandCleanupMiddleware()(AsyncMock(side_effect=RuntimeError('delivery failed')), event, {})
    event.delete.assert_not_awaited()
