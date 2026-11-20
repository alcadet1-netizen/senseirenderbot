#!/usr/bin/env python3
"""Preview or apply one counter-only correction while all writers are stopped.

This is an operator-run maintenance tool, not a bot command. It cannot verify
that old processes, external tools, or financial workers are stopped. Before
applying, an operator must stop *all* writers and take a verified backup. An
incorrect assertion can invalidate the snapshot and the accounting limit.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal

from pymongo import MongoClient
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

from scripts.diagnose_emission import build_report, read_snapshot
from src.services.emission_correction_plan import CorrectionPlanError, make_correction_plan
from src.services.emission_watch import _amount

CORRECTION_ID = 'counter-baseline-v1'
CONFIRM = 'ALL_FINANCIAL_WRITERS_STOPPED_AND_BACKUP_VERIFIED'


def exact_float(number):
    """Fail instead of silently storing a different decimal amount."""
    value = float(number)
    if Decimal(str(value)) != number:
        raise CorrectionPlanError('value cannot be represented safely as a float')
    return value


def run_snapshot(db, session, *, expected_delta, apply=False):
    """Run only in a snapshot transaction, after externally stopping writers."""
    now = datetime.now(timezone.utc)
    full_bank = db.bank.find_one({'_id': 'single'}, session=session)
    if full_bank and full_bank.get('emission_correction_id') == CORRECTION_ID:
        if (full_bank.get('emission_correction_applied') is True
                and _amount(full_bank.get('emission_correction_reserve')) is not None
                and _amount(full_bank.get('total_emitted')) is not None
                and _amount(full_bank.get('burned')) is not None
                and isinstance(full_bank.get('emission_correction_at'), datetime)):
            return {'status': 'already_applied', 'correction_id': CORRECTION_ID}
        raise CorrectionPlanError('correction receipt is incomplete')
    single, legacy, users, events, escrow = read_snapshot(db, session, 0, now)
    report = build_report(single, legacy, users, events, started_at=now,
                          finished_at=datetime.now(timezone.utc), history_days=0, escrow=escrow)
    plan = make_correction_plan(report, full_bank, expected_delta=expected_delta)
    current_after = exact_float(plan['current_after'])
    reserve = exact_float(plan['limit_reserve'])
    # Validate representability of both values and their accounting sum.
    if Decimal(str(current_after)) + Decimal(str(reserve)) != plan['current_before']:
        raise CorrectionPlanError('stored values would change accounted lifetime')
    result = {'status': 'preview' if not apply else 'applied', 'correction_id': CORRECTION_ID,
              **{k: str(v) for k, v in plan.items()}}
    if not apply:
        return result
    changed = db.bank.update_one({
        '_id': 'single', 'coins': full_bank['coins'],
        'total_emitted': full_bank['total_emitted'], 'burned': full_bank['burned'],
        'emission_correction_reserve': {'$exists': False},
        'emission_correction_applied': {'$exists': False},
        'emission_correction_id': {'$exists': False},
    }, {'$set': {
        'total_emitted': current_after,
        'emission_correction_reserve': reserve,
        'emission_correction_applied': True,
        'emission_correction_id': CORRECTION_ID,
        'emission_correction_at': now,
    }}, session=session)
    if changed.matched_count != 1:
        raise CorrectionPlanError('bank changed or correction already exists')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-difference', required=True,
                        help='Difference from a recent report, in Coin (not a connection string).')
    parser.add_argument('--apply', action='store_true', help='Apply after independent operator verification; default is preview only.')
    parser.add_argument('--confirm', default='', help='Required maintenance acknowledgement for --apply.')
    args = parser.parse_args(argv)
    if args.apply and args.confirm != CONFIRM:
        print('Apply refused: explicit maintenance and backup acknowledgement required.', file=sys.stderr)
        return 2
    uri, name = os.environ.get('MONGO_URI'), os.environ.get('MONGO_DB')
    if not uri or not name:
        print('Set MONGO_URI and MONGO_DB in the existing environment; never share them.', file=sys.stderr)
        return 2
    client = None
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=10000, connectTimeoutMS=10000,
                             appname='sensei-emission-correction')
        with client.start_session() as session:
            result = session.with_transaction(
                lambda tx: run_snapshot(client[name], tx, expected_delta=args.expected_difference, apply=args.apply),
                read_concern=ReadConcern('snapshot'), write_concern=WriteConcern('majority'))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        # Never print driver exception text: it can contain connection secrets.
        print(f'Correction failed ({type(exc).__name__}); outcome may be unknown. Verify the receipt before any retry.', file=sys.stderr)
        return 1
    finally:
        if client is not None:
            client.close()


if __name__ == '__main__':
    sys.exit(main())
