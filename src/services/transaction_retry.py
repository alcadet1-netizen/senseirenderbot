"""Narrow retry for a first-use MongoDB collection-creation race."""
import asyncio

from pymongo.errors import OperationFailure


class _NamespaceCreationConflict(Exception):
    pass


def _is_namespace_creation_conflict(exc):
    # This is a pre-commit callback failure, not an unknown commit result.
    message = str(exc).casefold()
    return (exc.code == 112 and 'collection namespace' in message
            and 'is already in use' in message
            and 'please retry your operation or multi-document transaction' in message)


async def retry_initial_namespace(transaction, mongo, callback, *, attempts=4):
    """Retry only a specifically identified collection creation race.

    Wrapping the callback confines recognition to errors before commit. Motor's
    with_transaction must abort that callback before this wrapper can retry;
    errors from abort or commit are never reclassified here. Operations in the
    callback must have the same retry safety required by with_transaction.
    """
    if attempts < 1:
        raise ValueError('attempts must be positive')

    async def guarded(session):
        try:
            return await callback(session)
        except OperationFailure as exc:
            if _is_namespace_creation_conflict(exc):
                raise _NamespaceCreationConflict() from exc
            raise

    for attempt in range(attempts):
        try:
            return await transaction(mongo, guarded)
        except _NamespaceCreationConflict as exc:
            if attempt + 1 == attempts:
                raise exc.__cause__ from exc
            await asyncio.sleep(0.025 * (2 ** attempt))
