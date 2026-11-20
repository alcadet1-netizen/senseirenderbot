"""Read-only, aggregate-only accounting snapshot for administrators.

The scan is bounded in time, not in collection size. Never prints user records.
"""
from datetime import datetime, timezone

from scripts.diagnose_emission import build_report
from src.services.emission_watch import correction_reserve


async def read_bank_diagnostic(db):
    started = datetime.now(timezone.utc)
    async with await db.client.start_session(snapshot=True) as session:
        single = await db.bank.find_one({'_id': 'single'},
            {'coins': 1, 'total_emitted': 1, 'emission_cap': 1, 'burned': 1,
             'emission_correction_reserve': 1, 'emission_correction_applied': 1,
             'emission_correction_id': 1}, session=session, max_time_ms=10000)
        legacy = await db.bank.find_one({'_id': 'main'}, {'balance': 1}, session=session, max_time_ms=10000)
        numeric = {'$isNumber': '$coins'}
        users = await db.users.aggregate([{'$group': {
            '_id': None, 'count': {'$sum': 1},
            'numeric_sum': {'$sum': {'$cond': [numeric, '$coins', 0]}},
            'positive_sum': {'$sum': {'$cond': [{'$and': [numeric, {'$gt': ['$coins', 0]}]}, '$coins', 0]}},
            'negative_sum': {'$sum': {'$cond': [{'$and': [numeric, {'$lt': ['$coins', 0]}]}, '$coins', 0]}},
            'positive_count': {'$sum': {'$cond': [{'$and': [numeric, {'$gt': ['$coins', 0]}]}, 1, 0]}},
            'negative_count': {'$sum': {'$cond': [{'$and': [numeric, {'$lt': ['$coins', 0]}]}, 1, 0]}},
            'non_numeric_count': {'$sum': {'$cond': [numeric, 0, 1]}},
        }}], session=session, maxTimeMS=10000).to_list(length=1)
        valid = {'$and': [{'$isNumber': '$bet'}, {'$gte': ['$bet', 0]}]}
        escrow = await db.duel_escrows.aggregate([
            {'$match': {'state': {'$in': ['reserved', 'decided']}}},
            {'$group': {'_id': None, 'bets': {'$sum': {'$cond': [valid, '$bet', 0]}},
                        'invalid': {'$sum': {'$cond': [valid, 0, 1]}}}},
        ], session=session, maxTimeMS=10000).to_list(length=1)
    report = build_report(single, legacy, users[0] if users else {}, [],
        started_at=started, finished_at=datetime.now(timezone.utc), history_days=0,
        escrow=escrow[0] if escrow else {'bets': 0, 'invalid': 0})
    reserve = correction_reserve(single) if single is not None else None
    report['limit_reserve'] = str(reserve) if reserve is not None else None
    return report


def format_bank_diagnostic(report):
    def val(value):
        return str(value) if value is not None else 'неизвестно'
    single, legacy, users = report['bank_single'], report['bank_main'], report['users']
    calculated, escrow = report['calculated'], report['duel_escrow']
    return '\n'.join([
        '🏦 Сверка банка · только чтение',
        f"Снимок UTC: {report['snapshot_requested_utc']}",
        f"Банк single: {val(single['coins'])} Coin; документ: {'есть' if single['present'] else 'нет'}",
        f"Банк main (старая схема): {val(legacy['balance'])} Coin; документ: {'есть' if legacy['present'] else 'нет'}",
        f"Эмиссия: {val(single['total_emitted'])} Coin; сожжено: {val(single['burned'])} Coin",
        f"Служебный резерв лимита (не Coin): {val(report.get('limit_reserve'))}",
        f"Сумма балансов игроков: {val(users['numeric_balance_sum'])} Coin; профилей: {users['count']}",
        f"Отрицательных балансов: {users['negative_count']}; сумма: {val(users['negative_balance_sum'])} Coin",
        f"Балансов с отсутствующим или нечисловым значением: {users['missing_or_non_numeric_count']}",
        f"Ставки дуэлей: {val(escrow['held_coins'])} Coin; некорректных ставок: {escrow['invalid_stakes']}",
        f"Всего по расчёту интерфейса: {val(calculated['ui_total_supply'])} Coin",
        f"Эмиссия минус всего: {val(calculated['emission_minus_ui_total_supply'])} Coin",
        'Это снимок, а не доказательство причины расхождения. История может быть неполной; балансы не изменены.',
    ])
