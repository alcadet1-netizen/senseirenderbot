from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.services.broadcast_service import BroadcastService


@pytest.mark.asyncio
async def test_count_uses_database_without_loading_user_profiles():
    users = SimpleNamespace(count_documents=AsyncMock(return_value=1_000_000), find=Mock())
    service = BroadcastService(SimpleNamespace(database=SimpleNamespace(users=users)))
    assert await service.get_count() == 1_000_000
    users.count_documents.assert_awaited_once_with({'is_banned': {'$ne': True}})
    users.find.assert_not_called()


@pytest.mark.asyncio
async def test_count_failure_propagates_instead_of_claiming_empty_audience():
    users = SimpleNamespace(count_documents=AsyncMock(side_effect=OSError('database offline')))
    service = BroadcastService(SimpleNamespace(database=SimpleNamespace(users=users)))
    with pytest.raises(OSError, match='database offline'):
        await service.get_count()
