"""Referral accounting. All callers must supply the purchase Mongo session."""
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN

from pymongo.errors import DuplicateKeyError
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern


async def transaction(mongo, callback):
    async with await mongo.database.client.start_session() as session:
        return await session.with_transaction(callback, read_concern=ReadConcern('snapshot'),
                                              write_concern=WriteConcern('majority'))

RATES = (Decimal('0.10'), Decimal('0.01'), Decimal('0.001'))


def commission(cost, rate):
    return float((Decimal(str(cost)) * rate).quantize(Decimal('0.001'), rounding=ROUND_DOWN))


async def ancestors(db, uid, session):
    seen = {uid}
    result = []
    user = await db.users.find_one({'id': uid}, session=session)
    for _ in RATES:
        parent = (user or {}).get('referrer_id')
        if not parent or parent in seen:
            break
        seen.add(parent)
        user = await db.users.find_one({'id': parent}, session=session)
        if not user:
            break
        result.append(user)
    return result


async def distribute(db, user, cost, event, session):
    """Split purchase principal, never mint coins or recurse on commissions."""
    total = Decimal('0')
    now = datetime.now(timezone.utc)
    for level, (parent, rate) in enumerate(zip(await ancestors(db, user['id'], session), RATES), 1):
        if parent.get('is_banned'):
            continue
        amount = commission(cost, rate)
        if amount <= 0:
            continue
        total += Decimal(str(amount))
        await db.users.update_one({'id': parent['id']}, {'$inc': {'coins': amount, 'referral_earned': amount}}, session=session)
        await db.transactions.insert_one(dict(_id=f'{event}:ref:{level}', user_id=parent['id'],
            source_user_id=user['id'], level=level, tx_type='referral_commission', coins_change=amount,
            created_at=now), session=session)
    remainder = float(Decimal(str(cost)) - total)
    await db.bank.update_one({'_id': 'single'}, {'$inc': {'coins': remainder}}, upsert=True, session=session)


async def bind(mongo, uid, parent_id):
    # Every graph change must serialize, including links through intermediate
    # ancestors. Touching only the two endpoints allows longer concurrent
    # cycles (write skew under Mongo snapshot isolation).
    db = mongo.database
    # Mini App initData may retain a start parameter on each refresh. Linked
    # accounts are immutable, so avoid serializing every later refresh.
    existing = await db.users.find_one({'id': uid})
    if not existing or existing.get('referrer_id'):
        return {'success': False, 'error': 'Приглашение недоступно'}
    try:
        await db.referral_locks.update_one(
            {'_id': 'graph'}, {'$setOnInsert': {'revision': 0}}, upsert=True)
    except DuplicateKeyError:
        # Another worker created the lock concurrently.
        pass

    async def execute(tx):
        await db.referral_locks.update_one(
            {'_id': 'graph'}, {'$inc': {'revision': 1}}, session=tx)
        user = await db.users.find_one({'id': uid}, session=tx)
        parent = await db.users.find_one({'id': parent_id}, session=tx)
        if not user or not parent or parent.get('is_banned') or parent.get('is_bot') or user.get('is_banned') or user.get('is_bot') or uid == parent_id or user.get('referrer_id'):
            return {'success': False, 'error': 'Приглашение недоступно'}
        seen = {uid}
        cursor = parent
        for _ in range(100):
            if cursor['id'] in seen:
                return {'success': False, 'error': 'Цикл приглашений запрещён'}
            seen.add(cursor['id'])
            next_id = cursor.get('referrer_id')
            if not next_id:
                break
            cursor = await db.users.find_one({'id': next_id}, session=tx)
            if not cursor:
                break
        else:
            return {'success': False, 'error': 'Слишком длинная цепочка'}
        await db.users.update_one({'id': uid}, {'$set': {
            'referrer_id': parent_id, 'referral_binding_closed': True,
            'referral_version': 2, 'referral_activity_days': [],
            'referral_paid_upgrade': False}}, session=tx)
        # Keep the direct-referral counter in the same transaction as the link.
        await db.users.update_one({'id': parent_id}, {'$inc': {'referral_count': 1}}, session=tx)
        return {'success': True, 'referrer_reward': {}, 'referral_reward': {}}
    return await transaction(mongo, execute)


async def activate(db, user, event, session):
    """New v2 referrals only; unpaid bonus remains pending if bank is short."""
    if user.get('referral_version') != 2 or user.get('referral_bonus_paid'):
        return
    days = set(user.get('referral_activity_days', []))
    days.add(datetime.now(timezone.utc).date().isoformat())
    if len(days) < 3:
        return
    parent = await db.users.find_one({'id': user.get('referrer_id')}, session=session)
    if not parent or parent.get('is_banned'):
        return
    debit = await db.bank.update_one({'_id': 'single', 'coins': {'$gte': 150}}, {'$inc': {'coins': -150}}, session=session)
    if debit.matched_count != 1:
        return
    for uid, amount in ((parent['id'], 100), (user['id'], 50)):
        inc = {'coins': amount}
        if uid == parent['id']:
            inc['referral_earned'] = amount
        await db.users.update_one({'id': uid}, {'$inc': inc}, session=session)
        await db.transactions.insert_one(dict(_id=f'referral:activation:{user["id"]}:{uid}', user_id=uid,
            source_user_id=user['id'], tx_type='referral_activation', coins_change=amount,
            created_at=datetime.now(timezone.utc)), session=session)
    await db.users.update_one({'id': user['id']}, {'$set': {'referral_bonus_paid': True}}, session=session)
