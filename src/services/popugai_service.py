"""Per-chat Telegram media references and reply probability, Mongo only."""
import hashlib
import math
from datetime import datetime, timedelta, timezone
from pymongo.errors import DuplicateKeyError
from typing import Optional, Tuple


class PopugaiService:
    def __init__(self, mongo_client):
        self.db = mongo_client.database
        self.chances = self.db.popugai_chances
        self.media = self.db.popugai_media
        self.decisions = self.db.popugai_decisions

    async def ensure_indexes(self):
        await self.media.create_index('chat_id')
        await self.decisions.create_index('expires_at', expireAfterSeconds=0)

    async def get_reply_chance(self, chat_id: int) -> float:
        doc = await self.chances.find_one({'_id': chat_id})
        if doc is None:
            doc = await self.chances.find_one({'chat_id': chat_id})
        value = float((doc or {}).get('chance', 0))
        return max(0.0, min(1.0, value)) if math.isfinite(value) else 0.0

    async def set_reply_chance(self, chat_id: int, chance: float) -> None:
        if not math.isfinite(chance):
            raise ValueError('Chance must be finite')
        legacy = await self.chances.find_one({'chat_id': chat_id})
        key = legacy['_id'] if legacy else chat_id
        await self.chances.update_one({'_id': key},
            {'$set': {'chat_id': chat_id, 'chance': max(0.0, min(1.0, chance))}}, upsert=True)

    async def add_media(self, chat_id: int, media_type: str, file_id: str, file_unique_id=None) -> None:
        if media_type not in ('sticker', 'gif') or not file_id:
            return
        identity = file_unique_id or file_id
        key = hashlib.sha256(f'{chat_id}:{media_type}:{identity}'.encode()).hexdigest()
        # Atomic dedup even across workers; refresh the usable Telegram file_id.
        await self.media.update_one({'_id': key}, {'$set': dict(
            chat_id=chat_id, media_type=media_type, file_id=file_id)}, upsert=True)

    async def get_random_media(self, chat_id: int) -> Optional[Tuple[str, str]]:
        # Sample inside Mongo instead of loading an unbounded chat history.
        items = await self.media.aggregate([
            {'$match': {'chat_id': chat_id, 'media_type': {'$in': ['sticker', 'gif']}}},
            {'$sample': {'size': 1}}]).to_list(length=1)
        return (items[0]['media_type'], items[0]['file_id']) if items else None

    async def reserve_reply(self, chat_id, message_id):
        # At-most-once attempt across workers/re-delivery; never release on timeout.
        now = datetime.now(timezone.utc)
        try:
            await self.decisions.insert_one(dict(_id=f'{chat_id}:{message_id}',
                expires_at=now+timedelta(days=7)))
            return True
        except DuplicateKeyError:
            return False
