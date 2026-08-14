import asyncio
from unittest.mock import MagicMock, AsyncMock
from aiogram.types import ChatMemberUpdated, User, Chat
from src.bot.handlers.events import on_user_join
from src.core.container import Container

async def main():
    # Mock container
    container = MagicMock(spec=Container)
    container.user_service = MagicMock()
    container.user_service.get_or_create = AsyncMock()

    # Mock user
    new_user = User(id=12345, is_bot=False, first_name="Neo", username="neo_matrix")
    
    # Mock event
    event = AsyncMock(spec=ChatMemberUpdated)
    event.new_chat_member = MagicMock()
    event.new_chat_member.user = new_user
    event.chat = Chat(id=-100, type="supergroup")
    event.answer = AsyncMock()

    # Run handler
    print("Testing on_user_join...")
    await on_user_join(event, container)

    # Check output
    if event.answer.called:
        args, kwargs = event.answer.call_args
        print("Bot answered with:")
        print(args[0])
    else:
        print("Bot did not answer.")

if __name__ == "__main__":
    asyncio.run(main())
