
import asyncio
import re
from unittest.mock import AsyncMock, MagicMock
from src.bot.handlers import triggers

# Mock Container
class MockContainer:
    def __init__(self):
        self.crypto_service = AsyncMock()
        self.daily_service = AsyncMock()
        self.user_service = AsyncMock()

async def verify_triggers():
    print("🚀 Verifying Triggers...")
    
    # 1. Verify Regex Patterns
    print("\n🔍 Checking Regex Patterns:")
    
    # Help
    help_text = "сенсей помоги"
    assert triggers.HELP_PATTERN.search(help_text), f"❌ Failed to match help pattern: {help_text}"
    print(f"✅ Help pattern matched: '{help_text}'")
    
    help_text_2 = "ℹ️ Помощь"
    assert triggers.HELP_PATTERN.search(help_text_2), f"❌ Failed to match help pattern: {help_text_2}"
    print(f"✅ Help pattern matched: '{help_text_2}'")

    # Crypto Top
    top_text = "сенсей дай курс"
    assert triggers.CRYPTO_TOP_PATTERN.search(top_text), f"❌ Failed to match top pattern: {top_text}"
    print(f"✅ Top pattern matched: '{top_text}'")
    
    top_text_btn = "📊 CoinGecko"
    assert triggers.CRYPTO_TOP_PATTERN.search(top_text_btn), f"❌ Failed to match top pattern: {top_text_btn}"
    print(f"✅ Top pattern matched: '{top_text_btn}'")

    # Crypto Price
    price_text = "курс TON"
    match = triggers.CRYPTO_PRICE_PATTERN.search(price_text)
    assert match and match.group(1).lower() == "ton", f"❌ Failed to match price pattern: {price_text}"
    print(f"✅ Price pattern matched: '{price_text}' -> {match.group(1)}")

    # Crypto Calc
    calc_text = "курс № TON № 100"
    match = triggers.CRYPTO_CALC_PATTERN.search(calc_text)
    assert match and match.group(1).lower() == "ton" and match.group(2) == "100", f"❌ Failed to match calc pattern: {calc_text}"
    print(f"✅ Calc pattern matched: '{calc_text}' -> {match.group(1)}, {match.group(2)}")

    # Sensei (General)
    sensei_text = "сенсей"
    assert triggers.SENSEI_PATTERN.search(sensei_text), f"❌ Failed to match sensei pattern: {sensei_text}"
    print(f"✅ Sensei pattern matched: '{sensei_text}'")

    # Daily
    daily_text = "ежа"
    assert triggers.DAILY_PATTERN.search(daily_text), f"❌ Failed to match daily pattern: {daily_text}"
    print(f"✅ Daily pattern matched: '{daily_text}'")

    # 2. Verify Handlers (Mocking)
    print("\n🔍 Checking Handlers Logic:")
    
    container = MockContainer()
    message = AsyncMock()
    
    # Test Crypto Top
    container.crypto_service.get_top_10_message.return_value = "Top 10 List..."
    await triggers.trigger_crypto_top(message, container)
    message.answer.assert_called_with("Top 10 List...", parse_mode="HTML")
    print("✅ trigger_crypto_top handler working")
    
    # Test Crypto Price
    message.reset_mock()
    message.text = "курс TON"
    container.crypto_service.get_price_message.return_value = "TON Price..."
    await triggers.trigger_crypto_price(message, container)
    message.answer.assert_called_with("TON Price...", parse_mode="HTML")
    print("✅ trigger_crypto_price handler working")

    # Test Crypto Calc
    message.reset_mock()
    message.text = "курс № TON № 100"
    container.crypto_service.get_calculator_message.return_value = "Calc Result..."
    await triggers.trigger_crypto_calc(message, container)
    message.answer.assert_called_with("Calc Result...", parse_mode="HTML")
    print("✅ trigger_crypto_calc handler working")

    # Test Easter Egg
    message.reset_mock()
    message.text = "путь самурая"
    # Note: check_easter_eggs_handler doesn't use container, it uses texts.phrases
    # We invoke it directly
    await triggers.check_easter_eggs_handler(message)
    # We expect an answer because "путь самурая" is in EASTER_EGGS
    message.answer.assert_called()
    print("✅ check_easter_eggs_handler working")

    print("\n🎉 All triggers verified successfully!")

if __name__ == "__main__":
    asyncio.run(verify_triggers())
