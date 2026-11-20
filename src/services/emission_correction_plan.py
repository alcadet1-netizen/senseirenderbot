"""Read-only preflight for a possible emission-counter correction.

This module deliberately has no write or apply operation. The report must be
from a single consistent snapshot. A plan is not authorization or proof that
history is complete; financial writers must be quiesced before any future apply.
"""
from decimal import Decimal, ROUND_HALF_UP

from scripts.diagnose_emission import amount
from src.core.constants import TOTAL_EMISSION_CAP


class CorrectionPlanError(ValueError):
    """The supplied snapshot is not safe enough even to preview a correction."""


def make_correction_plan(report, bank_doc, *, expected_delta):
    if not isinstance(report, dict) or not isinstance(bank_doc, dict):
        raise CorrectionPlanError('snapshot unavailable')
    single = report.get('bank_single') or {}
    legacy = report.get('bank_main') or {}
    users = report.get('users') or {}
    escrow = report.get('duel_escrow') or {}
    calculated = report.get('calculated') or {}
    if not single.get('present') or not legacy.get('present'):
        raise CorrectionPlanError('bank account missing')
    if any(key in bank_doc for key in ('emission_correction_applied', 'emission_correction_reserve',
                                        'emission_correction_id', 'emission_correction_at')):
        raise CorrectionPlanError('correction already applied or incomplete correction fields exist')
    if users.get('negative_count') != 0 or users.get('missing_or_non_numeric_count') != 0:
        raise CorrectionPlanError('user balances require investigation')
    # The report serializes monetary values as strings; parse only known fields.
    def number(value):
        try:
            d = Decimal(str(value))
            return d if d.is_finite() and d >= 0 else None
        except Exception:
            return None
    if escrow.get('invalid_stakes') != 0 or number(escrow.get('held_coins')) != 0:
        raise CorrectionPlanError('duel stakes require investigation')
    current = number(single.get('total_emitted'))
    supply = number(calculated.get('ui_total_supply'))
    delta = number(calculated.get('emission_minus_ui_total_supply'))
    burned = number(single.get('burned'))
    bank_balance = number(single.get('coins'))
    legacy_balance = number(legacy.get('balance'))
    player_balance = number(users.get('numeric_balance_sum'))
    expected = number(expected_delta)
    if any(v is None for v in (current, supply, delta, burned, bank_balance, legacy_balance, player_balance, expected)):
        raise CorrectionPlanError('missing or invalid values')
    if (amount(bank_doc.get('total_emitted')) != current or amount(bank_doc.get('burned')) != burned
            or amount(bank_doc.get('coins')) != bank_balance):
        raise CorrectionPlanError('bank document does not match report')
    if current - supply != delta or bank_balance + legacy_balance + player_balance != supply:
        raise CorrectionPlanError('snapshot totals disagree')
    if current + burned > Decimal(str(TOTAL_EMISSION_CAP)):
        raise CorrectionPlanError('recorded lifetime already exceeds cap')
    if 'emission_cap' in bank_doc and amount(bank_doc['emission_cap']) != Decimal(str(TOTAL_EMISSION_CAP)):
        raise CorrectionPlanError('stored cap differs from configured limit')
    adjustment = delta.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    if adjustment <= 0 or abs(delta - expected) > Decimal('0.01') or adjustment > current:
        raise CorrectionPlanError('difference changed or is invalid')
    # Preserve current + burns exactly in decimal arithmetic by transferring the
    # same accounting amount to a separate, non-spendable limit reserve.
    return {'current_before': current, 'current_after': current - adjustment,
            'limit_reserve': adjustment, 'burned': burned,
            'supply': supply, 'residual': delta - adjustment,
            'lifetime_before': current + burned,
            'lifetime_after': (current - adjustment) + burned + adjustment}
