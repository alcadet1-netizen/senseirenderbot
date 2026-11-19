#!/usr/bin/env python3
"""Read-only, aggregate-only diagnostic for SenseiCoin accounting.

Requires MONGO_URI and MONGO_DB in the environment, and MongoDB 5.0+ with
snapshot reads. Never initializes application services or writes to MongoDB.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from bson.decimal128 import Decimal128
from pymongo import MongoClient
from pymongo.read_preferences import ReadPreference

# Fixed allowlist: no descriptions, user identifiers, or arbitrary type names.
TX_TYPES = (
    "burn", "ban_confiscation", "duel_escrow", "duel_bet_payout",
    "duel_bet_refund", "dojo_task", "dojo_profile_task", "game_win",
    "admin_grant", "daily_bonus", "message_reward", "slots_win", "slots_bet",
)


def amount(value):
    """Preserve numeric precision; invalid/missing values remain unknown."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        if isinstance(value, Decimal128):
            value = value.to_decimal()
        if not isinstance(value, (int, float, Decimal)):
            return None
        number = Decimal(str(value))
        return number if number.is_finite() else None
    except (ValueError, TypeError, InvalidOperation):
        return None


def as_text(value):
    return format(value, 'f') if value is not None else None


def stats_amount(value):
    """Only compare values the current stats service can coerce with float()."""
    if isinstance(value, Decimal128):
        return None
    return amount(value)


def bank_fields(doc, fields):
    # Only explicitly allowed non-identifying fields may leave the database.
    result = {field: as_text(amount((doc or {}).get(field))) for field in fields}
    return {"present": doc is not None, **result}


def build_report(single, legacy, users, events, *, started_at, finished_at, history_days):
    single_info = bank_fields(single, ('coins', 'total_emitted', 'emission_cap', 'burned'))
    legacy_info = bank_fields(legacy, ('balance',))
    player_total = amount(users.get('numeric_sum', 0))
    player_total_for_ui = stats_amount(users.get('numeric_sum', 0))
    single_balance = stats_amount((single or {}).get('coins'))
    legacy_balance = stats_amount((legacy or {}).get('balance'))
    emitted = stats_amount((single or {}).get('total_emitted'))
    # Match StatsService's current displayed computation, including clamping.
    # A missing document is equivalent to zero; a malformed value is unknown.
    if single is None:
        single_balance = Decimal(0)
    if legacy is None:
        legacy_balance = Decimal(0)
    if player_total_for_ui is not None and single_balance is not None and legacy_balance is not None:
        calculated = max(Decimal(0), player_total_for_ui) + max(Decimal(0), single_balance) + max(Decimal(0), legacy_balance)
    else:
        calculated = None
    difference = emitted - calculated if emitted is not None and calculated is not None else None
    return {
        'schema_version': 1,
        'snapshot_requested_utc': started_at.isoformat(),
        'snapshot_read_completed_utc': finished_at.isoformat(),
        'consistency': 'MongoDB snapshot session; reads share one snapshot',
        'bank_single': single_info,
        'bank_main': legacy_info,
        'users': {
            'count': users.get('count', 0),
            'numeric_balance_sum': as_text(player_total),
            'positive_balance_sum': as_text(amount(users.get('positive_sum', 0))),
            'negative_balance_sum': as_text(amount(users.get('negative_sum', 0))),
            'positive_count': users.get('positive_count', 0),
            'negative_count': users.get('negative_count', 0),
            'missing_or_non_numeric_count': users.get('non_numeric_count', 0),
        },
        'calculated': {
            'ui_total_supply': as_text(calculated),
            'emission_minus_ui_total_supply': as_text(difference),
        },
        'transaction_history': {
            'requested_days': history_days,
            'daily_aggregates': events,
            'warning': 'Journal is incomplete; totals are not proof of active escrow or of the cause.',
        },
        'limitations': [
            'Active duels are stored in the bot process, not a durable escrow ledger; their current total cannot be established from this snapshot.',
            'Emission reservations/releases and some older operations do not have a complete reliable transaction journal.',
            'A read snapshot may capture multi-step non-transactional operations in progress; do not infer cause or correct balances from one report.',
            'Current UI calculations clamp negative component totals; inspect negative and non-numeric balances separately. Comparison is null when input types cannot be safely compared to UI coercion.',
            'No individual records, user IDs, transaction descriptions, connection details or credentials are included.',
        ],
    }


