"""Durable, at-most-one-attempt xRocket awards; ambiguous outcomes need review."""
import hashlib
import math
from datetime import datetime, timezone
from pymongo.errors import DuplicateKeyError
from src.services.xrocket_service import XRocketTransferRejected


async def award_boss_gram(container, state, user_id, amount, event_key):
    if not math.isfinite(amount) or amount <= 0:
        raise ValueError('Invalid GRAM amount')
    db = container.mongo_client.database
    key = hashlib.sha256(f"{state.get('battle_id', state['start_time'])}:{user_id}:{event_key}".encode()).hexdigest()[:20]
    receipts = db.boss_xrocket_rewards
    try:
        await receipts.insert_one(dict(_id=key, user_id=user_id, amount=amount, currency='GRAM',
            battle_id=state.get('battle_id'), start_time=state['start_time'], status='prepared',
            created_at=datetime.now(timezone.utc)))
    except DuplicateKeyError:
        return 'duplicate'
    settings = await container.boss_service.get_reward_settings()
    limit = settings['pool_limit']
    if not math.isfinite(limit) or limit < 0:
        raise ValueError('Invalid GRAM pool limit')
    # Reserve BEFORE the external call. Never auto-release an ambiguous transfer.
    reserved = await db.boss_state.update_one(
        {'_id':'boss_state', 'start_time':state['start_time'],
         '$expr':{'$lte':[{'$add':[{'$ifNull':['$gram_reserved',0]},amount]},limit]}},
        {'$inc':{'gram_reserved':amount}})
    if reserved.modified_count != 1:
        await receipts.update_one({'_id':key},{'$set':{'status':'pool_exhausted'}})
        return 'pool_exhausted'
    await receipts.update_one({'_id':key},{'$set':{'status':'sending'}})
    try:
        confirmed = await container.xrocket_service.transfer(user_id,'GRAM',amount,transfer_id=key,raise_rejection=True)
    except XRocketTransferRejected as exc:
        await receipts.update_one({'_id':key},{'$set':{'status':'rejected',
            'provider_status':exc.status,'provider_detail':exc.detail}})
        # Keep reservation for explicit reconciliation; never blindly refund/retry.
        return 'rejected'
    except Exception:
        confirmed = False
    status = 'confirmed' if confirmed else 'needs_review'
    await receipts.update_one({'_id':key},{'$set':{'status':status}})
    return status
