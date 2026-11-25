"""
🛡️ Сервис модерации.
"""

from typing import List, Optional
from datetime import datetime, timedelta, timezone
import logging
import re

from aiogram import Bot
from src.core.config import settings
from src.infra.mongo.client import MongoClient
from src.services.bank_ledger import BankLedger

logger = logging.getLogger(__name__)

# Причина автобана за выход из чата. По ней же находится бан, ошибочно
# выданный за отписку от канала, поэтому строка вынесена в константу.
AUTO_BAN_REASON = "Выход из чата (AutoBan)"


class ModerationService:
    """Сервис для модерации пользователей."""

    def __init__(self, mongo_client: MongoClient):
        self.mongo_client = mongo_client
        self.db = mongo_client.database
        # Collections
        self.users = self.db.users
        self.transactions = self.db.transactions
        self.bank = self.db.bank  # legacy {_id: "main", balance: X}
        self.ledger = BankLedger(mongo_client)
        self.muted_users = self.db.muted_users  # For muted users
    async def ensure_mute_index(self):
        await self.muted_users.create_index([('user_id', 1), ('muted_until', 1)])

    async def handle_user_left(self, user_id: int) -> dict:
        """Обработать выход пользователя (автобан и конфискация)."""
        return await self.ban_user(
            user_id=user_id,
            reason=AUTO_BAN_REASON,
            confiscate_coins=True
        )

    async def ban_user(
        self,
        user_id: int,
        reason: str = "Нарушение правил",
        confiscate_coins: bool = True
    ) -> dict:
        """Забанить пользователя."""
        # Get user
        user = await self.users.find_one({"id": user_id})
        if not user:
            return {"success": False, "error": "User not found"}

        if user.get("is_banned"):
            return {"success": False, "error": "Already banned"}

        confiscated = 0.0
        if confiscate_coins:
            user_coins = user.get("coins", 0)
            if user_coins > 0:
                # Compare-and-set: only the request that actually zeroed the
                # old balance may put those coins back into the bank.  A
                # read-then-write race could otherwise deposit the same coins
                # twice and mint them.
                cleared = await self.users.update_one(
                    {"id": user_id, "coins": user_coins},
                    {"$set": {"coins": 0}},
                )
                if getattr(cleared, "matched_count", 1) == 1:
                    confiscated = user_coins
                    # Deposit to the canonical/legacy bank pool.
                    await self.ledger.deposit(confiscated)
                    # Create transaction record
                    tx_doc = {
                        "user_id": user_id,
                        "tx_type": "ban_confiscation",
                        "coins_change": -confiscated,
                        "description": f"Ban confiscation: {reason}",
                        "created_at": datetime.now(timezone.utc),
                    }
                    await self.transactions.insert_one(tx_doc)

        # Ban user
        await self.users.update_one(
            {"id": user_id},
            {"$set": {
                "is_banned": True,
                "ban_reason": reason,
                "updated_at": datetime.now(timezone.utc)
            }}
        )

        logger.info(f"User {user_id} banned. Reason: {reason}. Confiscated: {confiscated}")

        return {
            "success": True,
            "user_id": user_id,
            "username": user.get("username") or user.get("first_name"),
            "reason": reason,
            "confiscated": confiscated,
        }

    async def unban_user(self, user_id: int) -> dict:
        """Разбанить пользователя."""
        result = await self.users.update_one(
            {"id": user_id, "is_banned": True},
            {"$set": {
                "is_banned": False,
                "ban_reason": None,
                "updated_at": datetime.now(timezone.utc)
            }}
        )

        if result.matched_count == 0:
            return {"success": False, "error": "User not found or not banned"}

        logger.info(f"User {user_id} unbanned")
        return {"success": True, "user_id": user_id}

    async def unban_if_active_in_chat(self, bot: Bot, chat_id: int, user_id: int) -> dict:
        """
        Если пользователь забанен в боте (is_banned=True в MongoDB), но пишет сообщение
        в чате и не забанен в самом Telegram — снимаем бан в боте.

        Делает запрос к MongoDB только если флаг bana уже стоит, и get_chat_member
        в Telegram — только для пользователей из бана. Для обычных пользователей
        лишних запросов нет.
        """
        # Проверяем флаг бана в базе (один запрос к MongoDB)
        user = await self.users.find_one({"id": user_id}, {"is_banned": 1})
        if not user or not user.get("is_banned"):
            # Пользователь не в бане — лишних запросов нет
            return {"success": False, "reason": "not_banned"}

        # Флаг бана стоит — проверяем статус в Telegram-чате
        try:
            member = await bot.get_chat_member(chat_id, user_id)
            is_banned_in_tg = member.status in ("kicked", "restricted")
        except Exception as e:
            logger.warning(f"Failed to check chat member for user {user_id}: {e}")
            return {"success": False, "error": str(e)}

        if not is_banned_in_tg:
            # Не забанен в чате — снимаем бан в боте
            return await self.unban_user(user_id)

        return {"success": False, "reason": "banned_in_chat"}

    async def get_banned_users(self) -> List[dict]:
        """Получить список забаненных."""
        cursor = self.users.find({"is_banned": True})
        users = await cursor.to_list(length=None)

        return [
            {
                "user_id": u["id"],
                "username": u.get("username") or u.get("first_name") or f"User {u['id']}",
                "reason": u.get("ban_reason") or "Не указана",
            }
            for u in users
        ]

    async def restore_channel_unsubscribe_bans(self) -> dict:
        """Снять баны, выданные за отписку от канала задания.

        Пока ``on_user_leave`` не проверял тип чата, отписка от канала
        вызывала тот же автобан с конфискацией. Возвращаем только тех, чья
        причина бана — автобан за выход из чата, и только если игрок после
        бана ничего не заработал (иначе вернуть конфискованное неоткуда).
        """
        restored, skipped, amount_total = 0, 0, 0.0
        cursor = self.users.find({'is_banned': True,
                                  'ban_reason': AUTO_BAN_REASON})
        async for user in cursor:
            user_id = user.get('id')
            if user_id is None:
                continue
            # Сколько было конфисковано, видно по единственной записи журнала.
            record = await self.transactions.find_one(
                {'user_id': user_id, 'tx_type': 'ban_confiscation'},
                sort=[('created_at', -1)])
            amount = abs(float((record or {}).get('coins_change', 0) or 0))
            if amount > 0:
                refunded = await self._refund_from_bank(user_id, amount)
                if not refunded:
                    skipped += 1
                    continue
                amount_total += amount
            await self.users.update_one(
                {'id': user_id, 'is_banned': True},
                {'$set': {'is_banned': False, 'ban_reason': None,
                          'updated_at': datetime.now(timezone.utc)}})
            restored += 1
        logger.info('Restored %s channel-unsubscribe bans (%.2f coins), skipped %s',
                    restored, amount_total, skipped)
        return {'success': True, 'restored': restored, 'skipped': skipped,
                'coins_returned': amount_total}

    async def _refund_from_bank(self, user_id: int, amount: float) -> bool:
        """Вернуть конфискованное из банка. Без денег в банке — не банимся."""
        if amount <= 0:
            return True
        if not await self.ledger.try_withdraw(amount):
            logger.warning('Cannot refund %.2f to user %s: bank is short', amount, user_id)
            return False
        credited = await self.users.update_one(
            {'id': user_id}, {'$inc': {'coins': amount}})
        if getattr(credited, 'matched_count', 1) != 1:
            await self.ledger.deposit(amount)
            return False
        await self.transactions.insert_one({
            'user_id': user_id, 'tx_type': 'ban_refund', 'coins_change': amount,
            'description': 'Autoban refund: unsubscribing from a task channel is allowed',
            'created_at': datetime.now(timezone.utc),
        })
        return True

    async def unban_all_users(self) -> dict:
        """Амнистия: разбанить всех пользователей."""
        result = await self.users.update_many(
            {"is_banned": True},
            {"$set": {
                "is_banned": False,
                "ban_reason": None,
                "updated_at": datetime.now(timezone.utc)
            }}
        )
        affected = result.modified_count
        logger.info(f"Unbanned {affected} users (amnesty)")
        return {"success": True, "affected": affected}

    async def mute_user(
        self,
        user_id: int,
        muted_by: int = None,
        reason: str = None,
        until: datetime = None
    ) -> dict:
        """Замьютить пользователя."""
        if await self.is_muted(user_id):
            return {"success": False, "error": "Пользователь уже замьючен"}

        # Add to muted users collection
        mute_doc = {
            "user_id": user_id,
            "muted_by": muted_by,
            "reason": reason,
            "muted_at": datetime.now(timezone.utc),
            "muted_until": until,
        }
        await self.muted_users.update_one({"_id": user_id}, {"$set": mute_doc}, upsert=True)

        logger.info(f"User {user_id} muted. Reason: {reason}. Until: {until}")
        return {"success": True}

    async def unmute_user(self, user_id: int) -> dict:
        """Снять мьют с пользователя."""
        # Remove from muted users collection
        result = await self.muted_users.delete_many({"user_id": user_id})

        if result.deleted_count == 0:
            return {"success": False, "error": "Пользователь не был замьючен"}

        logger.info(f"User {user_id} unmuted")
        return {"success": True}

    async def is_muted(self, user_id: int) -> bool:
        """Проверить, замьючен ли пользователь."""
        active = {"$or": [{"muted_until": None}, {"muted_until": {"$gt": datetime.now(timezone.utc)}}]}
        return await self.muted_users.find_one({"user_id": user_id, **active}, {"_id": 1}) is not None

    async def get_muted_users(self) -> List[dict]:
        cursor = self.muted_users.find({"$or": [{"muted_until": None}, {"muted_until": {"$gt": datetime.now(timezone.utc)}}]})
        mutes = await cursor.to_list(length=None)

        # Convert to list of dicts (excluding MongoDB _id if needed, but we can keep it)
        return [
            {
                "user_id": m["user_id"],
                "muted_by": m.get("muted_by"),
                "reason": m.get("reason"),
                "muted_at": m.get("muted_at"),
                "muted_until": m.get("muted_until"),
            }
            for m in mutes
        ]

    async def _mute_target(self, username):
        name = username.removeprefix('@')
        if not re.fullmatch(r'[A-Za-z0-9_]{1,32}', name):
            return None
        rows = await self.users.find({'username': {'$regex': '^' + re.escape(name) + '$', '$options': 'i'}}).limit(2).to_list(length=2)
        return rows[0] if len(rows) == 1 else None

    async def mute_user_by_username(
        self,
        username: str,
        hours: float = 0,
        muted_by: int = None,
        reason: str = None
    ) -> dict:
        """Замьютить пользователя по нику."""
        # Find user by username
        user = await self._mute_target(username)
        if not user:
            return {"success": False, "error": "Не удалось определить пользователя. Ответь командой на его сообщение.", "username": username}
        user_id = user["id"]

        until = None
        if hours > 0:
            until = datetime.now(timezone.utc) + timedelta(hours=hours)

        result = await self.mute_user(user_id, muted_by, reason, until)
        if result["success"]:
            result["username"] = user.get("username") or user.get("first_name")
        return result

    async def unmute_user_by_username(self, username: str) -> dict:
        """Снять мьют по нику."""
        # Find user by username
        user = await self._mute_target(username)
        if not user:
            return {"success": False, "error": "Не удалось определить пользователя. Ответь командой на его сообщение.", "username": username}
        user_id = user["id"]

        result = await self.unmute_user(user_id)
        if result["success"]:
            result["username"] = user.get("username") or user.get("first_name")
        return result