"""Prepare empty collection namespaces before financially sensitive work.

Only missing collections are created. No documents, indexes, balances, or
transactions are edited. A failure is reported; callers must not infer that
financial operations are safe solely because this preparation was attempted.
"""
import asyncio
import logging

from pymongo.errors import OperationFailure

logger = logging.getLogger(__name__)

# Collections implicated in the reproduced first-use duel/exchange race.
COLLECTIONS = ('duel_escrows', 'transactions', 'tickets')


async def prepare_financial_collections(db):
    """Create namespaces outside transactions before polling or recovery.

    create is safe to repeat and does not modify an existing collection. A
    namespace conflict during *this create command* is safe to retry; this is
    deliberately not a retry of a money transaction or its commit.
    """
    failed = []
    for name in COLLECTIONS:
        for attempt in range(4):
            try:
                await db.command('create', name)
            except OperationFailure as exc:
                if exc.code == 48:  # NamespaceExists, including a concurrent creator
                    break
                if exc.code == 112 and attempt < 3:
                    await asyncio.sleep(0.05 * (2 ** attempt))
                    continue
                logger.warning('Financial collection preparation failed collection=%s error_type=%s code=%s',
                               name, type(exc).__name__, exc.code)
                failed.append(name)
                break
            except Exception as exc:
                logger.warning('Financial collection preparation failed collection=%s error_type=%s',
                               name, type(exc).__name__)
                failed.append(name)
                break
            else:
                break
    return failed
