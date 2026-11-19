from types import SimpleNamespace
from unittest.mock import AsyncMock, call, patch

import pytest
from pymongo.errors import OperationFailure

from src.infra.mongo.financial_collections import COLLECTIONS, prepare_financial_collections


@pytest.mark.asyncio
async def test_prepares_all_three_collections_without_data_writes():
    db = SimpleNamespace(command=AsyncMock())
    assert await prepare_financial_collections(db) == []
    assert db.command.await_args_list == [call('create', name) for name in COLLECTIONS]


@pytest.mark.asyncio
async def test_existing_collection_is_not_changed_or_treated_as_failure():
    db = SimpleNamespace(command=AsyncMock(side_effect=OperationFailure('NamespaceExists', code=48)))
    assert await prepare_financial_collections(db) == []
    assert db.command.await_count == len(COLLECTIONS)


@pytest.mark.asyncio
async def test_create_conflict_retry_is_bounded_and_other_errors_visible():
    db = SimpleNamespace(command=AsyncMock(side_effect=[
        OperationFailure('conflict', code=112), None,
        OperationFailure('forbidden', code=13),
        OSError('offline'),
    ]))
    with patch('src.infra.mongo.financial_collections.asyncio.sleep', new=AsyncMock()) as wait:
        assert await prepare_financial_collections(db) == ['transactions', 'tickets']
    wait.assert_awaited_once_with(.05)
    assert db.command.await_count == 4


@pytest.mark.asyncio
async def test_create_conflict_stops_after_four_attempts():
    async def create(command, name):
        if name == 'duel_escrows':
            raise OperationFailure('conflict', code=112)
    db = SimpleNamespace(command=AsyncMock(side_effect=create))
    with patch('src.infra.mongo.financial_collections.asyncio.sleep', new=AsyncMock()) as wait:
        assert await prepare_financial_collections(db) == ['duel_escrows']
    assert db.command.await_count == 6
    assert wait.await_count == 3
