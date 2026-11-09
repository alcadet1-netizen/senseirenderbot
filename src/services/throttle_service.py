"""Mongo fixed-window limiter. TTL is cleanup, never the expiry decision."""
import logging
import time
from datetime import datetime, timezone, timedelta

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

logger = logging.getLogger(__name__)


class ThrottleService:
    def __init__(self, mongo_client):
        self.collection = mongo_client.database.throttle

    async def ensure_indexes(self):
        await self.collection.create_index([('expiry', 1)], expireAfterSeconds=0)

    async def throttle(self, key: str, limit_seconds: int, scope: str = 'default') -> bool:
        if limit_seconds <= 0:
            return True
        stamp = time.time()
        now = datetime.fromtimestamp(stamp, timezone.utc)
        try:
            # BSON type bracketing makes date and legacy numeric expiry comparisons
            # independent. An active document fails the predicate -> duplicate _id.
            await self.collection.find_one_and_update(
                {'_id': f'{scope}:{key}', '$or': [
                    {'expiry': {'$lte': now}}, {'expiry': {'$lte': stamp}},
                    {'expiry': {'$exists': False}}]},
                {'$set': {'expiry': now + timedelta(seconds=limit_seconds)}},
                upsert=True, return_document=ReturnDocument.AFTER)
            return True
        except DuplicateKeyError:
            return False
        except Exception as exc:
            # Preserve existing fail-open policy for non-financial throttling.
            logger.error('Throttle unavailable error_type=%s', type(exc).__name__)
            return True
