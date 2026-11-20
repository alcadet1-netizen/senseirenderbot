from copy import deepcopy
from decimal import Decimal
from types import SimpleNamespace as NS
from unittest.mock import Mock
import pytest

from scripts import prepare_emission_correction as tool
from src.services.emission_correction_plan import CorrectionPlanError


def snapshot():
    return ({'_id': 'single', 'coins': 75, 'total_emitted': 120, 'burned': 5},
            {'_id': 'main', 'balance': 0},
            {'numeric_sum': 25, 'negative_count': 0, 'non_numeric_count': 0}, [],
            {'bets': 0, 'invalid': 0})


def test_preview_and_apply_only_touch_counter_and_reserved_capacity(monkeypatch):
    single, legacy, users, events, escrow = snapshot()
    db = NS(bank=NS(find_one=Mock(return_value=deepcopy(single)), update_one=Mock(return_value=NS(matched_count=1))))
    monkeypatch.setattr(tool, 'read_snapshot', lambda *args: (single, legacy, users, events, escrow))
    result = tool.run_snapshot(db, 'session', expected_delta='20')
    assert result['status'] == 'preview' and Decimal(result['lifetime_after']) == Decimal(result['lifetime_before'])
    db.bank.update_one.assert_not_called()
    result = tool.run_snapshot(db, 'session', expected_delta='20', apply=True)
    assert result['status'] == 'applied'
    query, update = db.bank.update_one.call_args.args
    assert query['coins'] == 75 and query['emission_correction_id'] == {'$exists': False}
    assert update['$set']['total_emitted'] == 100
    assert update['$set']['emission_correction_reserve'] == 20
    assert 'coins' not in update['$set'] and 'burned' not in update['$set']


def test_retry_and_race_fail_closed(monkeypatch):
    single, legacy, users, events, escrow = snapshot()
    db = NS(bank=NS(find_one=Mock(return_value=deepcopy(single)), update_one=Mock(return_value=NS(matched_count=0))))
    monkeypatch.setattr(tool, 'read_snapshot', lambda *args: (single, legacy, users, events, escrow))
    with pytest.raises(CorrectionPlanError):
        tool.run_snapshot(db, 'session', expected_delta='20', apply=True)
    db.bank.find_one.return_value = {'emission_correction_applied': True, 'emission_correction_id': tool.CORRECTION_ID}
    assert tool.run_snapshot(db, 'session', expected_delta='20', apply=True)['status'] == 'already_applied'
    db.bank.update_one.assert_called_once()


def test_apply_requires_explicit_acknowledgement_without_credentials(monkeypatch, capsys):
    monkeypatch.delenv('MONGO_URI', raising=False)
    assert tool.main(['--expected-difference', '20', '--apply']) == 2
    assert 'acknowledgement' in capsys.readouterr().err
