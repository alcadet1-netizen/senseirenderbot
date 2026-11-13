"""Mongo-transactional boss Coin settlement; no external payment in transaction."""
import time
from datetime import datetime, timezone
from src.services.paid_hedgehog_service import PaidHedgehogService


async def settle_boss(mongo):
    db = mongo.database
    async def settle(tx):
        state = await db.boss_state.find_one({'_id': 'boss_state'}, session=tx)
        if not state:
            return None
        kind = state.get('settlement_kind')
        if not kind and not state.get('is_dead') and not state.get('is_expired') and state.get('deadline') and state['deadline'] <= time.time():
            kind = 'loss'
        if not kind or state.get('settlement'):
            return state
        # For legacy terminal battles without a marker, do not guess/replay money.
        users = []
        for uid in (state.get('hits') or {}):
            user = await db.users.find_one({'id': int(uid)}, session=tx)
            if user:
                users.append(user)
        total = 0.0
        share = 0.0
        if kind == 'win' and users:
            from src.core.constants import BOSSES
            requested = float(BOSSES[state['boss_id']].get('coins_reward', 0))
            bank = await db.bank.find_one({'_id':'single'}, session=tx)
            total = min(max(0, float((bank or {}).get('coins',0))), max(0,requested))
            share = total / len(users)
            if total:
                debit = await db.bank.update_one({'_id':'single','coins':{'$gte':total}}, {'$inc':{'coins':-total}}, session=tx)
                if debit.matched_count != 1:
                    raise RuntimeError('Bank changed during boss settlement')
        count = 0
        battle = state.get('battle_id') or str(state['start_time'])
        for user in users:
            # Preserve existing loss policy (-100), including low balances.
            delta = share if kind == 'win' else -100.0
            await db.users.update_one({'id':user['id']}, {'$inc':{'coins':delta}}, session=tx)
            await db.transactions.insert_one(dict(_id=f'boss:{battle}:{kind}:{user["id"]}',
                user_id=user['id'], tx_type='boss_win' if kind == 'win' else 'boss_loss',
                coins_change=delta, created_at=datetime.now(timezone.utc)), session=tx)
            count += 1
            if kind == 'loss':
                total += 100.0
        if kind == 'loss' and total:
            # Never invent bank principal; only collected penalties are deposited.
            await db.bank.update_one({'_id':'single'}, {'$inc':{'coins':total}}, upsert=True, session=tx)
        result = dict(kind=kind, total=total, count=count, share=share)
        changes = {'settlement_kind':kind, 'settlement':result, 'card_synced':False}
        if kind == 'loss':
            changes['is_expired'] = True
            changes['ended_at'] = state.get('deadline') or time.time()
        await db.boss_state.update_one({'_id':'boss_state'}, {'$set':changes}, session=tx)
        return {**state, **changes}
    return await PaidHedgehogService(mongo).transaction(settle)
