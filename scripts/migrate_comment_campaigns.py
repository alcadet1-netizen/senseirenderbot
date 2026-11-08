"""Idempotent campaign indexes/schema marker; never reads or prints credentials."""
import argparse
import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from src.core.config import settings
from src.infra.mongo.client import MongoClient
from src.services.comment_campaign_service import CommentCampaignService


async def migrate(check_only=False):
    mongo = MongoClient()
    await mongo.connect()
    try:
        hello = await mongo.database.command('hello')
        if not hello.get('logicalSessionTimeoutMinutes') or not (hello.get('setName') or hello.get('msg') == 'isdbgrid'):
            raise RuntimeError('A MongoDB replica set/mongos with transactions is required')
        if not check_only:
            service = CommentCampaignService(SimpleNamespace(settings=settings, mongo_client=mongo))
            await service.ensure_indexes()
            await mongo.database.schema_migrations.update_one({'_id': 'comment_campaign_v1'},
                {'$setOnInsert': {'applied_at': datetime.now(timezone.utc)}}, upsert=True)
        print('Comment campaign database: transaction topology OK; ' + ('check only' if check_only else 'indexes applied'))
    finally:
        await mongo.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    asyncio.run(migrate(args.check))
