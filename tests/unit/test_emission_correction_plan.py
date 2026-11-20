from copy import deepcopy
from decimal import Decimal
import pytest

from src.services.emission_correction_plan import CorrectionPlanError, make_correction_plan


def sample():
    report = {'bank_single': {'present': True, 'coins': '75', 'total_emitted': '120.004', 'burned': '5'},
              'bank_main': {'present': True, 'balance': '0'},
              'users': {'numeric_balance_sum': '25', 'negative_count': 0, 'missing_or_non_numeric_count': 0},
              'duel_escrow': {'held_coins': '0', 'invalid_stakes': 0},
              'calculated': {'ui_total_supply': '100', 'emission_minus_ui_total_supply': '20.004'}}
    return report, {'total_emitted': 120.004, 'burned': 5, 'coins': 75}


def test_preview_keeps_lifetime_and_changes_no_input():
    report, doc = sample()
    before = deepcopy((report, doc))
    plan = make_correction_plan(report, doc, expected_delta='20.00')
    assert plan['current_after'] == Decimal('100.004')
    assert plan['limit_reserve'] == Decimal('20.00')
    assert plan['residual'] == Decimal('0.004')
    assert plan['lifetime_before'] == plan['lifetime_after'] == Decimal('125.004')
    assert (report, doc) == before


@pytest.mark.parametrize('change', ['old', 'negative', 'invalid', 'held', 'mismatch', 'missing', 'changed'])
def test_preview_refuses_unsafe_snapshot(change):
    report, doc = sample()
    if change == 'old': doc['emission_correction_applied'] = True
    if change == 'negative': report['users']['negative_count'] = 1
    if change == 'invalid': report['users']['missing_or_non_numeric_count'] = 1
    if change == 'held': report['duel_escrow']['held_coins'] = '10'
    if change == 'mismatch': doc['total_emitted'] = 120
    if change == 'missing': report['bank_main']['present'] = False
    if change == 'changed': report['calculated']['emission_minus_ui_total_supply'] = '21'
    with pytest.raises(CorrectionPlanError):
        make_correction_plan(report, doc, expected_delta='20.00')


@pytest.mark.parametrize('field,value', [
    ('emission_correction_applied', False),
    ('emission_correction_id', 'unknown'),
    ('emission_correction_at', None),
    ('emission_correction_reserve', 0),
])
def test_preview_refuses_any_partial_correction(field, value):
    report, doc = sample()
    doc[field] = value
    with pytest.raises(CorrectionPlanError):
        make_correction_plan(report, doc, expected_delta='20.00')
