"""Small durable local ingress queue; mount its directory on persistent storage."""
import asyncio
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite


class CampaignInbox:
    def __init__(self, path, bot_id):
        if not path.strip() or path == ':memory:':
            raise ValueError('Campaign inbox requires a persistent filesystem path')
        self.path = path
        self.bot_id = bot_id
        self.db = None
        self.lock = asyncio.Lock()

    async def open(self):
        Path(self.path).parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db = await aiosqlite.connect(self.path)
        Path(self.path).chmod(0o600)
        await self.db.execute('PRAGMA journal_mode=WAL')
        await self.db.execute('PRAGMA synchronous=FULL')
        await self.db.execute('PRAGMA busy_timeout=5000')
        await self.db.execute('CREATE TABLE IF NOT EXISTS campaign_inbox '
            '(bot_id INTEGER NOT NULL, update_id INTEGER NOT NULL, payload TEXT NOT NULL, '
            'PRIMARY KEY(bot_id,update_id))')
        await self.db.execute('CREATE TABLE IF NOT EXISTS campaign_deleted_inbox '
            '(bot_id INTEGER NOT NULL, chat_id INTEGER NOT NULL, message_id INTEGER NOT NULL, '
            'PRIMARY KEY(bot_id,chat_id,message_id))')
        await self.db.execute('CREATE TABLE IF NOT EXISTS campaign_inbox_identity (id INTEGER PRIMARY KEY, value TEXT NOT NULL)')
        await self.db.execute('INSERT OR IGNORE INTO campaign_inbox_identity VALUES(1,?)', (uuid.uuid4().hex,))
        async with self.db.execute('SELECT value FROM campaign_inbox_identity WHERE id=1') as cursor:
            self.identity = (await cursor.fetchone())[0]
        await self.db.commit()

    @asynccontextmanager
    async def settlement_barrier(self):
        # Lock both this connection and other processes sharing the SQLite file.
        # No admitted insert/ack may interleave pending-check and Mongo sealing.
        async with self.lock:
            try:
                await self.write('BEGIN IMMEDIATE')
                yield not await self._pending()
            finally:
                await self.db.rollback()

    async def write(self, sql, parameters=()):
        # Another process may be holding the settlement barrier. Busy is not
        # an ingress failure: retain the update and retry until lock release.
        while True:
            try:
                return await self.db.execute(sql, parameters)
            except aiosqlite.OperationalError as exc:
                if getattr(exc, 'sqlite_errorcode', None) not in (5, 6):
                    raise
                await asyncio.sleep(.05)

    async def put(self, event):
        async with self.lock:
            await self.write('INSERT OR IGNORE INTO campaign_inbox VALUES(?,?,?)',
                (self.bot_id, event.update_id, event.model_dump_json(exclude_none=True)))
            await self.db.commit()

    async def deleted(self, chat_id, message_id):
        async with self.lock:
            await self.write('INSERT OR IGNORE INTO campaign_deleted_inbox VALUES(?,?,?)',
                (self.bot_id, chat_id, message_id))
            await self.db.commit()

    async def deletion_batch(self, size):
        async with self.lock:
            async with self.db.execute('SELECT chat_id,message_id FROM campaign_deleted_inbox WHERE bot_id=? LIMIT ?',
                    (self.bot_id,size)) as cursor:
                return await cursor.fetchall()


    async def ack_deletion(self, chat_id, message_id):
        async with self.lock:
            await self.write('DELETE FROM campaign_deleted_inbox WHERE bot_id=? AND chat_id=? AND message_id=?',
                (self.bot_id,chat_id,message_id))
            await self.db.commit()


    async def batch(self, size):
        async with self.lock:
            async with self.db.execute('SELECT update_id,payload FROM campaign_inbox '
                    'WHERE bot_id=? ORDER BY update_id LIMIT ?', (self.bot_id, size)) as cursor:
                return await cursor.fetchall()


    async def ack(self, update_id):
        async with self.lock:
            await self.write('DELETE FROM campaign_inbox WHERE bot_id=? AND update_id=?', (self.bot_id, update_id))
            await self.db.commit()


    async def pending(self):
        async with self.lock:
            return await self._pending()

    async def _pending(self):
        async with self.db.execute('SELECT 1 FROM campaign_inbox WHERE bot_id=? LIMIT 1', (self.bot_id,)) as cursor:
            if await cursor.fetchone() is not None:
                return True
        async with self.db.execute('SELECT 1 FROM campaign_deleted_inbox WHERE bot_id=? LIMIT 1', (self.bot_id,)) as cursor:
            return await cursor.fetchone() is not None

    async def close(self):
        async with self.lock:
            if self.db:
                await self.db.close()
                self.db = None
