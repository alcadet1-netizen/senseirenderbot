
import asyncio
import sys
from unittest.mock import MagicMock, AsyncMock

# Mock structlog before importing anything that might use it
sys.modules["structlog"] = MagicMock()

from aiogram.types import Message, Chat, User
from src.bot.middlewares.user_activity import EnhancedUserActivityMiddleware, ActivityConfig

async def test_reproduce_issue():
    print("Reproducing issue...")

    # Mock ThrottleManager
    mock_throttle = MagicMock()
    mock_throttle.throttle = AsyncMock(return_value=True) # Always allow throttling for test

    # Mock Config
    config = ActivityConfig(throttle_seconds=0)

    # Initialize Middleware
    middleware = EnhancedUserActivityMiddleware(mock_throttle, config)

    # Mock Handler
    async def handler(event, data):
        return True

    # Mock Container and EconomyService
    mock_container = MagicMock()
    mock_economy_service = MagicMock()
    mock_economy_service.process_message_reward = AsyncMock(return_value={"success": True})
    mock_container.economy_service = mock_economy_service
    
    # Mock Middleware Data
    data = {"container": mock_container}

    # --- Scenario 1: Private Chat ---
    print("\nScenario 1: Private Chat")
    event_private = MagicMock(spec=Message)
    event_private.chat = MagicMock(spec=Chat)
    event_private.chat.type = "private"
    event_private.chat.id = 123
    event_private.from_user = MagicMock(spec=User)
    event_private.from_user.id = 456
    event_private.from_user.username = "test_user_private"
    event_private.from_user.first_name = "Test"
    event_private.from_user.last_name = "User"
    event_private.from_user.is_bot = False
    event_private.content_type = "text"

    # We need to spy on ActivityProcessor.process_message or check the call to economy_service
    # But ActivityProcessor is created inside the method.
    # However, we can check the call to mock_economy_service.process_message_reward
    
    await middleware(handler, event_private, data)
    
    # Check arguments passed to process_message_reward
    # apply_rewards argument is what we care about.
    # process_message_reward(user_id, ..., apply_rewards=...)
    
    call_args_private = mock_economy_service.process_message_reward.call_args
    if call_args_private:
        kwargs = call_args_private.kwargs
        apply_rewards = kwargs.get('apply_rewards')
        print(f"  Private Chat apply_rewards: {apply_rewards}")
        if apply_rewards:
             print("  ISSUE REPRODUCED: apply_rewards is True for private chat.")
        else:
             print("  NO ISSUE: apply_rewards is False for private chat.")
    else:
        print("  Error: process_message_reward not called.")

    mock_economy_service.process_message_reward.reset_mock()

    # --- Scenario 2: Group Chat ---
    print("\nScenario 2: Group Chat")
    event_group = MagicMock(spec=Message)
    event_group.chat = MagicMock(spec=Chat)
    event_group.chat.type = "group"
    event_group.chat.id = 789
    event_group.from_user = MagicMock(spec=User)
    event_group.from_user.id = 101
    event_group.from_user.username = "test_user_group"
    event_group.from_user.first_name = "Test"
    event_group.from_user.last_name = "User"
    event_group.from_user.is_bot = False
    event_group.content_type = "text"

    await middleware(handler, event_group, data)

    call_args_group = mock_economy_service.process_message_reward.call_args
    if call_args_group:
        kwargs = call_args_group.kwargs
        apply_rewards = kwargs.get('apply_rewards')
        print(f"  Group Chat apply_rewards: {apply_rewards}")
        if apply_rewards:
             print("  BEHAVIOR CORRECT: apply_rewards is True for group chat.")
        else:
             print("  UNEXPECTED: apply_rewards is False for group chat.")
    else:
        print("  Error: process_message_reward not called.")

if __name__ == "__main__":
    asyncio.run(test_reproduce_issue())