def read_snapshot(db, session, history_days, now):
    single = db.bank.find_one({'_id': 'single'}, {'coins': 1, 'total_emitted': 1, 'emission_cap': 1, 'burned': 1}, session=session)
    legacy = db.bank.find_one({'_id': 'main'}, {'balance': 1}, session=session)
    is_num = {'$isNumber': '$coins'}
    users_pipeline = [{'$group': {
        '_id': None,
        'count': {'$sum': 1},
        'numeric_sum': {'$sum': {'$cond': [is_num, '$coins', 0]}},
        'positive_sum': {'$sum': {'$cond': [{'$and': [is_num, {'$gt': ['$coins', 0]}]}, '$coins', 0]}},
        'negative_sum': {'$sum': {'$cond': [{'$and': [is_num, {'$lt': ['$coins', 0]}]}, '$coins', 0]}},
        'positive_count': {'$sum': {'$cond': [{'$and': [is_num, {'$gt': ['$coins', 0]}]}, 1, 0]}},
        'negative_count': {'$sum': {'$cond': [{'$and': [is_num, {'$lt': ['$coins', 0]}]}, 1, 0]}},
        'non_numeric_count': {'$sum': {'$cond': [is_num, 0, 1]}},
    }}]
    rows = list(db.users.aggregate(users_pipeline, session=session, maxTimeMS=120000))
    events = []
    if history_days:
        pipeline = [
            {'$match': {'created_at': {'$gte': now - timedelta(days=history_days), '$lt': now}, 'tx_type': {'$in': list(TX_TYPES)}}},
            {'$group': {'_id': {'day': {'$dateToString': {'format': '%Y-%m-%d', 'date': '$created_at', 'timezone': 'UTC'}}, 'type': '$tx_type'},
                        'count': {'$sum': 1}, 'amount': {'$sum': {'$cond': [{'$isNumber': '$coins_change'}, '$coins_change', 0]}},
                        'non_numeric_amounts': {'$sum': {'$cond': [{'$isNumber': '$coins_change'}, 0, 1]}}}},
            {'$sort': {'_id.day': 1, '_id.type': 1}},
        ]
        for row in db.transactions.aggregate(pipeline, session=session, maxTimeMS=120000):
            events.append({'day_utc': row['_id']['day'], 'type': row['_id']['type'],
                           'count': row['count'], 'signed_amount': as_text(amount(row['amount'])),
                           'non_numeric_amounts': row['non_numeric_amounts']})
    return single, legacy, rows[0] if rows else {}, events


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--history-days', type=int, default=0, choices=range(0, 91), metavar='0..90',
                        help='Optional UTC daily transaction aggregates for the last N days (default: 0).')
    args = parser.parse_args(argv)
    uri, db_name = os.environ.get('MONGO_URI'), os.environ.get('MONGO_DB')
    if not uri or not db_name:
        print('Set MONGO_URI and MONGO_DB in the local environment; do not share the URI.', file=sys.stderr)
        return 2
    client = None
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=10000, connectTimeoutMS=10000,
                             appname='sensei-emission-readonly-diagnostic', read_preference=ReadPreference.PRIMARY)
        started = datetime.now(timezone.utc)
        with client.start_session(snapshot=True) as session:
            single, legacy, users, events = read_snapshot(client[db_name], session, args.history_days, started)
        report = build_report(single, legacy, users, events, started_at=started,
                              finished_at=datetime.now(timezone.utc), history_days=args.history_days)
        print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except Exception as exc:
        # Exception strings can contain hosts, usernames, URI parameters or data.
        print(f'Diagnostic failed ({type(exc).__name__}); no report was produced. Check permissions, connectivity, snapshot-read support and timeouts locally.', file=sys.stderr)
        return 1
    finally:
        if client is not None:
            client.close()


if __name__ == '__main__':
    sys.exit(main())
