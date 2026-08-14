import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.exceptions import TelegramBadRequest

from src.services.duel_service import DuelService, Duel


@pytest.mark.asyncio
async def test_update_control_dm_does_not_send_on_message_not_modified():
    container = MagicMock()
    # Mock the mongo_client and its database
    container.mongo_client = AsyncMock()
    container.mongo_client.database = AsyncMock()
    # Mock the users collection
    container.mongo_client.database.users = AsyncMock()
    container.mongo_client.database.users.find_one = AsyncMock(return_value=None)

    service = DuelService(container)

    bot = AsyncMock()
    bot.edit_message_text = AsyncMock(side_effect=TelegramBadRequest(method="editMessageText", message="Bad Request: message is not modified"))
    bot.send_message = AsyncMock()

    duel = Duel(
        id=1,
        challenger_id=10,
        opponent_id=20,
        bet=300,
        chat_id=100,
        bot=bot,
        container=container,
    )
    duel.accepted = True
    duel.round_num = 1
    duel.round_deadline_mono = asyncio.get_event_loop().time() + 30
    duel.actions[10] = {"dodge": None, "attack": None}
    duel.hits[10] = 0
    duel.hits[20] = 0
    duel.challenger_name = "Alice"
    duel.opponent_name = "Bob"
    duel.control_message_ids[10] = 777

    await service._update_control_dm(duel, 10)

    # Should not send a new message since edit failed with "not modified"
    bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_update_control_dm_sends_new_only_when_message_missing():
    container = MagicMock()
    # Mock the mongo_client and its database
    container.mongo_client = AsyncMock()
    container.mongo_client.database = AsyncMock()
    # Mock the users collection to return user data
    container.mongo_client.database.users = AsyncMock()
    container.mongo_client.database.users.find_one = AsyncMock(return_value={"id": 20, "name": "Bob"})

    service = DuelService(container)

    bot = AsyncMock()
    bot.edit_message_text = AsyncMock(side_effect=TelegramBadRequest(method="editMessageText", message="Bad Request: message to edit not found"))
    sent = MagicMock()
    sent.message_id = 888
    bot.send_message = AsyncMock(return_value=sent)
    bot.delete_message = AsyncMock()

    duel = Duel(
        id=1,
        challenger_id=10,
        opponent_id=20,
        bet=300,
        chat_id=100,
        bot=bot,
        container=container,
    )
    duel.accepted = True
    duel.round_num = 1
    duel.round_deadline_mono = asyncio.get_event_loop().time() + 30
    duel.actions[10] = {"dodge": None, "attack": None}
    duel.hits[10] = 0
    duel.hits[20] = 0
    duel.challenger_name = "Alice"
    duel.opponent_name = "Bob"
    duel.control_message_ids[10] = 777

    await service._update_control_dm(duel, 10)

    # Should send a new message since the edit failed with "message not found"
    bot.send_message.assert_called_once()