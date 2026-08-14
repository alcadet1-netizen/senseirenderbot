import asyncio
import os
import sys
from unittest.mock import MagicMock, patch, AsyncMock

# Add project root to path
sys.path.append(os.getcwd())

from src.core.config import Settings
from src.core.providers import AIProviderFactory
from src.services.digest_service import DigestService

async def main():
    print("Testing Groq Configuration...")
    
    # Reload settings to pick up .env changes
    from src.core import config
    import importlib
    importlib.reload(config)
    settings = config.get_settings()
    
    print(f"Groq API Key present: {'Yes' if settings.groq_api_key else 'No'}")
    if settings.groq_api_key:
        print("✅ API Key is set.")
    else:
        print("❌ API Key is not set.")

    factory = AIProviderFactory(settings)
    print(f"Active Provider: {factory.active_provider}")
    
    if factory.active_provider == "groq":
        print("✅ Active provider is Groq.")
    else:
        print(f"❌ Active provider is {factory.active_provider}")

    provider = factory.get_provider()
    print(f"Provider URL: {provider.url}")
    print(f"Provider Model: {provider.model}")
    
    if "groq.com" in provider.url:
        print("✅ URL is correct.")
    else:
        print("❌ URL is incorrect.")

    # Test DigestService limit change
    print("\nTesting DigestService limit...")
    
    service = DigestService(settings)
    
    # Create a mock chat_id
    chat_id = 123
    
    # Mock get_messages to return 1000 messages
    mock_msgs = [MagicMock() for _ in range(1000)]
    service.get_messages = MagicMock(return_value=mock_msgs)
    service.get_stats = MagicMock(return_value={})
    service.get_topics = MagicMock(return_value=[])
    
    # Use AsyncMock for async methods
    service.generate_short_reaction = AsyncMock(return_value="Reaction")
    service.generate_digest = AsyncMock(return_value="Digest result")
    service.mark_digest_done = MagicMock()
    
    # Mock format_for_llm
    service.format_for_llm = MagicMock(return_value="Mock Log")
    
    # Mock bot
    bot = MagicMock()
    bot.send_message = AsyncMock() # send_message is async
    bot.send_chat_action = AsyncMock() # send_chat_action is async
    
    # Run trigger_digest
    # Note: trigger_digest checks if chat_id is in generating.
    # It adds it, then removes it in finally.
    
    await service.trigger_digest(chat_id, bot)
    
    # Check arguments to format_for_llm
    args, _ = service.format_for_llm.call_args
    print(f"format_for_llm called with limit: {args[1]}")
    
    if args[1] == 500:
        print("✅ limit is 500.")
    else:
        print(f"❌ limit is {args[1]}.")

if __name__ == "__main__":
    asyncio.run(main())
