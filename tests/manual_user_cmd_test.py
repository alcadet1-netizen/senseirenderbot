import sys
import asyncio
from unittest.mock import AsyncMock, MagicMock

try:
    from aiogram.types import Message, User, Chat
    from src.bot.handlers.user_commands import cmd_senseiuser
    from src.core.container import Container
    from src.core.visuals import Visuals
except ImportError as e:
    sys.stderr.write(f"ImportError: {e}\n")
    sys.exit(1)
except Exception as e:
    sys.stderr.write(f"Error during import: {e}\n")
    sys.exit(1)

async def test_cmd_senseiuser():
    sys.stderr.write("Testing cmd_senseiuser...\n")

    # Mock Container and StatsService
    container = MagicMock(spec=Container)
    container.stats_service = AsyncMock()
    container.stats_service.get_admin_stats.return_value = {
        "users": {"total": 1337}
    }

    # Mock Message
    message = AsyncMock(spec=Message)
    message.from_user = User(id=1, is_bot=False, first_name="TestUser", username="testuser")
    message.chat = Chat(id=1, type="private")
    message.answer = AsyncMock()

    # Run command
    await cmd_senseiuser(message, container)

    # Verify
    message.answer.assert_called_once()
    args, kwargs = message.answer.call_args
    text = args[0]
    
    sys.stderr.write(f"Output text:\n{text}\n")

    if "👥 ПОЛЬЗОВАТЕЛИ" in text and "Всего: 1337" in text:
        sys.stderr.write("✅ Success: Command output contains expected user count.\n")
    else:
        sys.stderr.write("❌ Failed: Output does not contain expected user count.\n")

if __name__ == "__main__":
    asyncio.run(test_cmd_senseiuser())
