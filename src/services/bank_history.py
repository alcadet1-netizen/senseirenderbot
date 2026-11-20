"""Private aggregate-only view of selected recent journal entries, not a ledger."""
from datetime import datetime, timedelta, timezone

from scripts.diagnose_emission import amount

# Fixed names only: do not reveal arbitrary stored strings or descriptions.
TYPES = ('burn', 'ban_confiscation', 'duel_escrow', 'duel_bet_payout',
         'duel_bet_refund', 'dojo_daily', 'dojo_chest', 'dojo_task',
         'dojo_profile_task', 'game_win', 'admin_grant', 'daily_bonus',
         'daily_pet_bonus', 'paid_pet_reward', 'message_reward', 'purchase',
         'exchange_in', 'exchange_out', 'slots_bet', 'slots_win')


async def read_bank_history(db, *, now=None):
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(days=30)
    pipeline = [
        {'$match': {'created_at': {'$gte': since, '$lt': now}, 'tx_type': {'$in': list(TYPES)}}},
        {'$group': {'_id': '$tx_type', 'count': {'$sum': 1},
                    'amount': {'$sum': {'$cond': [{'$isNumber': '$coins_change'}, '$coins_change', 0]}},
                    'invalid': {'$sum': {'$cond': [{'$isNumber': '$coins_change'}, 0, 1]}}}},
    ]
    rows = await db.transactions.aggregate(pipeline, maxTimeMS=10000).to_list(length=len(TYPES))
    return since, now, rows


def format_bank_history(since, now, rows):
    lines = ['🏦 История операций · только чтение',
             f'UTC: {since.isoformat()} — {now.isoformat()}',
             'Только выбранные виды операций за последние 30 дней. Суммы — изменения в журнале, не остаток банка.']
    ordered = {row['_id']: row for row in rows if row.get('_id') in TYPES}
    for kind in TYPES:
        if kind not in ordered:
            continue
        row = ordered[kind]
        value = amount(row.get('amount'))
        total = format(value, 'f') if value is not None else 'неизвестно'
        lines.append(f"{kind}: {row.get('count', 0)} записей, сумма {total} Coin; нечисловых: {row.get('invalid', 0)}")
    if not ordered:
        lines.append('Записей выбранных типов за период не найдено.')
    lines.append('Журнал может быть неполным. Переводы могут записываться с одной стороны; суммы нельзя приравнивать к созданию или потере Coin. Данные не изменены.')
    return '\n'.join(lines)
