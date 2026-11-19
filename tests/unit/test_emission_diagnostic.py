from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

from bson.decimal128 import Decimal128

from scripts import diagnose_emission as diagnostic

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def report(single, legacy, users):
    return diagnostic.build_report(single, legacy, users, [], started_at=NOW, finished_at=NOW, history_days=0)


def test_report_matches_ui_calculation_without_hiding_discrepancy():
    result = report({'coins': 968485634, 'total_emitted': 971011837, 'emission_cap': 10_000_000_000,
                     'secret': 'never output'}, {'balance': 0}, {'numeric_sum': 2129839, 'count': 1})
    assert result['calculated'] == {'ui_total_supply': '970615473', 'emission_minus_ui_total_supply': '396364'}
    assert 'secret' not in str(result)
    assert result['bank_single']['burned'] is None


def test_missing_invalid_negative_and_decimal_values():
    result = report({'coins': 100.25, 'total_emitted': 105.50}, None,
                    {'numeric_sum': -2, 'negative_sum': -2, 'negative_count': 1})
    assert result['calculated']['ui_total_supply'] == '100.25'
    assert result['calculated']['emission_minus_ui_total_supply'] == '5.25'
    assert not result['bank_main']['present']
    assert result['users']['negative_balance_sum'] == '-2'
    assert report({'coins': 'not a number', 'total_emitted': 1}, None, {})['calculated']['ui_total_supply'] is None
    assert report({'coins': Decimal128('100.25'), 'total_emitted': 105}, None, {})['calculated']['ui_total_supply'] is None
    assert diagnostic.amount(Decimal128('100.25')) == Decimal('100.25')
    assert diagnostic.amount(float('nan')) is None
    assert diagnostic.amount(True) is None
    assert diagnostic.amount(Decimal('1.234')) == Decimal('1.234')


def test_queries_are_read_only_use_same_session_and_no_history_by_default():
    session = object()
    bank = MagicMock()
    bank.find_one.side_effect = [{'coins': 1}, None]
    users = MagicMock()
    users.aggregate.return_value = [{'numeric_sum': 4}]
    transactions = MagicMock()
    db = SimpleNamespace(bank=bank, users=users, transactions=transactions)
    diagnostic.read_snapshot(db, session, 0, NOW)
    assert bank.find_one.call_count == 2
    assert all(call.kwargs['session'] is session for call in bank.find_one.call_args_list)
    assert users.aggregate.call_args.kwargs['session'] is session
    transactions.aggregate.assert_not_called()
    assert set(bank.method_calls[i][0] for i in range(2)) == {'find_one'}


def test_history_uses_allowlisted_aggregate_only_and_same_snapshot():
    session = object()
    bank, users, tx = MagicMock(), MagicMock(), MagicMock()
    bank.find_one.return_value = None
    users.aggregate.return_value = []
    tx.aggregate.return_value = [{'_id': {'day': '2025-12-31', 'type': 'burn'},
                                  'amount': -10, 'count': 1, 'non_numeric_amounts': 0}]
    _, _, _, result = diagnostic.read_snapshot(SimpleNamespace(bank=bank, users=users, transactions=tx), session, 30, NOW)
    assert result == [{'day_utc': '2025-12-31', 'type': 'burn', 'count': 1, 'signed_amount': '-10', 'non_numeric_amounts': 0}]
    assert tx.aggregate.call_args.kwargs['session'] is session
    pipeline = tx.aggregate.call_args.args[0]
    assert pipeline[0]['$match']['tx_type']['$in'] == list(diagnostic.TX_TYPES)
    assert all('$out' not in stage and '$merge' not in stage for stage in pipeline)


def test_failure_does_not_print_connection_secrets(monkeypatch, capsys):
    monkeypatch.setenv('MONGO_URI', 'mongodb://private-secret')
    monkeypatch.setenv('MONGO_DB', 'private-db')
    monkeypatch.setattr(diagnostic, 'MongoClient', lambda *a, **kw: (_ for _ in ()).throw(ValueError('private-secret')))
    assert diagnostic.main([]) == 1
    result = capsys.readouterr()
    assert result.out == ''
    assert 'private-secret' not in result.err and 'private-db' not in result.err
