"""
🔗 Сервис реферальной программы.
"""

import logging
from typing import Tuple, Optional

from src.core.config import settings
from src.services.user_service import UserService

logger = logging.getLogger(__name__)


class ReferralService:
    def __init__(self, mongo_client):
        # We'll set the user_service later from the container to avoid circular import
        self.user_service: Optional[UserService] = None
        # We don't use mongo_client directly here, but we keep it for consistency
        self.mongo_client = mongo_client

    async def ensure_indexes(self):
        db = self.mongo_client.database
        await db.users.create_index([('referrer_id', 1), ('id', 1)])
        await db.transactions.create_index([('user_id', 1), ('tx_type', 1), ('created_at', -1), ('_id', -1)])

    async def process_referral(self, referred_id: int, referrer_code: str) -> Tuple[bool, str]:
        """Process a referral.
        Args:
            referred_id: The ID of the user being referred.
            referrer_code: The referral code (e.g., "ref_123").
        Returns:
            Tuple (success, message)
        """
        if self.user_service is None:
            logger.error("UserService not set in ReferralService")
            return False, "Internal error"

        # Extract referrer ID from code
        if not referrer_code or not referrer_code.startswith("ref_"):
            return False, "❌ Неверный код"
        try:
            referrer_id = int(referrer_code[4:])
        except ValueError:
            return False, "❌ Неверный код"

        # Use the user_service to process the referral
        result = await self.user_service.process_referral(referred_id, referrer_id)
        # The user_service.process_referral returns a dict with keys: success, referrer_id, etc.
        # We need to convert to the expected tuple (bool, str)
        if result.get("success"):
            return True, '🥷 Приглашение принято! Бонус 50 Coin — после активности в три разных дня и платного улучшения катаны; при наличии средств банка.'
        else:
            error = result.get("error", "Unknown error")
            return False, f"❌ {error}"

    async def get_stats(self, user_id: int):
        from src.domain.entities.referral import ReferralStats
        db = self.mongo_client.database
        counts, active = [], []
        # Breadth-first aggregation avoids loading the referral tree into Python.
        for depth in range(3):
            pipeline = [{'$match': {'referrer_id': user_id}}]
            for _ in range(depth):
                pipeline += [{'$lookup': {'from': 'users', 'localField': 'id', 'foreignField': 'referrer_id', 'as': 'children'}},
                             {'$unwind': '$children'}, {'$replaceRoot': {'newRoot': '$children'}}]
            pipeline += [{'$group': {'_id': '$id', 'active': {'$max': {'$cond': ['$referral_bonus_paid', 1, 0]}}}},
                         {'$group': {'_id': None, 'count': {'$sum': 1}, 'active': {'$sum': '$active'}}}]
            rows = await db.users.aggregate(pipeline).to_list(length=1)
            counts.append(rows[0]['count'] if rows else 0)
            active.append(rows[0]['active'] if rows else 0)
        user = await db.users.find_one({'id': user_id}) or {}
        return ReferralStats(user_id=user_id, level_1_count=counts[0], level_2_count=counts[1],
            level_3_count=counts[2], level_1_active=active[0], level_2_active=active[1], level_3_active=active[2],
            total_coins_earned=user.get('referral_earned', 0),
            bonus_eligible=user.get('referral_version') == 2, bonus_paid=bool(user.get('referral_bonus_paid')),
            activity_days=min(3, len(set(user.get('referral_activity_days') or []))),
            paid_upgrade=bool(user.get('referral_paid_upgrade')))

    async def get_top(self, limit=10):
        return []

    async def get_referrals_list(self, user_id, level=1, limit=10):
        from types import SimpleNamespace
        rows = await self.mongo_client.database.users.find({'referrer_id': user_id}).sort('id', 1).limit(limit).to_list(length=limit)
        return [SimpleNamespace(referred_id=r['id'], is_active=r.get('referral_bonus_paid', False), coins_earned=0) for r in rows]
