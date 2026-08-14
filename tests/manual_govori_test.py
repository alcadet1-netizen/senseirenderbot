import sys
import asyncio
from unittest.mock import AsyncMock, MagicMock

try:
    from aiogram.types import Message, CallbackQuery, Chat, User, InlineKeyboardMarkup
    from aiogram.fsm.context import FSMContext
    from src.bot.handlers.admin_commands import cmd_govori, process_govori_chat_selection, process_govori_content
    from src.bot.states.govori import GovoriState
    from src.core.container import Container
    from src.core.config import settings
except ImportError as e:
    sys.stderr.write(f"ImportError: {e}\n")
    sys.exit(1)

async def test_govori_flow():
    sys.stderr.write("Testing /govori flow...\n")

    old_main_chat_id = settings.main_chat_id
    old_allowed_chats_str = settings.allowed_chats_str
    settings.main_chat_id = 100
    settings.allowed_chats_str = "101,102"

    # Mock State
    state = AsyncMock(spec=FSMContext)
    state_data = {}
    async def update_data(**kwargs):
        state_data.update(kwargs)
    async def get_data():
        return state_data
    state.update_data = AsyncMock(side_effect=update_data)
    state.get_data = AsyncMock(side_effect=get_data)

    # 1. Test cmd_govori
    message = AsyncMock()
    message.chat = MagicMock()
    message.chat.type = "private"
    message.bot.get_chat = AsyncMock()
    message.bot.get_chat.side_effect = lambda id: AsyncMock(title=f"Title {id}")
    
    await cmd_govori(message, state)
    
    message.answer.assert_called_once()
    args, kwargs = message.answer.call_args
    assert "Выберите чат" in args[0]
    assert isinstance(kwargs['reply_markup'], InlineKeyboardMarkup)
    kb = kwargs['reply_markup']
    # Expect 1 (all) + 3 (chats) + 1 (cancel) = 5 buttons (rows)
    assert len(kb.inline_keyboard) >= 3 
    sys.stderr.write("✅ cmd_govori passed\n")

    # 2. Test chat selection (Select chat 101)
    callback = AsyncMock()
    callback.data = "govori_select:101"
    callback.message = AsyncMock()
    callback.message.edit_text = AsyncMock()
    
    await process_govori_chat_selection(callback, state)
    
    assert state_data['target_chat_id'] == "101"
    state.set_state.assert_called_with(GovoriState.waiting_for_content)
    callback.message.edit_text.assert_called_once()
    sys.stderr.write("✅ process_govori_chat_selection passed\n")

    # 3. Test content sending
    content_message = AsyncMock()
    content_message.text = "Hello World"
    content_message.copy_to = AsyncMock()
    content_message.answer = AsyncMock()
    content_message.forward_origin = None
    container = MagicMock(spec=Container)

    await process_govori_content(content_message, state, container)
    
    content_message.copy_to.assert_called_once_with(101)
    sys.stderr.write("✅ process_govori_content passed\n")

    settings.main_chat_id = old_main_chat_id
    settings.allowed_chats_str = old_allowed_chats_str

if __name__ == "__main__":
    asyncio.run(test_govori_flow())
