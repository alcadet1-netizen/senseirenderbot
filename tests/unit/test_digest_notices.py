from collections import defaultdict
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.services.digest_service import ChatData, DigestService


@pytest.fixture
def service():
    obj = DigestService.__new__(DigestService)
    obj.chats = defaultdict(ChatData)
    obj.cooldowns = {}
    obj.generating = set()
    obj.digest_number = defaultdict(int)
    obj.settings = SimpleNamespace(digest_cooldown=60)
    return obj


def test_count_survives_buffer_rotation(service):
    for _ in range(1000):
        service.add_message(1, 7, 'user', 'User', 'Hi')
    service.mark_digest_done(1)
    service.add_message(1, 7, 'user', 'User', 'New')
    assert service.get_new_messages_count(1) == 1
    assert len(service.chats[1].messages) == 1000


@pytest.mark.asyncio
@pytest.mark.parametrize('vestnik', [True, False])
@pytest.mark.parametrize('fails', [True, False])
async def test_publication_lifecycle(service, monkeypatch, vestnik, fails):
    service.add_message(1, 7, 'user', 'User', 'Hi')
    async def generate(*args):
        service.add_message(1, 8, 'user', 'User', 'New')
        if fails:
            raise ValueError('internal details')
        return '<hello>' * 600
    monkeypatch.setattr(service, 'generate_vestnik' if vestnik else 'generate_digest', generate)
    bot = AsyncMock()
    await service._publish_issue(1, bot, vestnik=vestnik)
    messages = [c.args[1] for c in bot.send_message.await_args_list][1:]
    assert all(c.kwargs['parse_mode'] is None for c in bot.send_message.await_args_list)
    if fails:
        assert len(messages) == 1 and '/senseivesti' in messages[0] and 'internal details' not in messages[0]
    else:
        assert ''.join(messages) == '<hello>' * 600 and all(0 < len(m) <= 4000 for m in messages)
    assert service.get_new_messages_count(1) == (2 if fails else 1)
    bot.send_message.return_value.delete.assert_awaited_once()
