
import asyncio
from aiogram import Dispatcher, F
from aiogram.types import Message, User, Chat
from unittest.mock import MagicMock, AsyncMock

from src.bot.handlers import setup_routers
from src.bot.handlers.triggers import router as triggers_router

async def verify_catchall():
    # Setup Dispatcher and Routers
    dp = Dispatcher()
    
    # We only need to check if triggers_router (which contains the catch-all) 
    # handles a random message.
    # But to be sure, we should use the full setup.
    main_router = setup_routers()
    dp.include_router(main_router)
    
    # Create a mock message
    user = User(id=123, is_bot=False, first_name="TestUser", username="testuser")
    chat = Chat(id=123, type="private")
    message = Message(
        message_id=1, 
        date=1234567890, 
        chat=chat, 
        from_user=user, 
        text="some random text that is not a command"
    )
    
    # Mock bot
    bot = AsyncMock()
    bot.me = User(id=1, is_bot=True, first_name="Bot", username="Bot")
    
    # Resolve handler
    # In aiogram 3, we can use dp.feed_update or look at internal routing.
    # But simpler: we can check if the router handles it.
    
    # We can try to propagate the update and see if it is handled.
    # Since we can't easily spy on which handler was selected without running it,
    # we can just run it. But we need to mock dependencies.
    
    # Instead, let's just check triggers_router directly.
    # The catch-all is at the end.
    
    print("Verifying triggers_router catch-all...")
    
    # Create a dummy update
    # Note: resolving filters manually is hard.
    
    # Let's inspect the handlers in triggers_router
    print(f"Triggers router has {len(triggers_router.message.handlers)} handlers.")
    
    # The last handler should be our catch-all (no filters)
    last_handler = triggers_router.message.handlers[-1]
    print(f"Last handler: {last_handler}")
    print(f"Last handler callback: {last_handler.callback.__name__}")
    
    if last_handler.callback.__name__ == "catch_all_message":
        print("SUCCESS: catch_all_message is the last handler in triggers_router.")
        
        # Check filters
        if not last_handler.filters:
            print("SUCCESS: catch_all_message has NO filters (matches everything).")
        else:
            print(f"WARNING: catch_all_message has filters: {last_handler.filters}")
            
    else:
        print("FAILURE: catch_all_message is NOT the last handler.")

if __name__ == "__main__":
    asyncio.run(verify_catchall())
