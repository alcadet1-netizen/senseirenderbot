"""Offline counter correction on a disposable replica set; no production data."""
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from pymongo import MongoClient
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

from scripts.prepare_emission_correction import run_snapshot


def test_counter_correction_is_one_shot_and_preserves_balances_and_limit():
    uri = os.environ.get('CAMPAIGN_TEST_MONGO_URI')
    if not uri:
        pytest.skip('MongoDB replica set required')
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    name = 'sensei_counter_test_' + uuid.uuid4().hex
    db = client[name]
    try:
        db.bank.insert_many([{'_id': 'single', 'coins': 75, 'total_emitted': 120, 'burned': 5, 'emission_cap': 10_000_000_000},
                             {'_id': 'main', 'balance': 0}])
        db.users.insert_one({'id': 7, 'coins': 25})
        # Avoid Mongo's concurrent first-creation conflicts; application startup
        # also precreates this namespace before running financial operations.
        db.create_collection('duel_escrows')
        def apply():
            with client.start_session() as session:
                return session.with_transaction(lambda s: run_snapshot(db, s, expected_delta='20', apply=True),
                    read_concern=ReadConcern('snapshot'), write_concern=WriteConcern('majority'))
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: apply(), range(2)))
        assert sorted(r['status'] for r in results) == ['already_applied', 'applied']
        bank = db.bank.find_one({'_id': 'single'})
        assert bank['coins'] == 75 and bank['burned'] == 5
        assert bank['total_emitted'] == 100 and bank['emission_correction_reserve'] == 20
        assert bank['total_emitted'] + bank['burned'] + bank['emission_correction_reserve'] == 125
        assert db.users.find_one({'id': 7})['coins'] == 25
        assert apply()['status'] == 'already_applied'
    finally:
        client.drop_database(name)
        client.close()
