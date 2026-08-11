from datetime import datetime
from collections import defaultdict
import asyncio
import logging
import json
from dataclasses import asdict
from typing import Tuple, Optional, List

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.exc import IntegrityError

from src.infra.database.uow import UnitOfWork
from src.infra.database.models import TransactionType
from src.domain.repositories.referral_repository import ReferralRepository
from src.domain.repositories.user_repository import UserRepository
from src.domain.repositories.bank_repository import BankRepository
from src.domain.repositories.transaction_repository import TransactionRepository
from src.infra.database.models.referral import Referral
from src.domain.entities.referral import ReferralStats, REWARDS, ReferralRank

logger = logging.getLogger(__name__)

class ReferralSecurity:
    MAX_PER_HOUR = 10
    MAX_PER_DAY = 50
    SUSPICIOUS_SET_KEY = "referral:suspicious"
    
    def __init__(self, redis: Redis):
        self.redis = redis
    
    async def check(self, referrer_id: int, referred_id: int) -> Tuple[bool, str]:
        if referrer_id == referred_id:
            return False, "🚫 Нельзя пригласить себя!"
            
        # Check suspicious list in Redis
        if await self.redis.sismember(self.SUSPICIOUS_SET_KEY, referrer_id):
            return False, "🔒 Аккаунт заблокирован"
        
        # Rate limiting using Redis ZSET (Sliding Window)
        key = f"referral:rate:{referrer_id}"
        now_ts = datetime.now().timestamp()
        hour_ago = now_ts - 3600
        day_ago = now_ts - 86400
        
        async with self.redis.pipeline(transaction=True) as pipe:
            # Remove old records
            await pipe.zremrangebyscore(key, 0, day_ago)
            # Count last hour
            await pipe.zcount(key, hour_ago, "+inf")
            # Count last day (already cleaned < day_ago)
            await pipe.zcard(key)
            results = await pipe.execute()
            
        count_hour = results[1]
        count_day = results[2]
        
        if count_hour >= self.MAX_PER_HOUR:
            return False, "⏰ Лимит за час. Попробуйте позже."
        if count_day >= self.MAX_PER_DAY:
            return False, "📅 Дневной лимит достигнут."
            
        return True, ""
    
    async def record(self, referrer_id: int):
        """Record a successful referral event"""
        key = f"referral:rate:{referrer_id}"
        now_ts = datetime.now().timestamp()
        # Member must be unique for each event, using timestamp
        member = f"{now_ts}"
        
        async with self.redis.pipeline(transaction=True) as pipe:
            await pipe.zadd(key, {member: now_ts})
            await pipe.expire(key, 86400) # 24 hours TTL
            await pipe.execute()

