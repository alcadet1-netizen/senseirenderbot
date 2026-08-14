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
