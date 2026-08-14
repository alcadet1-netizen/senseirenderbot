# Fix the duel service DM test file:
# Fix the mock setup for the users collection

with open(r'C:\sensei\tests\unit\test_duel_service_dm_single_message.py', 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

print("Reading duel service DM test file...")

# We need to fix the mock setup in this test file
# The error is: TypeError: 'MagicMock' object can't be awaited
# This happens when we try to await self.users.find_one but self.users is a regular MagicMock, not an AsyncMock

# Let's look at how the container mock is set up in this file
lines = content.split('\n')

# Find where the container mock is created
container_setup_lines = []
for i, line in enumerate(lines):
    if 'container = MagicMock()' in line:
        container_setup_lines.append(i)
        print(f"Found container mock at line {i+1}: {line}")

# Also look for how the users mock is set up
for i, line in enumerate(lines):
    if 'container.users' in line and ('=' in line or 'return_value' in line):
        print(f"Users mock setup at line {i+1}: {line}")

# Let's rewrite the test file with proper async mocks
# Instead of trying to edit it in place, let's create a fixed version

fixed_content = '''import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.services.duel_service import DuelService, Duel

@pytest.mark.asyncio
async def test_update_control_dm_does_not_send_on_message_not_modified():
    container = MagicMock()
    # Make users collection an AsyncMock
    container.users = AsyncMock()
    container.users.find_one = AsyncMock(return_value=None)

    service = DuelService(container)

    bot = AsyncMock()
    bot.edit_message_text = AsyncMock(side_effect=Exception("Bad Request: message is not modified"))
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
    # Make users collection an AsyncMock
    container.users = AsyncMock()
    # Mock the find_one to return user data
    container.users.find_one = AsyncMock(return_value={"id": 20, "name": "Bob"})

    service = DuelService(container)

    bot = AsyncMock()
    bot.edit_message_text = AsyncMock(side_effect=Exception("Bad Request: message to edit not found"))
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
'''

# Write the fixed file
with open(r'C:\sensei\tests\unit\test_duel_service_dm_single_message.py', 'w', encoding='utf-8') as f:
    f.write(fixed_content)

print("Fixed duel service DM test file.")

# Now let's test it