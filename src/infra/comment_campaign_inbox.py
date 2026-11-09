"""Mongo-only durable ingress. All mutations and sealing share a write fence."""
import uuid
from pymongo import ReturnDocument


class CampaignInbox:
    def __init__(self, db, bot_id, transaction):
        self.db, self.bot_id, self.transaction = db, bot_id, transaction
        self.key = f'campaign_inbox:{bot_id}'
        self.updates = db.campaign_inbox_updates
        self.deletions = db.campaign_inbox_deletions

    async def open(self):
        await self.updates.create_index([('bot_id', 1), ('update_id', 1)], unique=True)
        await self.deletions.create_index([('bot_id', 1), ('chat_id', 1), ('message_id', 1)], unique=True)
        # Keep the pre-existing identity; old local backlog is explicitly retired
        # by the operator, never reset Mongo campaigns or financial records.
        async def initialize(tx):
            row = await self.db.settings.find_one_and_update({'_id': self.key},
                {'$setOnInsert': {'identity': uuid.uuid4().hex},
                 '$set': {'backend': 'mongodb', 'schema_version': 2}, '$inc': {'revision': 1}},
                upsert=True, return_document=ReturnDocument.AFTER, session=tx)
            return row['identity']
        self.identity = await self.transaction(initialize)

    async def fence(self, tx):
        await self.db.settings.update_one({'_id': self.key}, {'$inc': {'revision': 1}}, session=tx)

    async def mutate(self, collection, key, row=None, generation=None, replace=False):
        async def apply(tx):
            await self.fence(tx)
            if row is None:
                query = {'_id': key}
                if generation is not None:
                    query['generation'] = generation
                await collection.delete_many(query, session=tx)
            else:
                await collection.update_one({'_id': key}, {'$set' if replace else '$setOnInsert': row}, upsert=True, session=tx)
        await self.transaction(apply)

    async def put(self, event):
        await self.mutate(self.updates, f'{self.bot_id}:{event.update_id}',
            dict(bot_id=self.bot_id, update_id=event.update_id, payload=event.model_dump_json(exclude_none=True)))

    async def deleted(self, chat_id, message_id):
        await self.mutate(self.deletions, f'{self.bot_id}:{chat_id}:{message_id}',
            dict(bot_id=self.bot_id, chat_id=chat_id, message_id=message_id, generation=uuid.uuid4().hex), replace=True)

    async def batch(self, size):
        rows = await self.updates.find({'bot_id': self.bot_id}).sort('update_id', 1).limit(size).to_list(length=size)
        return [(r['update_id'], r['payload']) for r in rows]

    async def deletion_batch(self, size):
        rows = await self.deletions.find({'bot_id': self.bot_id}).limit(size).to_list(length=size)
        return [(r['chat_id'], r['message_id'], r['generation']) for r in rows]

    async def ack(self, update_id):
        await self.mutate(self.updates, f'{self.bot_id}:{update_id}')

    async def ack_deletion(self, chat_id, message_id, generation):
        await self.mutate(self.deletions, f'{self.bot_id}:{chat_id}:{message_id}', generation=generation)

    async def pending(self, tx=None):
        return bool(await self.updates.find_one({'bot_id': self.bot_id}, session=tx)
            or await self.deletions.find_one({'bot_id': self.bot_id}, session=tx))

    async def seal_if_empty(self, callback):
        async def seal(tx):
            await self.fence(tx)
            if await self.pending(tx):
                return False
            await callback(tx)
            return True
        return await self.transaction(seal)

    async def close(self):
        # MongoClient lifecycle belongs to the container.
        pass
