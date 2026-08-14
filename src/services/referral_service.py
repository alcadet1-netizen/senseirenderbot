"""
���������🔗 Сервис реферальной программы.
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
            return False, "��❌ Неверный код"
        try:
            referrer_id = int(referrer_code[4:])
        except ValueError:
            return False, "��❌ Неверный код"

        # Use the user_service to process the referral
        result = await self.user_service.process_referral(referred_id, referrer_id)
        # The user_service.process_referral returns a dict with keys: success, referrer_id, etc.
        # We need to convert to the expected tuple (bool, str)
        if result.get("success"):
            referrer_reward = result.get("referrer_reward", {})
            coins = referrer_reward.get("coins", 0)
            xp = referrer_reward.get("xp", 0)
            return True, f"���🎉 Бонус: +{coins} монет, +{xp} XP!"
        else:
            error = result.get("error", "Unknown error")
            return False, f"��❌ {error}"

    # We'll implement other methods as needed, but for now we stub them out
    async def get_stats(self, user_id: int):
        """Stub for getting referral stats."""
        return {
            "total": 0,
            "level1": 0,
            "level2": 0,
            "bonus": 0.0,
        }

    async def get_top(self, limit: int = 10):
        """Stub for getting top referrers."""
        return []

    async def get_referrals_list(self, user_id: int, level: int = 1, limit: int = 10):
        """Stub for getting list of referrals."""
        return []