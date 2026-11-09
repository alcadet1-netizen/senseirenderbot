"""Per-chat Telegram media references and reply probability, Mongo only."""
import hashlib
import math
from typing import Optional, Tuple


class PopugaiService:
    def __init__(self, mongo_client):
        self.db = mongo_client.database
        self.chances = self.db.popugai_chances
        self.media = self.db.popugai_media

    async def ensure_indexes(self):
        await self.media.create_index('chat_id')

    async def get_reply_chance(self, chat_id: int) -> float:
        doc = await self.chances.find_one({'chat_id': chat_id})
        value = float((doc or {}).get('chance', 0))
        return max(0.0, min(1.0, value)) if math.isfinite(value) else 0.0

    async def set_reply_chance(self, chat_id: int, chance: float) -> None:
        if not math.isfinite(chance):
            raise ValueError('Chance must be finite')
        await self.chances.update_one({'chat_id': chat_id},
            {'$set': {'chance': max(0.0, min(1.0, chance))}}, upsert=True)

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