class ReferralService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], redis: Redis):
        self.session_factory = session_factory
        self.redis = redis
        self.security = ReferralSecurity(redis)

    async def process_referral(self, referred_id: int, referrer_code: str) -> Tuple[bool, str]:
        # 1. Parse and Validate Code
        referrer_id = self._parse_code(referrer_code)
        if not referrer_id:
            return False, "❌ Неверный код"
            
        # 2. Security Checks
        ok, msg = await self.security.check(referrer_id, referred_id)
        if not ok:
            return False, msg
            
        # 3. Distributed Lock for the REFERRED user
        # Ensures a user cannot be processed as a referral multiple times concurrently
        lock_key = f"referral:lock:{referred_id}"
        acquired = await self.redis.set(lock_key, "1", nx=True, ex=10)
        if not acquired:
            return False, "⏳ Обработка... Подождите."
            
        try:
            return await self._execute_referral(referred_id, referrer_id)
        finally:
            await self.redis.delete(lock_key)

    def _parse_code(self, code: str) -> Optional[int]:
        if not code or not code.startswith("ref_"):
            return None
        try:
            return int(code[4:])
        except ValueError:
            return None

    async def _execute_referral(self, referred_id: int, referrer_id: int) -> Tuple[bool, str]:
        uow = UnitOfWork(self.session_factory)
        async with uow:
            referral_repo = ReferralRepository(uow.session)
            user_repo = UserRepository(uow.session)
            
            # Pre-check existence (optimization before locking rows)
            # We use get_for_update later, but fast fail is good
            
            # Check if already referred (DB check)
            if await referral_repo.is_already_referred(referred_id):
                 return False, "❌ Вы уже приглашены"

            # Lock and Get Users
            referrer = await user_repo.get_for_update(referrer_id)
            referred = await user_repo.get_for_update(referred_id)
            
            if not referrer or not referred:
                return False, "❌ Пользователь не найден"

            if referrer.id == referred.id:
                 return False, "🚫 Нельзя пригласить себя!"
            
            # Double check inside transaction/lock
            if referred.referrer_id:
                 return False, "❌ Вы уже приглашены"

            # Prepare Rewards
            r1 = REWARDS.get(1, (0, 0, 0, 0)) # (ref_coins, ref_xp, user_coins, user_xp)
            
            try:
                # 1. Create L1 Referral Record
                ref_entry = Referral(
                    referrer_id=referrer_id,
                    referred_id=referred_id,
                    level=1,
                    coins_earned=r1[0],
                    xp_earned=r1[1],
                    is_active=True
                )
                await referral_repo.add(ref_entry)
                
                # 2. Update User Stats
                referred.referrer_id = referrer.id
                referrer.referral_count += 1
                
                # 3. Apply L1 Rewards
                self._apply_rewards(referrer, r1[0], r1[1])
                self._apply_rewards(referred, r1[2], r1[3])
                
                # 4. Create Transactions
                await self._create_l1_transactions(uow, referrer, referred, r1)
                
                # 5. Process Level 2 (Nested logic)
                await self._process_level_2(uow, referrer_id, referred_id, referred.username or str(referred_id))

                await uow.commit()
                
            except IntegrityError:
                await uow.rollback()
                logger.warning(f"IntegrityError processing referral {referred_id} -> {referrer_id}")
                return False, "❌ Вы уже приглашены (ошибка данных)"
            except Exception as e:
                logger.error(f"Referral processing error: {e}", exc_info=True)
                await uow.rollback()
                return False, "❌ Произошла ошибка при обработке"

        # Post-processing (after commit)
        await self.security.record(referrer_id)
        # Invalidate caches
        await self.redis.delete(f"referral:stats:{referrer_id}")
        
        return True, f"🎉 Бонус: +{r1[2]} монет, +{r1[3]} XP!"

    async def _process_level_2(self, uow: UnitOfWork, referrer_id: int, referred_id: int, referred_name: str):
        """
        Process Level 2 rewards.
        Uses a nested transaction (savepoint) so failure here does not rollback the main L1 referral.
        """
        try:
            async with uow.session.begin_nested():
                referral_repo = ReferralRepository(uow.session)
                user_repo = UserRepository(uow.session)
                
                original_referrer_id = await referral_repo.get_referrer_id(referrer_id)
                if not original_referrer_id:
                    return

                original_referrer = await user_repo.get_for_update(original_referrer_id)
                if not original_referrer:
                    return
                    
                r2 = REWARDS.get(2, (0, 0, 0, 0)) # (ref_coins, ref_xp, 0, 0)
                
                # Create L2 Referral Record
                # Note: This might fail if referred_id has a unique constraint globally.
                # If so, the IntegrityError will be caught, and L2 rewards skipped/rolled back,
                # but L1 will persist.
                await referral_repo.add(Referral(
                    referrer_id=original_referrer_id,
                    referred_id=referred_id,
                    level=2,
                    coins_earned=r2[0],
                    xp_earned=r2[1],
                    is_active=True
                ))
                
                # Apply Rewards
                self._apply_rewards(original_referrer, r2[0], r2[1])
                
                # Transactions
                bank_repo = BankRepository(uow.session)
                tx_repo = TransactionRepository(uow.session)
                
                await bank_repo.withdraw(r2[0])
                await tx_repo.create(
                    user_id=original_referrer_id,
                    tx_type=TransactionType.REFERRAL_BONUS.value,
                    coins_change=r2[0],
                    xp_change=r2[1],
                    description=f"L2 Referral bonus: {referred_name}"
                )
                
        except IntegrityError:
            # Likely duplicate entry for referred_id if unique constraint exists
            logger.warning(f"Skipping L2 referral for {referred_id}: DB Constraint Violation (Duplicate referred_id?)")
        except Exception as e:
            logger.error(f"Error processing L2 referral: {e}")

    def _apply_rewards(self, user, coins: float, xp: int):
        user.coins += coins
        user.xp += xp

    async def _create_l1_transactions(self, uow: UnitOfWork, referrer, referred, r1: Tuple):
        bank_repo = BankRepository(uow.session)
        tx_repo = TransactionRepository(uow.session)
        
        # Withdraw total needed from Bank (referrer bonus + referred bonus)
        await bank_repo.withdraw(r1[0] + r1[2])
        
        await tx_repo.create(
            user_id=referrer.id,
            tx_type=TransactionType.REFERRAL_BONUS.value,
            coins_change=r1[0],
            xp_change=r1[1],
            description=f"Referral bonus: {referred.username or referred.id}"
        )
        await tx_repo.create(
            user_id=referred.id,
            tx_type=TransactionType.REFERRAL_BONUS.value,
            coins_change=r1[2],
            xp_change=r1[3],
            description=f"Welcome bonus from: {referrer.username or referrer.id}"
        )

    async def get_stats(self, user_id: int) -> ReferralStats:
        cache_key = f"referral:stats:{user_id}"
        cached = await self.redis.get(cache_key)
        if cached:
            try:
                data = json.loads(cached)
                return ReferralStats(**data)
            except Exception as e:
                logger.error(f"Error decoding referral stats cache: {e}")

        uow = UnitOfWork(self.session_factory)
        async with uow:
            referral_repo = ReferralRepository(uow.session)
            stats = await referral_repo.get_stats(user_id)
            
            try:
                await self.redis.setex(
                    cache_key,
                    300,
                    json.dumps(asdict(stats))
                )
            except Exception as e:
                logger.error(f"Error caching referral stats: {e}")
            
            return stats

    async def get_top(self, limit: int = 10) -> List[Tuple[int, int, Optional[str], str]]:
        cache_key = f"referral:top:{limit}"
        cached = await self.redis.get(cache_key)
        if cached:
            try:
                data = json.loads(cached)
                # cached data is list of [user_id, count, username, first_name]
                return [(item[0], item[1], item[2], item[3]) for item in data]
            except Exception as e:
                logger.error(f"Error decoding referral top cache: {e}")

        uow = UnitOfWork(self.session_factory)
        async with uow:
            referral_repo = ReferralRepository(uow.session)
            result = await referral_repo.get_top_referrers(limit)
            
            try:
                await self.redis.setex(
                    cache_key,
                    600,
                    json.dumps(result)
                )
            except Exception as e:
                logger.error(f"Error caching referral top: {e}")
            
            return result
            
    async def get_referrals_list(self, user_id: int, level: int = 1, limit: int = 10) -> List[Referral]:
        uow = UnitOfWork(self.session_factory)
        async with uow:
             referral_repo = ReferralRepository(uow.session)
             return await referral_repo.get_referrals_list(user_id, level, limit)
