
import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock
from src.bot.middlewares.throttling import ThrottlingMiddleware
from src.core.constants import THROTTLE_RATE_LIMIT
from aiogram.types import Message, User

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_throttling_fix():
    print("🚀 Starting throttling fix verification...")

    # Mock ThrottleManager
    throttle_manager = AsyncMock()
    
    # Setup throttle behavior:
    # First call returns True (allowed), subsequent calls return False (blocked)
    # We need to simulate checking 'commands' scope vs other scopes.
    
    async def throttle_side_effect(key, limit_seconds, scope="default"):
        # For this test, let's say 'commands' scope is always blocked after first call?
        # Or better, we just check IF throttle was called.
        print(f"   -> throttle called with scope='{scope}'")
        if scope == "commands":
            return False # Simulate BLOCKED for commands
        return True # Allowed for others

    throttle_manager.throttle.side_effect = throttle_side_effect

    # Initialize Middleware
    middleware = ThrottlingMiddleware(throttle_manager)

    # Mock Handler
    handler = AsyncMock()
    handler.return_value = "Handler Result"

    # Mock Data
    data = {}

    # --- TEST CASE 1: Regular Message (should NOT be throttled) ---
    print("\n📝 Test Case 1: Regular Message")
    user = User(id=123, is_bot=False, first_name="TestUser", username="testuser")
    msg_text = MagicMock(spec=Message)
    msg_text.from_user = user
    msg_text.text = "Hello world"
    msg_text.answer = AsyncMock()

    # Reset mocks
    throttle_manager.throttle.reset_mock()
    handler.reset_mock()
    throttle_manager.throttle.side_effect = None # Reset side effect
    throttle_manager.throttle.return_value = False # Should NOT be called, but if called returns False to prove block

    result = await middleware(handler, msg_text, data)

    if handler.called:
        print("✅ SUCCESS: Regular message passed through middleware.")
    else:
        print("❌ FAILURE: Regular message was blocked!")
        
    if throttle_manager.throttle.called:
         print("❌ FAILURE: Throttle was called for regular message!")
    else:
         print("✅ SUCCESS: Throttle was NOT called for regular message.")


    # --- TEST CASE 2: Command Message (should be throttled) ---
    print("\n🤖 Test Case 2: Command Message")
    msg_cmd = MagicMock(spec=Message)
    msg_cmd.from_user = user
    msg_cmd.text = "/start"
    msg_cmd.answer = AsyncMock()

    # Reset mocks
    throttle_manager.throttle.reset_mock()
    handler.reset_mock()
    
    # Simulate blocked command
    throttle_manager.throttle.side_effect = None
    throttle_manager.throttle.return_value = False # BLOCKED

    result = await middleware(handler, msg_cmd, data)

    if not handler.called:
        print("✅ SUCCESS: Command message was blocked.")
    else:
        print("❌ FAILURE: Command message passed through (should be blocked)!")
        
    # Verify throttle call arguments
    throttle_manager.throttle.assert_called()
    call_args = throttle_manager.throttle.call_args
    print(f"   Throttle called with: {call_args}")
    
    if call_args.kwargs.get('scope') == 'commands':
         print("✅ SUCCESS: Correct scope 'commands' used.")
    else:
         print(f"❌ FAILURE: Wrong scope used: {call_args.kwargs.get('scope')}")

if __name__ == "__main__":
    asyncio.run(test_throttling_fix())
