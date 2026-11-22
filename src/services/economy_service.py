"""
💰 Сервис экономики.
"""

import asyncio
import math
import random
import time
from pymongo.errors import DuplicateKeyError
from typing import Optional, List, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase
from src.core.config import settings
from src.core.constants import (
    COINS_PER_MESSAGE,
    HALVING_THRESHOLDS,
    MESSAGES_PER_TICKET,
    XP_PER_MESSAGE,
    KATANA_UPGRADE_COST,
    KATANA_UPGRADE_COST_TABLE,
    KATANA_UPGRADE_COOLDOWN_HOURS,
    KATANA_WIN_CHANCE,
    STARTER_XP,
    STARTER_COINS,
    STARTER_KATANA_LENGTH,
)
from src.core.exceptions import (
    InsufficientFundsError,
    UserNotFoundError,
    CooldownError,
    NoKatanaError,
)
from src.infra.mongo.client import MongoClient
from src.services.level_service import LevelService
from src.services.emission_service import EmissionService
from src.services.bank_ledger import BankLedger
from src.services.referral_economy import transaction
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal

logger = logging.getLogger(__name__)


class EconomyService:
    """Сервис экономики с халвингом и атомарными операциями."""

    def __init__(self, mongo_client: MongoClient):
        self.mongo_client = mongo_client
        self.db: AsyncIOMotorDatabase = mongo_client.database
        self.level_service = LevelService()
        # Collections
        self.users = self.db.users
        self.transactions = self.db.transactions
        self.bank = self.db.bank  # Stores a single document with balance
        self.tickets = self.db.tickets
        self.emission = EmissionService(mongo_client)
        self.ledger = BankLedger(mongo_client)
        # Locks for simulating distributed locks (since we are single instance)
        self._locks = {}
        # We'll use a simple dictionary of asyncio locks
        # In a production distributed system, we'd use something like Redis or MongoDB atomic operations.
        # For now, we use asyncio.Lock per key.
        # Cache for total coins in circulation to avoid heavy aggregation on every message
        self._total_circulation_cache = (0.0, 0)  # (value, expiry_timestamp)
        self._circulation_lock = asyncio.Lock()
        self._cache_ttl = 10.0  # seconds

    def _get_lock(self, key: str) -> asyncio.Lock:
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]

    def _get_katana_upgrade_cost(self, katana_length: float) -> float:
        """Получить стоимость апгрейда катаны в зависимости от её длины."""
        for max_length, cost in KATANA_UPGRADE_COST_TABLE:
            if katana_length < max_length:
                return cost
        # Если длина больше всех порогов, возвращаем последнюю стоимость
        return KATANA_UPGRADE_COST_TABLE[-1][1]

    def _calculate_halving_multiplier(self, total_in_circulation: float) -> float:
        """Рассчитать множитель халвинга."""
        multiplier = 1.0
        for threshold in HALVING_THRESHOLDS:
            if total_in_circulation >= threshold:
                multiplier *= 0.5
            else:
                break
        return max(multiplier, 0.001)

    async def _get_bank_balance(self) -> float:
        """Read the canonical bank balance.

        Never refills an empty bank: minting new coins as a side effect of a
        read is how the old economy exceeded every supply limit.  The bank is
        filled once by :class:`EmissionService` and afterwards only moves coins
        that already exist.
        """
        return await self.ledger.balance()

    async def _set_bank_balance(self, balance: float) -> None:
        """Explicit bank rewrite (season reset/migration only).

        Reward paths must use :meth:`_withdraw_from_bank`; this setter is kept
        for compatibility with administrative code and deliberately does not
        invent a fresh emission counter.
        """
        await self.bank.update_one(
            {"_id": "single"},
            {"$set": {"coins": float(balance)}},
            upsert=True,
        )
        logger.warning("[BANK] Balance rewritten explicitly to %s", balance)

    async def _withdraw_from_bank(self, amount: float) -> bool:
        """Atomically debit the bank; False means the bank did not cover it.

        The guard and the ``$inc`` are one Mongo update, so two processes can
        never both spend the final coins.
        """
        return await self.ledger.try_withdraw(amount)

    async def _deposit_to_bank(self, amount: float) -> None:
        """Return coins that already belong to players back to the bank."""
        await self.ledger.deposit(amount)

    @staticmethod
    def _new_profile(user_id: int, **fields) -> dict:
        """Delegate to the one canonical profile shape (never a partial copy)."""
        from src.services.user_service import UserService
        return UserService.new_profile(user_id, **fields)

    async def _grant_starter(self, user_id: int) -> float:
        """Reserve a registration starter kit under the global emission cap."""
        try:
            return await self.emission.reserve_starter(user_id, STARTER_COINS)
        except Exception:
            logger.exception("Starter emission unavailable for user=%s", user_id)
            return 0.0

    async def process_message_reward(
        self,
        user_id: int,
        username: Optional[str] = None,
        first_name: str = "",
        last_name: Optional[str] = None,
        is_bot: bool = False,
        apply_rewards: bool = True,
        chat_id: Optional[int] = None,
    ) -> dict:
        """Обработать награду за сообщение."""
        logger.info(f"[ECONOMY] process_message_reward called for user {user_id}, apply_rewards={apply_rewards}")
        lock_key = f"message_reward:{user_id}"
        lock = self._get_lock(lock_key)
        async with lock:
            if apply_rewards and not is_bot:
                day = datetime.now(timezone.utc).date().isoformat()
                await self.users.update_one({'id': user_id, 'referral_version': 2,
                    'referral_activity_days': {'$ne': day}, 'referral_bonus_paid': {'$ne': True}},
                    {'$push': {'referral_activity_days': {'$each': [day], '$slice': -3}}})
            # Get or create user
            starter_amount = None
            user = await self.users.find_one({"id": user_id})
            if user is None:
                # Create new user with starter bonuses, but only after the
                # starter amount has been atomically reserved under the cap.
                starter = await self._grant_starter(user_id)
                user = self._new_profile(
                    user_id, username=username, first_name=first_name,
                    last_name=last_name, is_bot=is_bot, coins=starter,
                )
                try:
                    await self.users.insert_one(user)
                except DuplicateKeyError:
                    # A duplicate-key rejection guarantees this insert was not applied.
                    if starter:
                        await self.emission.release(starter, f"starter:{user_id}")
                    raise
                except Exception:
                    # A timeout can follow a successful insert. Keep the reservation
                    # rather than reopening issuance that may already be credited.
                    logger.warning("Starter reservation retained after uncertain insert: user=%s", user_id)
                    raise
                starter_amount = starter
                # Refresh the user document
                user = await self.users.find_one({"id": user_id})
                logger.info(f"[ECONOMY] Created new user {user_id} with starter bonuses: {STARTER_XP} XP, {starter} coins, {STARTER_KATANA_LENGTH}cm katana")
            else:
                # Update if needed
                update_data = {}
                if username is not None:
                    update_data["username"] = username
                if first_name:
                    update_data["first_name"] = first_name
                if last_name is not None:
                    update_data["last_name"] = last_name
                if update_data:
                    await self.users.update_one({"id": user_id}, {"$set": update_data})
                    user.update(update_data)

            if user.get("is_banned", False):
                logger.info(f"[ECONOMY] User {user_id} is banned, returning")
                return {"success": False, "reason": "banned"}

            xp_reward = 0
            coins_reward = 0.0
            multiplier = 0.0
            ticket_created = None
            level_up = None
            old_xp = user.get("xp", 0)

            if apply_rewards:
                # Rates remain unchanged and the expensive circulation snapshot keeps
                # its existing cache. Bank debit, user credit, count and journal
                # commit together, including the message milestone ticket.
                total_circulation = await self._get_total_coins_in_circulation()
                multiplier = self._calculate_halving_multiplier(total_circulation)
                xp_reward = int(XP_PER_MESSAGE * multiplier)
                from src.services.wave_activity import wave_message_reward
                wave_coins = wave_message_reward(chat_id)
                requested = wave_coins if wave_coins is not None else COINS_PER_MESSAGE * multiplier

                async def settle(session):
                    current = await self.users.find_one({'id': user_id}, session=session)
                    if not current or current.get('is_banned'):
                        return None
                    accounts = []
                    for bank_id, field in (('single', 'coins'), ('main', 'balance')):
                        doc = await self.bank.find_one({'_id': bank_id}, session=session) or {}
                        value = float(doc.get(field, 0) or 0)
                        if not math.isfinite(value):
                            raise ValueError('Invalid bank balance')
                        accounts.append((bank_id, field, Decimal(str(max(0.0, value)))))
                    available = sum((item[2] for item in accounts), Decimal(0))
                    paid = min(Decimal(str(max(0.0, requested))), available)
                    remaining = paid
                    for bank_id, field, balance in accounts:
                        take = min(remaining, balance)
                        if take <= 0:
                            continue
                        debit = await self.bank.update_one(
                            {'_id': bank_id, field: {'$gte': float(take)}},
                            {'$inc': {field: -float(take)}}, session=session)
                        if debit.matched_count != 1:
                            raise RuntimeError('Bank changed during message reward')
                        remaining -= take
                    if remaining > 0:
                        raise RuntimeError('Message reward was not fully funded')
                    credited = await self.users.update_one(
                        {'id': user_id, 'is_banned': {'$ne': True}},
                        {'$inc': {'messages_count': 1, 'xp': xp_reward, 'coins': float(paid)}},
                        session=session)
                    if credited.matched_count != 1:
                        raise RuntimeError('User unavailable during message reward')
                    updated = await self.users.find_one({'id': user_id}, session=session)
                    await self.transactions.insert_one({
                        'user_id': user_id, 'tx_type': 'message_reward', 'xp_change': xp_reward,
                        'coins_change': float(paid),
                        'description': ('Wave message reward (30 SenseiCoin)' if wave_coins is not None
                                        else f'Message reward (x{multiplier:.3f})'),
                        'created_at': datetime.now(timezone.utc),
                    }, session=session)
                    ticket = None
                    if updated.get('messages_count', 0) % MESSAGES_PER_TICKET == 0:
                        result = await self.tickets.insert_one({
                            'user_id': user_id, 'code': await self._generate_ticket_code(),
                            'created_at': datetime.now(timezone.utc),
                        }, session=session)
                        ticket = str(result.inserted_id)
                    return current, updated, float(paid), ticket

                settled = await transaction(self.mongo_client, settle)
                if settled is None:
                    return {'success': False, 'reason': 'banned'}
                before, user, coins_reward, ticket_created = settled
                old_xp = before.get('xp', 0)
                level_up = self.level_service.check_level_up(old_xp, user.get('xp', 0))

            # Return the result
            result = {
                "success": True,
                "xp_earned": xp_reward,
                "coins_earned": coins_reward,
                "halving_multiplier": multiplier,
                "ticket_created": ticket_created,
                "level_up": level_up,
                "new_xp": user.get("xp", 0),
                "new_coins": user.get("coins", 0.0),
                "messages_count": user.get("messages_count", 0),
                "starter_coins": starter_amount,
            }
            logger.info(f"[ECONOMY] process_message_reward result for user {user_id}: {result}")
            return result

    async def _get_total_coins_in_circulation(self) -> float:
        """Получить общее количество монет в обращении (сумма монет всех пользователей)."""
        # Check cache first
        now = time.time()
        cached_value, expiry = self._total_circulation_cache
        if now < expiry:
            return cached_value

        # Single-flight: concurrent messages share one expensive users scan.
        # This does not synchronize money writes or change the existing 10s TTL.
        async with self._circulation_lock:
            now = time.time()
            cached_value, expiry = self._total_circulation_cache
            if now < expiry:
                return cached_value
            pipeline = [{"$group": {"_id": None, "total": {"$sum": "$coins"}}}]
            result = await self.users.aggregate(pipeline).to_list(length=1)
            total = result[0].get("total", 0.0) if result else 0.0
            self._total_circulation_cache = (total, time.time() + self._cache_ttl)
            return total

    async def _generate_ticket_code(self) -> str:
        """Генерировать уникальный код билета."""
        # For simplicity, we'll use a random string. In production, we might want something more robust.
        import uuid
        return str(uuid.uuid4())[:8]

    # We'll stub out the rest of the methods for now, but we need to implement at least the ones that are called.
    # Since we don't know which ones are called, we'll try to implement the critical ones.

    async def _bank_user_transfer(self, user_id: int, amount: float, *, admin_id=None) -> dict:
        """Move bank funds and optionally journal them in one Mongo transaction.

        This is not an idempotency key for separate command retries. A failed or
        ambiguous transaction must not be retried as a new command automatically.
        """
        try:
            amount = float(amount)
        except (TypeError, ValueError, OverflowError):
            return {'success': False, 'error': 'Укажите корректную сумму.'}
        if not math.isfinite(amount) or amount <= 0:
            return {'success': False, 'error': 'Укажите корректную сумму.'}

        requested = Decimal(str(amount))

        async def transfer(session):
            user = await self.users.find_one({'id': user_id}, session=session)
            if not user:
                return {'success': False, 'error': 'Пользователь не найден.'}
            accounts = []
            for bank_id, field in (('single', 'coins'), ('main', 'balance')):
                doc = await self.bank.find_one({'_id': bank_id}, session=session) or {}
                balance = float(doc.get(field, 0) or 0)
                if not math.isfinite(balance):
                    raise ValueError('Invalid bank balance')
                accounts.append((bank_id, field, Decimal(str(max(0.0, balance)))))
            balance = sum((account[2] for account in accounts), Decimal(0))
            if balance < requested:
                return {'success': False, 'error': f'Недостаточно в банке. Баланс: {balance:,.2f}'}
            remaining = requested
            for bank_id, field, available in accounts:
                take = min(remaining, available)
                if take <= 0:
                    continue
                debit = await self.bank.update_one({'_id': bank_id, field: {'$gte': float(take)}},
                    {'$inc': {field: -float(take)}}, session=session)
                if debit.matched_count != 1:
                    raise RuntimeError('Bank balance changed during transfer')
                remaining -= take
            if remaining > 0:
                raise RuntimeError('Bank transfer was not fully funded')
            credited = await self.users.update_one({'id': user_id}, {'$inc': {'coins': amount}}, session=session)
            if credited.matched_count != 1:
                raise RuntimeError('User unavailable during bank transfer')
            if admin_id is not None:
                await self.transactions.insert_one({
                    'user_id': user_id, 'tx_type': 'admin_grant', 'coins_change': amount,
                    'description': f'Admin grant by {admin_id}', 'created_at': datetime.now(timezone.utc),
                }, session=session)
            updated = await self.users.find_one({'id': user_id}, session=session)
            return {'success': True, 'user_id': user_id, 'amount': amount,
                    'new_balance': updated.get('coins', 0.0)}

        return await transaction(self.mongo_client, transfer)

    async def admin_add_coins(self, user_id: int, amount: float, admin_id: int) -> dict:
        """Issue an admin grant from the existing bank, not from emission."""
        return await self._bank_user_transfer(user_id, amount, admin_id=admin_id)

    async def upgrade_katana(self, user_id: int) -> dict:
        """
        Улучшение катаны.
        """
        lock_key = f"katana_up:{user_id}"
        lock = self._get_lock(lock_key)
        async with lock:
            # Get user to determine katana length for dynamic cost
            user = await self.users.find_one({"id": user_id})
            if not user:
                raise UserNotFoundError(user_id)
            if not user.get("has_katana", False):
                raise NoKatanaError()

            # Calculate dynamic cost based on katana length
            katana_length = user.get("katana_length", 0.0)
            cost = self._get_katana_upgrade_cost(katana_length)
            # Keep the actual starting length for the upgrade receipt, including
            # failures clamped to zero. Presentation must not re-read/retry it.
            old_length = user.get("katana_length", 0.0)
            # Check cooldown
            now = datetime.now(timezone.utc)
            snapshot_last_upgrade = user.get("last_katana_up")
            last_katana_up = snapshot_last_upgrade
            if last_katana_up:
                # Ensure it's timezone aware
                if last_katana_up.tzinfo is None:
                    last_katana_up = last_katana_up.replace(tzinfo=timezone.utc)
                diff = now - last_katana_up
                cooldown = timedelta(hours=KATANA_UPGRADE_COOLDOWN_HOURS)
                if diff < cooldown:
                    remaining = cooldown - diff
                    raise CooldownError(remaining.total_seconds())
            # Check balance
            if user.get("coins", 0.0) < cost:
                raise InsufficientFundsError(cost, user.get("coins", 0.0))
            # Random outcome is fixed across transaction retries.
            from src.services.referral_economy import distribute, activate, transaction
            import uuid
            event = 'katana:' + uuid.uuid4().hex
            is_success = random.random() < KATANA_WIN_CHANCE
            growth = round(random.uniform(0.03, 0.60) if is_success else random.uniform(0.01, 0.20), 2)
            new_length = old_length + growth if is_success else max(0.0, old_length - growth)

            receipt = dict(is_upgraded=is_success, old_length=old_length, growth=growth,
                           new_length=new_length, cost=cost)
            async def purchase(tx):
                current = await self.users.find_one({'id': user_id}, session=tx)
                if not current or current.get('is_banned'):
                    raise UserNotFoundError(user_id)
                if not current.get('has_katana'):
                    raise NoKatanaError()
                if current.get('last_katana_up') != snapshot_last_upgrade or current.get('katana_length', 0.0) != old_length:
                    raise CooldownError(KATANA_UPGRADE_COOLDOWN_HOURS * 3600)
                changes = {'katana_length': new_length, 'last_katana_up': now, 'last_katana_receipt': receipt}
                if current.get('referral_version') == 2:
                    # Upgrading is genuine gameplay too, including on otherwise silent days.
                    days = sorted(set(current.get('referral_activity_days') or []) | {now.date().isoformat()})[-3:]
                    changes.update(referral_activity_days=days, referral_paid_upgrade=True)
                    current.update(referral_activity_days=days, referral_paid_upgrade=True)
                debit = await self.users.update_one({'id': user_id, 'coins': {'$gte': cost}},
                    {'$inc': {'coins': -cost}, '$set': changes}, session=tx)
                if debit.matched_count != 1:
                    raise InsufficientFundsError(cost, current.get('coins', 0))
                await self.transactions.insert_one(dict(_id=event, user_id=user_id, tx_type='purchase',
                    coins_change=-cost, description='Katana upgrade attempt', created_at=now), session=tx)
                await distribute(self.db, current, cost, event, tx)
                await activate(self.db, current, event, tx)
                return receipt
            return await transaction(self.mongo_client, purchase)

    # We'll stub out the other methods to avoid errors, but they should be implemented properly.
    async def admin_add_xp(
        self,
        user_id: int,
        amount: int,
        admin_id: int
    ) -> dict:
        """Админ выдаёт XP."""
        user = await self.users.find_one({"id": user_id})
        if not user:
            return {"success": False, "error": "User not found"}
        old_xp = user.get("xp", 0)
        await self.users.update_one(
            {"id": user_id},
            {"$inc": {"xp": amount}}
        )
        new_xp = old_xp + amount
        level_up = self.level_service.check_level_up(old_xp, new_xp)
        # Create transaction
        tx_doc = {
            "user_id": user_id,
            "tx_type": "admin_grant",
            "xp_change": amount,
            "description": f"Admin XP grant by {admin_id}",
            "created_at": datetime.now(timezone.utc),
        }
        await self.transactions.insert_one(tx_doc)
        return {
            "success": True,
            "user_id": user_id,
            "amount": amount,
            "new_xp": new_xp,
            "level_up": level_up
        }

    async def confiscate_on_ban(self, user_id: int) -> float:
        """Конфискация монет при бане."""
        user = await self.users.find_one({"id": user_id})
        if not user:
            return 0.0
        confiscated = user.get("coins", 0.0)
        if confiscated > 0:
            await self.users.update_one(
                {"id": user_id},
                {"$set": {"coins": 0.0}}
            )
            await self._deposit_to_bank(confiscated)
            # Create transaction
            tx_doc = {
                "user_id": user_id,
                "tx_type": "ban_confiscation",
                "coins_change": -confiscated,
                "description": "Confiscated on ban",
                "created_at": datetime.now(timezone.utc),
            }
            await self.transactions.insert_one(tx_doc)
        return confiscated

    async def buy_katana(self, user_id: int) -> dict:
        """
        Покупка катаны.
        Стоимость: 1000 монет.
        """
        lock_key = f"katana_buy:{user_id}"
        lock = self._get_lock(lock_key)
        async with lock:
            cost = 1000.0
            user = await self.users.find_one({"id": user_id})
            if not user:
                raise UserNotFoundError(user_id)
            if user.get("has_katana", False):
                return {"success": False, "reason": "already_has_katana"}
            if user.get("coins", 0.0) < cost:
                raise InsufficientFundsError(cost, user.get("coins", 0.0))
            # Deduct coins
            await self.users.update_one(
                {"id": user_id},
                {"$inc": {"coins": -cost}}
            )
            await self._deposit_to_bank(cost)
            # Update user
            await self.users.update_one(
                {"id": user_id},
                {"$set": {"has_katana": True, "katana_length": 1.0}}
            )
            # Create transaction
            tx_doc = {
                "user_id": user_id,
                "tx_type": "purchase",
                "coins_change": -cost,
                "description": "Katana purchase",
                "created_at": datetime.now(timezone.utc),
            }
            await self.transactions.insert_one(tx_doc)
            # Get updated user
            user = await self.users.find_one({"id": user_id})
            return {
                "success": True,
                "cost": cost,
                "new_balance": user.get("coins", 0.0)
            }

    async def get_bank_stats(self) -> dict:
        """Получить статистику банка."""
        balance = await self._get_bank_balance()
        circulation = await self._get_total_coins_in_circulation()
        multiplier = self._calculate_halving_multiplier(circulation)
        return {
            "balance": balance,
            "in_circulation": circulation,
            "halving_multiplier": multiplier,
        }

    async def get_bank_balance(self) -> float:
        """Получить текущий баланс банка."""
        return await self._get_bank_balance()

    async def distribute_zov_reward(self, user_id: int, amount: float) -> bool:
        """Pay the existing zov reward atomically, without a transaction journal entry."""
        return (await self._bank_user_transfer(user_id, amount))['success']

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

        # Check bank balance
        bank_balance = await self._get_bank_balance()
        if bank_balance < total_reward:
            # If bank doesn't have enough, we adjust the reward to what's available
            if bank_balance <= 0:
                return {"success": False, "reason": "bank_empty"}
            total_reward = bank_balance

        reward_per_user = total_reward / len(participant_ids)
        processed_count = 0

        # Withdraw total reward from bank; do not credit players if the debit
        # raced away.
        if not await self._withdraw_from_bank(total_reward):
            return {"success": False, "count": 0, "reason": "insufficient_bank"}

        # Distribute to participants
        for user_id in participant_ids:
            await self.users.update_one(
                {"id": user_id},
                {"$inc": {"coins": reward_per_user}}
            )
            # Create transaction for each user
            tx_doc = {
                "user_id": user_id,
                "tx_type": "boss_win",
                "coins_change": reward_per_user,
                "description": f"Boss kill reward share ({total_reward} total)",
                "created_at": datetime.now(timezone.utc),
            }
            await self.transactions.insert_one(tx_doc)
            processed_count += 1

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

        total_collected = 0.0
        processed_count = 0

        for user_id in participant_ids:
            await self.users.update_one(
                {"id": user_id},
                {"$inc": {"coins": -penalty_amount}}
            )
            # Create transaction
            tx_doc = {
                "user_id": user_id,
                "tx_type": "boss_loss",
                "coins_change": -penalty_amount,
                "description": "Boss battle loss penalty",
                "created_at": datetime.now(timezone.utc),
            }
            await self.transactions.insert_one(tx_doc)
            total_collected += penalty_amount
            processed_count += 1

        # Deposit collected penalties to bank
        if total_collected > 0:
            await self._deposit_to_bank(total_collected)

        return {"success": True, "count": processed_count, "total_collected": total_collected}

    async def process_game_win(
        self,
        user_id: int,
        coins: float = 0.0,
        xp: int = 0,
        description: str = "Game Win"
    ) -> dict:
        """Process a game win reward for a user."""
        lock_key = f"game_win:{user_id}"
        lock = self._get_lock(lock_key)
        async with lock:
            # Get or create user
            user = await self.users.find_one({"id": user_id})
            if user is None:
                # Create new user with starter bonuses, capped like any mint.
                starter = await self._grant_starter(user_id)
                user = self._new_profile(user_id, coins=starter)
                try:
                    await self.users.insert_one(user)
                except DuplicateKeyError:
                    # A duplicate-key rejection guarantees this insert was not applied.
                    if starter:
                        await self.emission.release(starter, f"starter:{user_id}")
                    raise
                except Exception:
                    # A timeout can follow a successful insert. Keep the reservation
                    # rather than reopening issuance that may already be credited.
                    logger.warning("Starter reservation retained after uncertain insert: user=%s", user_id)
                    raise
                # Refresh the user document
                user = await self.users.find_one({"id": user_id})
                logger.info(f"[ECONOMY] Created new user {user_id} with starter bonuses: {STARTER_XP} XP, {starter} coins, {STARTER_KATANA_LENGTH}cm katana")
            else:
                # Update if needed - but for game win we don't typically update username/name
                pass

            coins = max(0.0, float(coins))

            async def pay(session):
                current = await self.users.find_one({'id': user_id}, session=session)
                if not current or current.get('is_banned'):
                    return {'success': False, 'reason': 'banned'}
                remaining = coins
                bank_balance = 0.0
                accounts = []
                for bank_id, field in (('single', 'coins'), ('main', 'balance')):
                    account = await self.bank.find_one({'_id': bank_id}, session=session) or {}
                    available = max(0.0, float(account.get(field, 0) or 0))
                    accounts.append((bank_id, field, available))
                    bank_balance += available
                if coins > bank_balance:
                    return {'success': False, 'reason': 'insufficient_bank',
                            'bank_balance': bank_balance, 'required': coins}
                for bank_id, field, available in accounts:
                    take = min(remaining, available)
                    if take <= 0:
                        continue
                    debit = await self.bank.update_one(
                        {'_id': bank_id, field: {'$gte': take}},
                        {'$inc': {field: -take}}, session=session)
                    if not debit.matched_count:
                        # Abort instead of committing a partial debit.
                        raise RuntimeError('bank balance changed during game payout')
                    remaining -= take
                credited = await self.users.update_one(
                    {'id': user_id, 'is_banned': {'$ne': True}},
                    {'$inc': {'xp': xp, 'coins': coins}}, session=session)
                if not credited.matched_count:
                    raise RuntimeError('player unavailable during game payout')
                await self.transactions.insert_one({
                    'user_id': user_id, 'tx_type': 'game_win', 'xp_change': xp,
                    'coins_change': coins, 'description': description,
                    'created_at': datetime.now(timezone.utc)}, session=session)
                old_xp = current.get('xp', 0)
                new_xp = old_xp + xp
                return {'success': True, 'xp_earned': xp, 'coins_earned': coins,
                        'new_xp': new_xp, 'new_coins': current.get('coins', 0.0) + coins,
                        'level_up': self.level_service.check_level_up(old_xp, new_xp) if xp > 0 else None}

            return await transaction(self.mongo_client, pay)

    async def fire_drop(
        self,
        sender_id: int,
        amount: float,
        recipients_data: List[Tuple[int, Optional[str], int]],
        is_admin: bool
    ) -> dict:
        """Process a fire drop: distribute coins from sender (or bank if admin) to recipients."""
        logger.info(f"[ECONOMY] fire_drop called: sender_id={sender_id}, amount={amount}, is_admin={is_admin}, recipients={len(recipients_data)}")

        # Use a lock for the sender to prevent concurrent modifications
        lock_key = f"fire_drop:{sender_id}"
        lock = self._get_lock(lock_key)
        async with lock:
            if is_admin:
                # Admin uses bank funds
                bank_balance = await self._get_bank_balance()
                if bank_balance < amount:
                    return {
                        "success": False,
                        "reason": "insufficient_funds_bank",
                        "balance": bank_balance
                    }
                # Withdraw from bank
                success = await self._withdraw_from_bank(amount)
                if not success:
                    return {"success": False, "reason": "bank_withdraw_failed"}
                # Create transaction for bank withdrawal
                tx_doc = {
                    "user_id": None,  # Bank transaction
                    "tx_type": "fire_drop_bank_withdraw",
                    "coins_change": -amount,
                    "description": f"Fire drop bank withdrawal for sender {sender_id}",
                    "created_at": datetime.now(timezone.utc),
                }
                await self.transactions.insert_one(tx_doc)
                logger.info(f"[ECONOMY] Fire drop: withdrew {amount} from bank")
            else:
                # Non-admin uses personal balance
                sender = await self.users.find_one({"id": sender_id})
                if not sender:
                    return {"success": False, "reason": "sender_not_found"}
                sender_balance = sender.get("coins", 0.0)
                if sender_balance < amount:
                    return {
                        "success": False,
                        "reason": "insufficient_funds",
                        "balance": sender_balance
                    }
                # Deduct from sender atomically. A read-then-write race could
                # otherwise let one balance fund two drops, and the second set
                # of recipients would be new coins.
                debited = await self.users.update_one(
                    {"id": sender_id, "coins": {"$gte": amount}},
                    {"$inc": {"coins": -amount}},
                )
                if getattr(debited, "matched_count", 1) != 1:
                    return {"success": False, "reason": "insufficient_funds"}
                # Create transaction for sender deduction
                tx_doc = {
                    "user_id": sender_id,
                    "tx_type": "fire_drop_sent",
                    "coins_change": -amount,
                    "description": f"Fire drop sent to {len(recipients_data)} recipients",
                    "created_at": datetime.now(timezone.utc),
                }
                await self.transactions.insert_one(tx_doc)
                logger.info(f"[ECONOMY] Fire drop: deducted {amount} from sender {sender_id}")

            # Distribute to recipients
            for recipient_id, _, amt in recipients_data:
                # Note: recipients_data tuples are (user_id, username, amount)
                await self.users.update_one(
                    {"id": recipient_id},
                    {"$inc": {"coins": amt}}
                )
                # Create transaction for each recipient
                tx_doc = {
                    "user_id": recipient_id,
                    "tx_type": "fire_drop_received",
                    "coins_change": amt,
                    "description": f"Fire drop received from sender {sender_id}",
                    "created_at": datetime.now(timezone.utc),
                }
                await self.transactions.insert_one(tx_doc)

            logger.info(f"[ECONOMY] Fire drop: distributed {amount} to {len(recipients_data)} recipients")
            return {"success": True}