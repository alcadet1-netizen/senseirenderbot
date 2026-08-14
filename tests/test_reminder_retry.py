
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from src.services.chat_activity_service import ChatActivityService

async def test_reminder_retry():
    print("🚀 Testing ChatActivityService Retry Logic...")
    
    # Mock Redis
    redis = AsyncMock()
    redis.srem = AsyncMock()
    
    service = ChatActivityService(redis)
    
    # Mock Bot
    bot = AsyncMock()
    
    # Mock Chat
    chat = MagicMock()
    chat.type = "group"
    bot.get_chat.return_value = chat
    
    # Scenario 1: Success on first try
    print("\n1️⃣ Scenario: Success on first try")
    bot.send_message.return_value = True
    await service._send_reminder(bot, 123)
    assert bot.send_message.call_count == 1
    print("✅ Success on first try passed")
    
    # Scenario 2: Fail twice, then succeed
    print("\n2️⃣ Scenario: Fail twice, then succeed")
    bot.send_message.reset_mock()
    # side_effect: raise Exception twice, then return True
    bot.send_message.side_effect = [Exception("Network Error"), Exception("Timeout"), True]
    
    await service._send_reminder(bot, 123)
    assert bot.send_message.call_count == 3
    print("✅ Retry logic worked (called 3 times)")
    
    # Scenario 3: Fail all times
    print("\n3️⃣ Scenario: Fail all times")
    bot.send_message.reset_mock()
    bot.send_message.side_effect = Exception("Fatal Error")
    
    await service._send_reminder(bot, 123)
    assert bot.send_message.call_count == 3
    print("✅ Max retries respected")

    print("\n🎉 All retry tests passed!")

if __name__ == "__main__":
    asyncio.run(test_reminder_retry())
