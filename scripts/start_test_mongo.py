"""Initialize the localhost-only CI Mongo replica set after docker run."""
import time
from pymongo import MongoClient
from pymongo.errors import PyMongoError

client = MongoClient('mongodb://127.0.0.1:27017/?directConnection=true', serverSelectionTimeoutMS=1000)
for attempt in range(60):
    try:
        client.admin.command('ping')
        break
    except PyMongoError:
        if attempt == 59:
            raise
        time.sleep(1)
try:
    client.admin.command('replSetInitiate', {'_id': 'rs0', 'members': [{'_id': 0, 'host': '127.0.0.1:27017'}]})
except PyMongoError as exc:
    if getattr(exc, 'code', None) != 23:  # AlreadyInitialized
        raise
for attempt in range(60):
    if client.admin.command('hello').get('isWritablePrimary'):
        break
    if attempt == 59:
        raise RuntimeError('Test replica set did not elect a primary')
    time.sleep(1)
client.close()
print('Local test replica set ready')
