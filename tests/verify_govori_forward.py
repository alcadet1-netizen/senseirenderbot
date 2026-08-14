import sys
import asyncio
from unittest.mock import AsyncMock, MagicMock

try:
    from aiogram.types import Message, CallbackQuery, Chat, User, InlineKeyboardMarkup, MessageOriginChannel
    from aiogram.fsm.context import FSMContext
    from src.bot.handlers.admin_commands import cmd_govori, process_govori_chat_selection, process_govori_content
    from src.bot.states.govori import GovoriState
    from src.core.container import Container
    from src.core.config import settings
except ImportError as e:
    sys.stderr.write(f"ImportError: {e}\n")
    sys.exit(1)

async def test_govori_forward_flow():
    sys.stderr.write("Testing /govori forward logic...\n")

    # Mock settings
    settings.main_chat_id = 100
    settings.allowed_chats_str = "101,102"

    # Mock State
    state = AsyncMock(spec=FSMContext)
    state_data = {'target_chat_id': '100'}
    async def get_data():
        return state_data
    state.get_data = AsyncMock(side_effect=get_data)

    # Test Case 1: Normal message (not forward from channel)
    # Should use message.copy_to
    msg1 = AsyncMock(spec=Message)
    msg1.text = "Normal message"
    msg1.forward_origin = None
    msg1.copy_to = AsyncMock()
    msg1.answer = AsyncMock()
    msg1.bot.copy_message = AsyncMock()
    
    container = MagicMock(spec=Container)

    sys.stderr.write("Testing normal message...\n")
    await process_govori_content(msg1, state, container)
    
    msg1.copy_to.assert_called()
    msg1.bot.copy_message.assert_not_called()
    sys.stderr.write("✅ Normal message used copy_to\n")

    # Test Case 2: Forward from channel
    # Should use bot.copy_message
    msg2 = AsyncMock(spec=Message)
    msg2.text = None
    msg2.forward_origin = MagicMock(spec=MessageOriginChannel)
    msg2.forward_origin.chat = MagicMock()
    msg2.forward_origin.chat.id = -999
    msg2.forward_origin.message_id = 555
    
    msg2.copy_to = AsyncMock()
    msg2.answer = AsyncMock()
    msg2.bot.copy_message = AsyncMock()

    sys.stderr.write("Testing channel forward message...\n")
    await process_govori_content(msg2, state, container)
    
    msg2.bot.copy_message.assert_called_with(chat_id=100, from_chat_id=-999, message_id=555)
    # copy_to should NOT be called if copy_message succeeds
    msg2.copy_to.assert_not_called()
    sys.stderr.write("✅ Channel forward used bot.copy_message\n")

    # Test Case 3: Forward from channel FAILS (e.g. bot not admin)
    # Should fallback to copy_to
    msg3 = AsyncMock(spec=Message)
    msg3.text = None
    msg3.forward_origin = MagicMock(spec=MessageOriginChannel)
    msg3.forward_origin.chat = MagicMock()
    msg3.forward_origin.chat.id = -999
    msg3.forward_origin.message_id = 555
    
    msg3.copy_to = AsyncMock()
    msg3.answer = AsyncMock()
    msg3.bot.copy_message = AsyncMock(side_effect=Exception("TelegramAPIError"))

    sys.stderr.write("Testing channel forward failure fallback...\n")
    await process_govori_content(msg3, state, container)
    
    msg3.bot.copy_message.assert_called()
    msg3.copy_to.assert_called()
    sys.stderr.write("✅ Fallback to copy_to worked\n")

if __name__ == "__main__":
    asyncio.run(test_govori_forward_flow())
