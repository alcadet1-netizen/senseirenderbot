"""
📅 Сервис ежедневных бонусов.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Optional, Tuple
import asyncio

from src.core.config import settings
from src.core.constants import (
    DAILY_BASE_COINS,
    DAILY_BASE_XP,
    DAILY_STREAK_BONUSES,
    STARTER_XP,
    STARTER_COINS,
    STARTER_KATANA_LENGTH,
)
from src.core.exceptions import DailyAlreadyClaimedError
from src.infra.mongo.client import MongoClient
import logging

logger = logging.getLogger(__name__)


class DailyService:
    """Сервис ежедневных бонусов."""

    def __init__(self, mongo_client: MongoClient):
        self.mongo_client = mongo_client
        self.db = mongo_client.database
        # Collections
        self.users = self.db.users
        self.daily_claims = self.db.daily_claims
        self.transactions = self.db.transactions
        # For bank balance, we'll use a single document in a collection or store in settings
        # For simplicity, we'll use a document in bot_stats or similar
        self.bank = self.db.bank  # Will store {_id: "main", balance: X}
        # Locks for concurrency control - we'll use asyncio.Lock per user for simplicity
        # In production, you might want to use MongoDB transactions or a proper locking mechanism
        self._user_locks = {}
        self._lock = asyncio.Lock()  # Lock for managing the _user_locks dict

    async def _get_user_lock(self, user_id: int) -> asyncio.Lock:
        """Get or create a lock for a specific user."""
        async with self._lock:
            if user_id not in self._user_locks:
                self._user_locks[user_id] = asyncio.Lock()
            return self._user_locks[user_id]

    async def claim_daily(
        self,
        user_id: int,
        username: Optional[str] = None,
        first_name: str = "",
        is_bot: bool = False
    ) -> dict:
        """Получить ежедневный бонус."""
        user_lock = await self._get_user_lock(user_id)

        async with user_lock:
            # Get or create user
            user = await self.users.find_one({"id": user_id})
            if not user:
                # Create user if doesn't exist
                user_doc = {
                    "id": user_id,
                    "username": username or "",
                    "first_name": first_name,
                    "is_bot": is_bot,
                    "is_banned": False,
                    "coins": STARTER_COINS,
                    "xp": STARTER_XP,
                    "level": 1,
                    "messages_count": 0,
                    "daily_streak": 0,
                    "last_daily": None,
                    "has_katana": True,
                    "katana_length": STARTER_KATANA_LENGTH,
                    "achievements_count": 0,
                    "wins": 0,
                    "losses": 0,
                    "role": None,
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
                await self.users.insert_one(user_doc)
                user = user_doc

            if user.get("is_banned"):
                return {"success": False, "error": "banned"}

            today = datetime.utcnow().date()
            start_of_day = datetime.combine(today, datetime.min.time())

            # Check if already claimed today
            existing_claim = await self.daily_claims.find_one({
                "user_id": user_id,
                "claim_date": start_of_day
            })

            if existing_claim:
                now = datetime.utcnow()
                tomorrow = datetime.combine(
                    today + timedelta(days=1),
                    datetime.min.time()
                )
                delta = tomorrow - now
                hours, remainder = divmod(int(delta.total_seconds()), 3600)
                minutes, _ = divmod(remainder, 60)

                time_str = f"через {hours} ч. {minutes} мин."
                raise DailyAlreadyClaimedError(time_str)

            # Calculate streak
            last_daily = user.get("last_daily")
            if last_daily:
                if isinstance(last_daily, str):
                    last_daily = datetime.fromisoformat(last_daily).date()
                elif hasattr(last_daily, 'date'):
                    last_daily = last_daily.date()

                yesterday = today - timedelta(days=1)
                if last_daily == yesterday:
                    new_streak = user.get("daily_streak", 0) + 1
                elif last_daily == today:
                    new_streak = user.get("daily_streak", 0)  # Already claimed today, but we checked above
                else:
                    new_streak = 1
            else:
                new_streak = 1

            # Calculate rewards
            xp_reward = DAILY_BASE_XP
            coins_reward = DAILY_BASE_COINS

            bonus_xp = 0
            bonus_coins = 0

            for streak_days, (b_xp, b_coins) in DAILY_STREAK_BONUSES.items():
                if new_streak >= streak_days:
                    bonus_xp = b_xp
                    bonus_coins = b_coins

            total_xp = xp_reward + bonus_xp
            total_coins = coins_reward + bonus_coins

            # Check bank balance
            bank_doc = await self.bank.find_one({"_id": "main"})
            bank_balance = bank_doc.get("balance", 0) if bank_doc else 0

            if bank_balance < total_coins:
                total_coins = min(total_coins, int(bank_balance))

            # Update bank if we're giving coins
            if total_coins > 0:
                await self.bank.update_one(
                    {"_id": "main"},
                    {"$inc": {"balance": -total_coins}},
                    upsert=True
                )

            # Update user
            await self.users.update_one(
                {"id": user_id},
                {
                    "$inc": {
                        "xp": total_xp,
                        "coins": total_coins
                    },
                    "$set": {
                        "last_daily": datetime.utcnow(),
                        "daily_streak": new_streak,
                        "updated_at": datetime.utcnow()
                    }
                }
            )

            # Create transaction record
            tx_doc = {
                "user_id": user_id,
                "tx_type": "daily_bonus",
                "xp_change": total_xp,
                "coins_change": total_coins,
                "description": f"Daily bonus, streak {new_streak}",
                "created_at": datetime.now(timezone.utc),
            }
            await self.transactions.insert_one(tx_doc)

            # Create daily claim record
            claim_doc = {
                "user_id": user_id,
                "claim_date": start_of_day,
                "xp_received": total_xp,
                "coins_received": int(total_coins),
                "streak_at_claim": new_streak,
                "created_at": datetime.now(timezone.utc),
            }
            await self.daily_claims.insert_one(claim_doc)

            return {
                "success": True,
                "xp": xp_reward,
                "coins": coins_reward,
                "bonus_xp": bonus_xp,
                "bonus_coins": bonus_coins,
                "total_xp": total_xp,
                "total_coins": total_coins,
                "streak": new_streak,
            }

    async def can_claim(self, user_id: int) -> Tuple[bool, Optional[str]]:
        """Проверить, может ли пользователь получить бонус."""
        today = datetime.utcnow().date()
        start_of_day = datetime.combine(today, datetime.min.time())

        existing_claim = await self.daily_claims.find_one({
            "user_id": user_id,
            "claim_date": start_of_day
        })

        if existing_claim:
            now = datetime.utcnow()
            tomorrow = datetime.combine(
                today + timedelta(days=1),
                datetime.min.time()
            )
            delta = tomorrow - now
            hours, remainder = divmod(int(delta.total_seconds()), 3600)
            minutes, _ = divmod(remainder, 60)
            return False, f"через {hours} ч. {minutes} мин."

        return True, None

    async def settle_hedgehog(self, user_id: int, won: bool, day: str) -> dict:
        """Atomically apply a day's game result to the user, never subtract funds.

        The receipt and the balance/streak change live in ONE Mongo document.
        Optional ledger writes follow that atomic commit; retries return the
        stored receipt rather than re-crediting after a network failure.
        """
        from pymongo import ReturnDocument
        from src.services.hedgehog_service import FAILURE_MESSAGE, GameError, utc_day

        if day != utc_day():
            raise GameError('Наступил новый день. Откройте /senseidaily заново.')
        lock = await self._get_user_lock(user_id)
        async with lock:
            user = await self.users.find_one({'id': user_id})
            if not user or user.get('is_banned'):
                raise GameError('Профиль недоступен.')
            if user.get('hedgehog_day') == day:
                return user['hedgehog_result']
            claim_date = datetime.combine(date.fromisoformat(day), datetime.min.time())
            if await self.daily_claims.find_one({'user_id': user_id, 'claim_date': claim_date}):
                raise DailyAlreadyClaimedError('завтра после 00:00 UTC')
            streak = 0
            if won:
                previous = user.get('last_daily')
                if isinstance(previous, str):
                    previous = datetime.fromisoformat(previous)
                yesterday = date.fromisoformat(day) - timedelta(days=1)
                streak = user.get('daily_streak', 0) + 1 if previous and previous.date() == yesterday else 1
            bonus_xp, bonus_coins = 0, 0
            if won:
                for days, bonus in sorted(DAILY_STREAK_BONUSES.items()):
                    if streak >= days:
                        bonus_xp, bonus_coins = bonus
            total_xp = DAILY_BASE_XP + bonus_xp if won else 0
            bank = await self.bank.find_one({'_id': 'main'}) if won else None
            total_coins = min(DAILY_BASE_COINS + bonus_coins, max(0, int((bank or {}).get('balance', 0)))) if won else 0
            result = {
                'success': won, 'streak': streak,
                'xp': DAILY_BASE_XP if won else 0, 'coins': DAILY_BASE_COINS if won else 0,
                'bonus_xp': bonus_xp, 'bonus_coins': bonus_coins,
                'total_xp': total_xp, 'total_coins': total_coins,
                'message': 'Вы погладили ежа! Он довольно фырчит, а бонус уже ваш. 🦔' if won else FAILURE_MESSAGE,
            }
            now = datetime.now(timezone.utc)
            changes = {'$set': {'hedgehog_day': day, 'hedgehog_result': result,
                                'daily_streak': streak, 'last_daily': now, 'updated_at': now}}
            if won:
                changes['$inc'] = {'xp': total_xp, 'coins': total_coins}
            committed = await self.users.find_one_and_update(
                {'id': user_id, 'is_banned': {'$ne': True}, 'hedgehog_day': {'$ne': day}},
                changes, return_document=ReturnDocument.AFTER,
            )
            if committed is None:
                cached = await self.users.find_one({'id': user_id, 'hedgehog_day': day})
                if cached:
                    return cached['hedgehog_result']
                raise GameError('Не удалось записать результат. Попробуйте ещё раз.')
            # The user receipt is authoritative. Bank accounting and journal
            # writes below are best-effort, not a multi-document transaction.
            try:
                if total_coins:
                    await self.bank.update_one(
                        {'_id': 'main', 'balance': {'$gte': total_coins}},
                        {'$inc': {'balance': -total_coins}},
                    )
                key = f'hedgehog:{user_id}:{day}'
                await self.daily_claims.update_one({'_id': key}, {'$setOnInsert': {
                    'user_id': user_id, 'claim_date': claim_date, 'xp_received': total_xp,
                    'coins_received': total_coins, 'streak_at_claim': streak,
                    'game_result': result, 'created_at': now,
                }}, upsert=True)
                if won:
                    await self.transactions.update_one({'_id': key}, {'$setOnInsert': {
                        'user_id': user_id, 'tx_type': 'daily_bonus', 'xp_change': total_xp,
                        'coins_change': total_coins, 'description': 'Hedgehog daily game', 'created_at': now,
                    }}, upsert=True)
            except Exception:
                logger.exception('Hedgehog receipt committed; daily journal needs reconciliation: user=%s day=%s', user_id, day)
            return result
