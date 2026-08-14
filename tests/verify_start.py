
import asyncio
from unittest.mock import AsyncMock, MagicMock
from src.bot.handlers import user_commands
from src.bot.keyboards import reply

# Mock Container
class MockContainer:
    def __init__(self):
        self.user_service = AsyncMock()
        # Mock get_or_create to return a dummy user or None
        self.user_service.get_or_create.return_value = MagicMock(id=1, username="test_user")

async def verify_start():
    print("🚀 Verifying Start Command...")
    
    # 1. Verify Keyboard
    print("\n🔍 Checking Crypto Start Keyboard:")
    keyboard = reply.get_crypto_start_keyboard()
    
    # Check if buttons exist in the keyboard
    # ReplyKeyboardMarkup has 'keyboard' attribute which is a list of lists of KeyboardButton
    buttons = []
    for row in keyboard.keyboard:
        for btn in row:
            buttons.append(btn.text)
            
    expected_buttons = ["📊 CoinGecko", "💹 CoinCap", "🔶 Binance", "📈 Сравнить", "ℹ️ Помощь"]
    
    for btn in expected_buttons:
        assert btn in buttons, f"❌ Missing button: {btn}"
        print(f"✅ Button found: {btn}")
        
    # 2. Verify Start Handler
    print("\n🔍 Checking Start Handler Logic:")
    
    container = MockContainer()
    message = AsyncMock()
    message.from_user.id = 123
    message.from_user.username = "test_user"
    message.from_user.first_name = "Test"
    message.chat.type = "private"
    
    await user_commands.cmd_start(message, container)
    
    # Verify user creation
    container.user_service.get_or_create.assert_called()
    print("✅ User creation called")
    
    # Verify answer with keyboard
    # message.answer should be called. We check if reply_markup was passed.
    args, kwargs = message.answer.call_args
    assert "reply_markup" in kwargs, "❌ reply_markup not missing in answer"
    assert kwargs["reply_markup"] == keyboard, "❌ Incorrect keyboard passed"
    print("✅ Start command answered with correct keyboard")

    print("\n🎉 Start command verified successfully!")

if __name__ == "__main__":
    asyncio.run(verify_start())
