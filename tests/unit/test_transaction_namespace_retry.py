from unittest.mock import AsyncMock

import pytest
from pymongo.errors import OperationFailure

from src.services.transaction_retry import retry_initial_namespace


def namespace_conflict():
    return OperationFailure("Caused by :: Collection namespace 'db.c' is already in use. :: "
                            'Please retry your operation or multi-document transaction.', code=112)


@pytest.mark.asyncio
async def test_callback_namespace_conflict_retries_after_transaction_abort():
    callback = AsyncMock(side_effect=[namespace_conflict(), 'committed'])
    async def transaction(mongo, guarded):
        return await guarded('session')
    assert await retry_initial_namespace(transaction, None, callback) == 'committed'
    assert callback.await_count == 2


@pytest.mark.asyncio
async def test_callback_namespace_conflict_is_bounded():
    callback = AsyncMock(side_effect=namespace_conflict())
    async def transaction(mongo, guarded):
        return await guarded('session')
    with pytest.raises(OperationFailure) as error:
        await retry_initial_namespace(transaction, None, callback, attempts=2)
    assert error.value.code == 112
    assert callback.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize('error', [OperationFailure('write conflict', code=112),
                                   OperationFailure('collection namespace is already in use', code=13),
                                   OSError('network')])
async def test_other_callback_errors_not_retried(error):
    callback = AsyncMock(side_effect=error)
    async def transaction(mongo, guarded):
        return await guarded('session')
    with pytest.raises(type(error)):
        await retry_initial_namespace(transaction, None, callback)
    callback.assert_awaited_once()


@pytest.mark.asyncio
async def test_commit_or_abort_error_never_retries_even_if_text_matches():
    callback = AsyncMock(return_value='would commit')
    async def transaction(mongo, guarded):
        await guarded('session')
        raise namespace_conflict()  # failure outside the callback, e.g. commit
    with pytest.raises(OperationFailure):
        await retry_initial_namespace(transaction, None, callback)
    callback.assert_awaited_once()
