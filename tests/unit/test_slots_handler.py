import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.types import Message, User, Chat
from aiogram.filters import CommandObject

from src.bot.handlers.slots import cmd_slots
from src.core.container import Container

@pytest.mark.asyncio
async def test_cmd_slots_bet_parsing():
    # Setup mocks
    message = AsyncMock(spec=Message)
    message.from_user = User(id=123, is_bot=False, first_name="TestUser", username="testuser")
    message.chat = Chat(id=1, type="private")
    message.bot = AsyncMock()
    
    # Mock message.answer to return a message with message_id
    sent_message_mock = MagicMock(spec=Message)
    sent_message_mock.message_id = 999
    sent_message_mock.text = "text"
    sent_message_mock.edit_text = AsyncMock()
    message.answer = AsyncMock(return_value=sent_message_mock)

    container = AsyncMock(spec=Container)
    container.message_cleanup_service = AsyncMock()
    container.slots_service = AsyncMock()
    
    # Mock successful play result
    container.slots_service.play_slots.return_value = {
        "success": True,
        "is_win": False,
        "prize": 0,
        "fee": 5,
        "balance": 90,
        "symbols": ["🍒", "🍋", "🍊"]
    }

    # Test cases
    test_cases = [
        ("100", 100),
        ("1k", 1000),
        ("1.5k", 1500),
        ("0.9m", 900000),
        ("0.5m", 500000),
        ("1к", 1000), # Cyrillic
        ("1м", 1000000), # Cyrillic
    ]

    for arg, expected_bet in test_cases:
        command = CommandObject(prefix="/", command="senseislots", args=arg)
        
        # Reset mocks
        container.slots_service.play_slots.reset_mock()
        
        await cmd_slots(message, command, container)
        
        # Verify play_slots was called with correct bet
        container.slots_service.play_slots.assert_called_with(123, expected_bet)

@pytest.mark.asyncio
async def test_cmd_slots_invalid_bet():
    # Setup mocks
    message = AsyncMock(spec=Message)
    message.from_user = User(id=123, is_bot=False, first_name="TestUser", username="testuser")
    message.answer = AsyncMock()
    
    container = AsyncMock(spec=Container)

    # "abc" should trigger ValueError
    command = CommandObject(prefix="/", command="senseislots", args="abc")
    await cmd_slots(message, command, container)
    message.answer.assert_called()
    assert "Неверная ставка" in message.answer.call_args[0][0]
