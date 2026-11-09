"""Small explicit attention model, NOT a biological connectome or language model."""
import hashlib
import re
import secrets
import unicodedata
from datetime import datetime, timezone, timedelta

from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

TOPICS = {
    'technology': (r'\b(?:код|бот|программ\w*|нейрон\w*|виджет\w*|технолог\w*)\b',
                   'А что здесь хочется улучшить в первую очередь?', 'Сенсей слушает. Иногда хорошее решение начинается с простого вопроса.'),
    'games': (r'\b(?:игр\w*|ежа|ёж\w*|катан\w*|поглаж\w*)\b',
              'А что в этой игре нравится больше всего?', 'Главное — удовольствие от игры, а не только счётчик.'),
    'crypto': (r'\b(?:крипт\w*|биткоин\w*|грам|gram|bitcoin|ton)\b',
               'А что привлекло внимание: технология или обсуждение вокруг неё?', 'Сенсей наблюдает. Громкое обсуждение — ещё не доказательство.'),
}
# Filter likely credentials/contact data, not conversation topics or profanity.
PRIVATE = re.compile(r'(?i)(?:seed\s*(?:phrase|фраз)|парол[ья]\s*[:=]|api[_ -]?key\s*[:=]|sk-[a-z0-9]{12,}|\d{7,})')


def features(message):
    text = unicodedata.normalize('NFKC', message.text or '')
    user = message.from_user
    if (not user or user.is_bot or message.sender_chat or message.is_automatic_forward
            or getattr(message, 'forward_origin', None)
            or any(e.type in {'bot_command', 'email', 'phone_number'}
                   for e in (getattr(message, 'entities', None) or []))
            or message.chat.type not in {'group', 'supergroup'} or not text.strip()
            or text.lstrip().startswith('/') or PRIVATE.search(text)):
        return None
    digest = hashlib.sha256(' '.join(text.lower().split()).encode()).hexdigest()
    for topic, (pattern, question, remark) in TOPICS.items():
        if re.search(pattern, text, re.I):
            return topic, digest, question, remark
    return 'general', digest, '', ''


class FlyService:
    def __init__(self, container, *, clock=None, roll=None):
        self.container = container
        self.db = container.mongo_client.database
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.roll = roll or (lambda: secrets.randbelow(10000))

    async def ensure_indexes(self):
        await self.db.fly_decisions.create_index("expires_at", expireAfterSeconds=0)

    async def transaction(self, callback):
        async with await self.db.client.start_session() as tx:
            return await tx.with_transaction(callback, read_concern=ReadConcern('snapshot'),
                                             write_concern=WriteConcern('majority'))

    async def reserve(self, message):
        signals = features(message)
        if not signals or not self.container.settings.fly_reactions_enabled:
            return None
        topic, digest, question, remark = signals
        now = self.clock()
        # Sample once outside transaction retries; no topic allowlist.
        sampled = self.roll() < 150
        async def choose(tx):
            cfg = await self.db.fly_settings.find_one({'_id': message.chat.id}, session=tx)
            if not cfg or not cfg.get('enabled'):
                return None
            key = f'{message.chat.id}:{message.message_id}'
            if await self.db.fly_decisions.find_one({'_id': key}, session=tx):
                return None
            state = await self.db.fly_chat_state.find_one({'_id': message.chat.id}, session=tx) or {}
            person = await self.db.fly_user_state.find_one({'_id': f'{message.chat.id}:{message.from_user.id}'}, session=tx) or {}
            novel = bool(state.get('topic') and state['topic'] != topic)
            day = now.date().isoformat()
            count = state.get('count', 0) if state.get('day') == day else 0
            # Bounded, time-decaying habituation: A/B/A must not bypass repetition suppression.
            recent = [item for item in state.get('recent', [])
                      if now.timestamp() - item['at'] < 21600]
            repeated = any(item['digest'] == digest for item in recent)
            # Preserve immediate-repeat suppression for pre-history state during rollout.
            if 'recent' not in state:
                repeated = repeated or digest == state.get('digest')
            allowed = (sampled and not repeated and count < 8
                and now.timestamp()-state.get('last_reply', 0) >= 900
                and now.timestamp()-person.get('last_reply', 0) >= 21600)
            recent = [item for item in recent if item['digest'] != digest]
            recent.append({'digest': digest, 'at': now.timestamp()})
            updates = {'topic': topic, 'digest': digest, 'day': day, 'count': count,
                       'recent': recent[-32:]}
            if allowed:
                updates.update(count=count+1, last_reply=now.timestamp())
                await self.db.fly_user_state.update_one({'_id': f'{message.chat.id}:{message.from_user.id}'},
                    {'$set': {'last_reply': now.timestamp()}}, upsert=True, session=tx)
            # Every decision writes this document: concurrent messages serialize limits.
            await self.db.fly_chat_state.update_one({'_id': message.chat.id}, {'$set': updates}, upsert=True, session=tx)
            await self.db.fly_decisions.insert_one(dict(_id=key, created_at=now, expires_at=now+timedelta(days=7),
                topic=topic, novelty=novel, repeated=repeated, selected=allowed, status='reserved' if allowed else 'silent'), session=tx)
            return (key, question if novel else remark) if allowed else None
        return await self.transaction(choose)
