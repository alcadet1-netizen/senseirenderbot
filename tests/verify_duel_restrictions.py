
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import asyncio
from unittest.mock import AsyncMock, MagicMock
from src.bot.handlers.duel_commands import cmd_duel
from src.core.container import Container

async def verify_duel_restrictions():
    print("🚀 Verifying Duel Restrictions...")
    
    # Mock Container
    container = MagicMock(spec=Container)
    container.user_service = AsyncMock()
    container.duel_service = AsyncMock()
    
    # Mock Message
    message = AsyncMock()
    message.from_user.id = 1
    message.from_user.username = "Challenger"
    message.from_user.full_name = "Challenger"
    message.text = "/duel"
    message.chat.id = 999
    
    # Mock Reply (Opponent)
    reply = AsyncMock()
    reply.from_user.id = 2
    reply.from_user.username = "Opponent"
    reply.from_user.full_name = "Opponent"
    reply.from_user.is_bot = False
    message.reply_to_message = reply
    
    # Helper to setup profiles
    def setup_profiles(p1_level, p1_katana, p2_level, p2_katana):
        container.user_service.get_profile.side_effect = [
            {"id": 1, "level": p1_level, "has_katana": p1_katana, "coins": 1000}, # Challenger
            {"id": 2, "level": p2_level, "has_katana": p2_katana, "coins": 1000}  # Opponent
        ]

    # Test 1: Challenger Level < 5
    print("\nTest 1: Challenger Level 4 (Fail)")
    setup_profiles(4, True, 10, True)
    await cmd_duel(message, container, AsyncMock())
    
    args, _ = message.answer.call_args
    print(f"Response: {args[0]}")
    assert "доступны только с 5 уровня" in args[0] or "доступны с 5 уровня" in args[0]

    # Test 2: Challenger No Katana
    print("\nTest 2: Challenger No Katana (Fail)")
    setup_profiles(10, False, 10, True)
    await cmd_duel(message, container, AsyncMock())
    
    args, _ = message.answer.call_args
    print(f"Response: {args[0]}")
    assert "нет катаны" in args[0]

    # Test 3: Opponent Level < 5
    print("\nTest 3: Opponent Level 4 (Fail)")
    setup_profiles(10, True, 4, True)
    await cmd_duel(message, container, AsyncMock())
    
    args, _ = message.answer.call_args
    print(f"Response: {args[0]}")
    assert "Оппонент слишком" in args[0] or "нужен 5 уровень" in args[0]

    # Test 4: Opponent No Katana
    print("\nTest 4: Opponent No Katana (Fail)")
    setup_profiles(10, True, 10, False)
    await cmd_duel(message, container, AsyncMock())
    
    args, _ = message.answer.call_args
    print(f"Response: {args[0]}")
    assert "У оппонента нет катаны" in args[0]

    # Test 5: Success
    print("\nTest 5: All OK (Success)")
    setup_profiles(10, True, 10, True)
    
    # Mock duel creation
    mock_duel = MagicMock()
    mock_duel.id = 777
    container.duel_service.create_duel.return_value = mock_duel
    
    await cmd_duel(message, container, AsyncMock())
    
    args, _ = message.answer.call_args
    print(f"Response: {args[0]}")
    assert "вызывает" in args[0] and "на дуэль" in args[0]
    
    print("\n✅ All restrictions verified.")

if __name__ == "__main__":
    asyncio.run(verify_duel_restrictions())
