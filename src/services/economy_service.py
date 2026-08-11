"""
💰 Сервис экономики.
"""

from typing import Optional

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from datetime import datetime, timedelta, timezone

from src.core.constants import (
    COINS_PER_MESSAGE,
    HALVING_THRESHOLDS,
    MESSAGES_PER_TICKET,
    XP_PER_MESSAGE,
    KATANA_UPGRADE_COST,
    KATANA_UPGRADE_COOLDOWN_HOURS,
    KATANA_WIN_CHANCE,
)
from src.core.exceptions import (
    InsufficientFundsError,
    UserNotFoundError,
    CooldownError,
    NoKatanaError,
)
from src.domain.repositories import (
    BankRepository,
    TicketRepository,
    TransactionRepository,
    UserRepository,
)
from src.infra.database.models import TransactionType
from src.infra.database.uow import UnitOfWork
from src.infra.redis.locks import DistributedLock
from src.services.level_service import LevelService
import random


class EconomyService:
    """Сервис экономики с халвингом и атомарными операциями."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        redis: Redis
    ):
        self.session_factory = session_factory
        self.redis = redis
        self.level_service = LevelService()

    def _calculate_halving_multiplier(self, total_in_circulation: float) -> float:
        """Рассчитать множитель халвинга."""
        multiplier = 1.0
        for threshold in HALVING_THRESHOLDS:
            if total_in_circulation >= threshold:
                multiplier *= 0.5
            else:
                break
        return max(multiplier, 0.001)

    async def process_message_reward(
        self,
        user_id: int,
        username: Optional[str] = None,
        first_name: str = "",
        last_name: Optional[str] = None,
        is_bot: bool = False,
        apply_rewards: bool = True
    ) -> dict:
        """Обработать награду за сообщение."""
        lock = DistributedLock(self.redis)
        
        async with lock.acquire(f"message_reward:{user_id}"):
            uow = UnitOfWork(self.session_factory)
            
            async with uow:
                user_repo = UserRepository(uow.session)
                tx_repo = TransactionRepository(uow.session)
                bank_repo = BankRepository(uow.session)
                ticket_repo = TicketRepository(uow.session)
                
                user, created = await user_repo.get_or_create(
                    user_id, username, first_name, last_name, is_bot=is_bot, with_lock=True
                )
                
                if user.is_banned:
                    return {"success": False, "reason": "banned"}
                
                xp_reward = 0
                coins_reward = 0.0
                multiplier = 0.0
                ticket_created = None
                level_up = None
                old_xp = user.xp

                if apply_rewards:
                    # Увеличиваем счетчик только если начисляем награду
                    user.messages_count += 1
                    
                    total_circulation = await tx_repo.get_total_coins_in_circulation()
                    multiplier = self._calculate_halving_multiplier(total_circulation)
                    
                    xp_reward = int(XP_PER_MESSAGE * multiplier)
                    coins_reward = COINS_PER_MESSAGE * multiplier
                    
                    bank_balance = await bank_repo.get_balance()
                    if bank_balance < coins_reward:
                        coins_reward = 0
                    else:
                        await bank_repo.withdraw(coins_reward)
                    
                    user.xp += xp_reward
                    user.coins += coins_reward
                    
                    await tx_repo.create(
                        user_id=user.id,
                        tx_type=TransactionType.MESSAGE_REWARD.value,
                        xp_change=xp_reward,
                        coins_change=coins_reward,
                        description=f"Message reward (x{multiplier:.3f})"
                    )
                    
                    if user.messages_count % MESSAGES_PER_TICKET == 0:
                        ticket = await ticket_repo.create(user.id)
                        ticket_created = ticket.code
                    
                    level_up = self.level_service.check_level_up(old_xp, user.xp)
                
                await uow.commit()
                
                return {
                    "success": True,
                    "xp_earned": xp_reward,
                    "coins_earned": coins_reward,
                    "halving_multiplier": multiplier,
                    "ticket_created": ticket_created,
                    "level_up": level_up,
                    "new_xp": user.xp,
                    "new_coins": user.coins,
                    "messages_count": user.messages_count,
                }

    async def admin_add_coins(
        self,
        user_id: int,
        amount: float,
        admin_id: int
    ) -> dict:
        """Админ выдаёт монеты из банка."""
        uow = UnitOfWork(self.session_factory)
        
        async with uow:
            user_repo = UserRepository(uow.session)
            bank_repo = BankRepository(uow.session)
            tx_repo = TransactionRepository(uow.session)
            
            user = await user_repo.get_for_update(user_id)
            if not user:
                return {"success": False, "error": "User not found"}
            
            bank_balance = await bank_repo.get_balance()
            if bank_balance < amount:
                return {
                    "success": False,
                    "error": f"Недостаточно в банке. Баланс: {bank_balance:,.2f}"
                }
            
            await bank_repo.withdraw(amount)
            user.coins += amount
            
            await tx_repo.create(
                user_id=user.id,
                tx_type=TransactionType.ADMIN_GRANT.value,
                coins_change=amount,
                description=f"Admin grant by {admin_id}"
            )
            
            await uow.commit()
            
            return {
                "success": True,
                "user_id": user.id,
                "amount": amount,
                "new_balance": user.coins
            }

    async def fire_drop(
        self,
        sender_id: int,
        amount: float,
        recipients_data: list[tuple[int, float]], # list of (user_id, amount)
        is_admin: bool = False
    ) -> dict:
        """Раздача монет (Fire Drop)."""
        lock = DistributedLock(self.redis)
        
        # Блокируем отправителя, если это не админ
        lock_key = f"fire_drop:{sender_id}" if not is_admin else "fire_drop:admin"
        
        async with lock.acquire(lock_key):
            uow = UnitOfWork(self.session_factory)
            
            async with uow:
                user_repo = UserRepository(uow.session)
                bank_repo = BankRepository(uow.session)
                tx_repo = TransactionRepository(uow.session)
                
                total_amount = sum(a for _, a in recipients_data)
                
                # Списание средств
                if is_admin:
                    bank_balance = await bank_repo.get_balance()
                    if bank_balance < total_amount:
                        return {"success": False, "reason": "insufficient_funds_bank", "balance": bank_balance}
                    await bank_repo.withdraw(total_amount)
                else:
                    sender = await user_repo.get_for_update(sender_id)
                    if not sender:
                         return {"success": False, "reason": "user_not_found"}
                    if sender.coins < total_amount:
                        return {"success": False, "reason": "insufficient_funds", "balance": sender.coins}
                    
                    sender.coins -= total_amount
                    
                    # Проводим средства через банк (Closed Loop Economy)
                    await bank_repo.deposit(total_amount)
                    await bank_repo.withdraw(total_amount)
                    
                    await tx_repo.create(
                        user_id=sender_id,
                        tx_type=TransactionType.TRANSFER_OUT.value,
                        coins_change=-total_amount,
                        description=f"Fire Drop sent to {len(recipients_data)} users"
                    )

                # Начисление средств получателям
                processed_count = 0
                for uid, amt in recipients_data:
                    recipient = await user_repo.get_by_id(uid)
                    if recipient:
                        recipient.coins += amt
                        processed_count += 1
                        # Создаем транзакцию для получателя
                        await tx_repo.create(
                            user_id=uid,
                            tx_type=TransactionType.TRANSFER_IN.value,
                            coins_change=amt,
                                description=f"Fire Drop received from {'Admin' if is_admin else sender_id}"
                            )
                
                    await uow.commit()
                
                    return {"success": True, "processed": processed_count}

    async def upgrade_katana(self, user_id: int) -> dict:
        """
        Улучшение катаны.
        
        Raises:
            UserNotFoundError: Если пользователь не найден.
            NoKatanaError: Если у пользователя нет катаны.
            CooldownError: Если не прошло время кулдауна.
            InsufficientFundsError: Если недостаточно средств.
        """
        lock = DistributedLock(self.redis)
        cost = KATANA_UPGRADE_COST
        
        async with lock.acquire(f"katana_up:{user_id}"):
            uow = UnitOfWork(self.session_factory)
            async with uow:
                user_repo = UserRepository(uow.session)
                bank_repo = BankRepository(uow.session)
                tx_repo = TransactionRepository(uow.session)
                
                user = await user_repo.get_for_update(user_id)
                if not user:
                    raise UserNotFoundError(user_id)
                
                if not user.has_katana:
                    raise NoKatanaError()
                
                # Проверка КД
                now = datetime.now(timezone.utc)
                if user.last_katana_up:
                    diff = now - user.last_katana_up
                    cooldown = timedelta(hours=KATANA_UPGRADE_COOLDOWN_HOURS)
                    if diff < cooldown:
                        remaining = cooldown - diff
                        raise CooldownError(remaining.total_seconds())

                # Проверка баланса
                if user.coins < cost:
                    raise InsufficientFundsError(cost, user.coins)
                
                # Списание
                user.coins -= cost
                await bank_repo.deposit(cost) # В банк
                
                await tx_repo.create(
                    user_id=user_id,
                    tx_type=TransactionType.PURCHASE.value,
                    coins_change=-cost,
                    description="Katana upgrade attempt"
                )
                
                # Попытка улучшения
                roll = random.random()
                is_success = roll < KATANA_WIN_CHANCE
                growth = 0.0
                
                if is_success:
                    growth = round(random.uniform(0.03, 0.60), 2)
                    user.katana_length += growth
                    user.last_katana_up = now
                else:
                    growth = round(random.uniform(0.01, 0.20), 2)
                    user.katana_length -= growth
                    if user.katana_length < 0:
                        user.katana_length = 0.0
                    user.last_katana_up = now
                    
                await uow.commit()
                
                return {
                    "is_upgraded": is_success,
                    "growth": growth,
                    "new_length": user.katana_length,
                    "cost": cost
                }

    async def admin_add_xp(
        self,
        user_id: int,
        amount: int,
        admin_id: int
    ) -> dict:
        """Админ выдаёт XP."""
        uow = UnitOfWork(self.session_factory)
        
        async with uow:
            user_repo = UserRepository(uow.session)
            tx_repo = TransactionRepository(uow.session)
            
            user = await user_repo.get_for_update(user_id)
            if not user:
                return {"success": False, "error": "User not found"}
            
            old_xp = user.xp
            user.xp += amount
            
            await tx_repo.create(
                user_id=user.id,
                tx_type=TransactionType.ADMIN_GRANT.value,
                xp_change=amount,
                description=f"Admin XP grant by {admin_id}"
            )
            
            level_up = self.level_service.check_level_up(old_xp, user.xp)
            
            await uow.commit()
            
            return {
                "success": True,
                "user_id": user.id,
                "amount": amount,
                "new_xp": user.xp,
                "level_up": level_up
            }

    async def confiscate_on_ban(self, user_id: int) -> float:
        """Конфискация монет при бане."""
        uow = UnitOfWork(self.session_factory)
        
        async with uow:
            user_repo = UserRepository(uow.session)
            bank_repo = BankRepository(uow.session)
            tx_repo = TransactionRepository(uow.session)
            
            user = await user_repo.get_for_update(user_id)
            if not user:
                return 0.0
            
            confiscated = user.coins
            if confiscated > 0:
                user.coins = 0
                await bank_repo.deposit(confiscated)
                
                await tx_repo.create(
                    user_id=user.id,
                    tx_type=TransactionType.BAN_CONFISCATION.value,
                    coins_change=-confiscated,
                    description="Confiscated on ban"
                )
            
            await uow.commit()
            return confiscated

    async def buy_katana(self, user_id: int) -> dict:
        """
        Покупка катаны.
        Стоимость: 1000 монет.
        """
        lock = DistributedLock(self.redis)
        cost = 1000.0
        
        async with lock.acquire(f"katana_buy:{user_id}"):
            uow = UnitOfWork(self.session_factory)
            async with uow:
                user_repo = UserRepository(uow.session)
                bank_repo = BankRepository(uow.session)
                tx_repo = TransactionRepository(uow.session)
                
                user = await user_repo.get_for_update(user_id)
                if not user:
                    raise UserNotFoundError(user_id)
                
                if user.has_katana:
                    return {"success": False, "reason": "already_has_katana"}
                
                if user.coins < cost:
                    raise InsufficientFundsError(cost, user.coins)
                
                user.coins -= cost
                user.has_katana = True
                user.katana_length = 1.0
                await bank_repo.deposit(cost)
                
                await tx_repo.create(
                    user_id=user_id,
                    tx_type=TransactionType.PURCHASE.value,
                    coins_change=-cost,
                    description="Katana purchase"
                )
                
                await uow.commit()
                
                return {
                    "success": True,
                    "cost": cost,
                    "new_balance": user.coins
                }

    async def get_bank_stats(self) -> dict:
        """Получить статистику банка."""
        uow = UnitOfWork(self.session_factory)
        
        async with uow:
            bank_repo = BankRepository(uow.session)
            tx_repo = TransactionRepository(uow.session)
            
            stats = await bank_repo.get_stats()
            circulation = await tx_repo.get_total_coins_in_circulation()
            multiplier = self._calculate_halving_multiplier(circulation)
            
            return {
                **stats,
                "in_circulation": circulation,
                "halving_multiplier": multiplier,
            }

    async def get_bank_balance(self) -> float:
        """Получить текущий баланс банка."""
        uow = UnitOfWork(self.session_factory)
        async with uow:
            bank_repo = BankRepository(uow.session)

            return await bank_repo.get_balance()

    async def distribute_zov_reward(self, user_id: int, amount: float) -> bool:
        """Выдать награду за созыв (без создания транзакции для скорости)."""
        uow = UnitOfWork(self.session_factory)
        async with uow:
            try:
                bank_repo = BankRepository(uow.session)
                user_repo = UserRepository(uow.session)
                
                # Снимаем с банка
                await bank_repo.withdraw(amount)
                
                # Начисляем юзеру
                user = await user_repo.get_for_update(user_id)
                if user:
                    user.coins += amount
                    await uow.commit()
                    return True
                return False
            except Exception:
                return False

    async def distribute_boss_reward(
        self,
        participant_ids: list[int],
        total_reward: float
    ) -> dict:
        """
        Распределить награду за босса между участниками.
        Средства берутся из банка Сенсея.
        """
        if not participant_ids or total_reward <= 0:
            return {"success": False, "count": 0, "reason": "no_participants_or_reward"}

        uow = UnitOfWork(self.session_factory)
        reward_per_user = total_reward / len(participant_ids)
        processed_count = 0
        
        async with uow:
            user_repo = UserRepository(uow.session)
            bank_repo = BankRepository(uow.session)
            tx_repo = TransactionRepository(uow.session)
            
            # 1. Проверяем баланс банка
            bank_balance = await bank_repo.get_balance()
            if bank_balance < total_reward:
                # Банк банкрот? Выдаем сколько есть или ничего?
                # По логике "все должно работать идеально", если банк пуст - это проблема банка.
                # Но давайте выдадим сколько есть пропорционально.
                if bank_balance <= 0:
                     return {"success": False, "reason": "bank_empty"}
                
                # Корректируем награду под баланс
                total_reward = bank_balance
                reward_per_user = total_reward / len(participant_ids)
            
            # 2. Снимаем с банка общую сумму
            await bank_repo.withdraw(total_reward)
            
            # 3. Раздаем участникам
            for user_id in participant_ids:
                user = await user_repo.get_for_update(int(user_id))
                if not user:
                    continue
                
                user.coins += reward_per_user
                processed_count += 1
                
                await tx_repo.create(
                    user_id=user.id,
                    tx_type=TransactionType.BOSS_WIN.value,
                    coins_change=reward_per_user,
                    description=f"Boss kill reward share ({total_reward} total)"
                )
            
            await uow.commit()
            
        return {
            "success": True, 
            "count": processed_count, 
            "reward_per_user": reward_per_user,
            "total_distributed": total_reward
        }

    async def process_boss_loss(
        self,
        participant_ids: list[int],
        penalty_amount: float
    ) -> dict:
        """Обработать проигрыш боссу (штраф участникам)."""
        if not participant_ids:
            return {"success": True, "count": 0}

        uow = UnitOfWork(self.session_factory)
        total_collected = 0.0
        processed_count = 0

        async with uow:
            user_repo = UserRepository(uow.session)
            bank_repo = BankRepository(uow.session)
            tx_repo = TransactionRepository(uow.session)

            for user_id in participant_ids:
                user = await user_repo.get_for_update(int(user_id))
                if not user:
                    continue

                user.coins -= penalty_amount
                total_collected += penalty_amount
                processed_count += 1

                await tx_repo.create(
                    user_id=user.id,
                    tx_type=TransactionType.BOSS_LOSS.value,
                    coins_change=-penalty_amount,
                    description="Boss battle loss penalty"
                )

            if total_collected > 0:
                try:
                    await bank_repo.deposit(total_collected)
                except ValueError:
                    pass 

            await uow.commit()

        return {"success": True, "count": processed_count, "total_collected": total_collected}


