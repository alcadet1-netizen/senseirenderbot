
import asyncio
from unittest.mock import AsyncMock, MagicMock
from src.bot.middlewares.user_activity import UserActivityMiddleware
from aiogram.types import Message, User

async def test_middleware():
    # Mock ThrottleManager
    throttle_manager = AsyncMock()
    throttle_manager.throttle.return_value = True

    # Mock Container and EconomyService
    economy_service = AsyncMock()
    economy_service.process_message_reward.return_value = {
        "success": True, 
        "messages_count": 10,
        "new_xp": 100,
        "new_coins": 50
    }
    
    achievement_service = AsyncMock()
    achievement_service.check_and_unlock_achievements.return_value = []

    container = MagicMock()
    container.economy_service = economy_service
    container.achievement_service = achievement_service

    # Initialize Middleware
    middleware = UserActivityMiddleware(throttle_manager)

    # Mock Handler
    handler = AsyncMock()
    handler.return_value = "Handler Result"

    # Mock Message
    user = User(id=123, is_bot=False, first_name="TestUser", username="testuser")
    message = MagicMock(spec=Message)
    message.from_user = user
    message.text = "/start" # A command!
    message.answer = AsyncMock()

    # Data dict
    data = {"container": container}

    # Run middleware
    result = await middleware(handler, message, data)

    # Assertions
    print(f"Handler called: {handler.called}")
    print(f"Process reward called: {economy_service.process_message_reward.called}")
    
    if economy_service.process_message_reward.called:
        print("SUCCESS: Command message triggered reward processing.")
    else:
        print("FAILURE: Command message did NOT trigger reward processing.")

if __name__ == "__main__":
    asyncio.run(test_middleware())
