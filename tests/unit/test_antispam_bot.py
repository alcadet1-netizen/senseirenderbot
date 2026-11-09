import pytest
from unittest.mock import AsyncMock, patch
from aiogram.methods import SendMessage
from aiogram.types import Message, Chat, User
from src.bot.custom_bot import AntiSpamBot

@pytest.mark.asyncio
async def test_no_deletion_logic():
    """Test that AntiSpamBot no longer deletes messages (feature disabled)."""
    
    bot = AntiSpamBot(token="123:ABC", default=None)
    bot.delete_message = AsyncMock()
    
    # Mock super().__call__
    with patch("aiogram.Bot.__call__", new_callable=AsyncMock) as mock_call:
        dummy_message = Message(
            message_id=123, 
            date=0, 
            chat=Chat(id=1, type="private"), 
            from_user=User(id=1, is_bot=True, first_name="Bot")
        )
        mock_call.return_value = dummy_message
        
        method = SendMessage(chat_id=1, text="Any text")
        
        # Execute
        await bot(method)
        
        # Verify NO deletion
        bot.delete_message.assert_not_called()


@pytest.mark.asyncio
async def test_bot_defaults_allow_copying():
    from src.bot.loader import create_bot
    from src.bot.native_widgets import SendWidget
    bot = create_bot()
    try:
        assert bot.default.protect_content is False
        assert SendWidget(chat_id=7, html='<html></html>').protect_content is False
    finally:
        await bot.session.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('value', [True, False, None])
async def test_copy_permission_enforced_without_mutating_request(value):
    from aiogram.methods import SendPhoto
    bot = AntiSpamBot(token='123:ABC')
    try:
        for method in (SendMessage(chat_id=7, text='copy', protect_content=value),
                       SendPhoto(chat_id=7, photo='file_id', protect_content=value)):
            with patch('aiogram.Bot.__call__', new_callable=AsyncMock) as call:
                await bot(method)
            outgoing = call.call_args.args[0]
            assert outgoing.protect_content is False
            assert method.protect_content is value
            assert outgoing is not method
    finally:
        await bot.session.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('protected', [True, False, None])
async def test_private_copy_probe_reports_telegram_result(protected):
    from types import SimpleNamespace as NS
    from src.bot.handlers.widget_check import cmd_copy_check
    msg = NS(chat=NS(type='private'), answer=AsyncMock(
        return_value=NS(has_protected_content=protected)))
    await cmd_copy_check(msg)
    assert msg.answer.await_count == 2
    for call in msg.answer.call_args_list:
        assert call.kwargs['protect_content'] is False
        assert call.kwargs['parse_mode'] is None
    assert ('has_protected_content=true' in msg.answer.call_args.args[0]) is bool(protected)
