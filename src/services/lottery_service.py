"""
 Сервис лотереи.
"""

from typing import List, Dict, Optional
import random
import asyncio
from datetime import datetime, timezone

from src.domain.tickets import active_ticket_filter
from src.core.config import settings
from src.infra.mongo.client import MongoClient
import logging

logger = logging.getLogger(__name__)


class LotteryService:
    """Сервис для проведения розыгрышей."""

    def __init__(self, mongo_client: MongoClient):
        self.mongo_client = mongo_client
        self.db = mongo_client.database
        # Collections
        self.tickets = self.db.tickets  # For ticket tracking
        self.users = self.db.users

    @staticmethod
    def _present(member) -> bool:
        status = member.status
        return (status in ('creator', 'administrator', 'member') or
                (status == 'restricted' and bool(getattr(member, 'is_member', False))))

    async def run_lottery(self, winners_count: int, *, chat_id: int, bot) -> List[dict]:
        """Uniformly draw eligible tickets, not users, from this Telegram chat.

        Stream in owner order so a holder is checked once and Python memory is
        O(winners_count), not O(all tickets). Any membership error aborts the
        whole draw before burning anything rather than biasing the draw.
        """
        from src.services.referral_economy import transaction

        if not 1 <= winners_count <= 10:
            raise ValueError('winners_count must be between 1 and 10')
        active = active_ticket_filter()
        cursor = self.tickets.find(active, {'user_id': 1, 'code': 1}).sort(
            [('user_id', 1), ('_id', 1)]).batch_size(200)
        selected = []
        seen = 0
        last_user_id = None
        member = None
        try:
            async for ticket in cursor:
                uid = ticket.get('user_id')
                if isinstance(uid, bool) or not isinstance(uid, int) or uid <= 0:
                    continue
                uid = int(uid)  # BSON int64 is an int subclass, common for Telegram IDs.
                if uid != last_user_id:
                    member = await asyncio.wait_for(bot.get_chat_member(chat_id, uid), timeout=10)
                    last_user_id = uid
                if not self._present(member) or getattr(getattr(member, 'user', None), 'is_bot', False):
                    continue
                seen += 1
                item = (ticket, member.user)
                if len(selected) < winners_count:
                    selected.append(item)
                else:
                    index = random.randrange(seen)
                    if index < winners_count:
                        selected[index] = item

        finally:
            await cursor.close()

        # Telegram membership and Mongo cannot share an atomic snapshot. Check
        # again immediately before burning; never silently replace a departed
        # winner because that would skew the draw.
        verified = set()
        for ticket, _ in selected:
            uid = ticket['user_id']
            if uid not in verified:
                current = await asyncio.wait_for(bot.get_chat_member(chat_id, uid), timeout=10)
                if not self._present(current) or getattr(current.user, 'is_bot', False):
                    raise RuntimeError('Membership changed during lottery; retry')
                verified.add(uid)

        if not selected:
            return []
        random.shuffle(selected)
        async def burn(session):
            now = datetime.now(timezone.utc)
            for ticket, _ in selected:
                result = await self.tickets.update_one(
                    {'_id': ticket['_id'], 'burned': {'$ne': True},
                     'is_burned': {'$ne': True}},
                    {'$set': {'burned': True, 'is_burned': True,
                              'burn_reason': 'lottery_win', 'burned_at': now}}, session=session)
                if result.matched_count != 1:
                    raise RuntimeError('Ticket changed during lottery; retry')
        await transaction(self.mongo_client, burn)
        winners = []
        for ticket, user in selected:
            name = ' '.join(filter(None, (user.first_name, user.last_name))) or f"User {user.id}"
            winners.append({'user_id': user.id, 'username': user.username,
                            'full_name': name, 'ticket_code': ticket['code']})
        return winners

    async def admin_add_ticket(self, user_id: int, admin_id: int) -> dict:
        """Админ выдаёт билет пользователю."""
        try:
            # Check if user exists
            user = await self.users.find_one({"id": user_id})
            if not user:
                return {"success": False, "error": "User not found"}

            # Generate ticket ID using atomic counter
            counter_doc = await self.db.counters.find_one_and_update(
                {"_id": "ticket_id"},
                {"$inc": {"seq": 1}},
                upsert=True,
                return_document=True
            )
            next_id = counter_doc["seq"]

            ticket_doc = {
                "_id": next_id,
                "user_id": user_id,
                "code": f"TICKET-{next_id:08d}",
                "created_at": datetime.now(timezone.utc),
                "burned": False
            }
            await self.tickets.insert_one(ticket_doc)

            return {
                "success": True,
                "user_id": user["id"],
                "username": user.get("username") or user.get("first_name") or f"User {user['id']}",
                "ticket_code": ticket_doc["code"],
            }
        except Exception as e:
            logger.error(f"Error in admin_add_ticket for user {user_id}: {e}")
            return {"success": False, "error": "Internal error"}

    async def admin_burn_user_tickets(self, user_id: int, admin_id: int) -> dict:
        """Админ сжигает все билеты пользователя."""
        # Check if user exists
        user = await self.users.find_one({"id": user_id})
        if not user:
            return {"success": False, "error": "User not found"}

        # Burn all user's tickets
        result = await self.tickets.update_many(
            {
                "user_id": user_id,
                "burned": {"$ne": True},
                "is_burned": {"$ne": True},
            },
            {
                "$set": {
                    "burned": True,
                    "is_burned": True,
                    "burn_reason": f"admin_burn_by_{admin_id}",
                    "burned_at": datetime.now(timezone.utc)
                }
            }
        )

        burned_count = result.modified_count

        return {
            "success": True,
            "user_id": user_id,
            "username": user.get("username") or user.get("first_name") or f"User {user_id}",
            "burned_count": burned_count
        }

    async def add_ticket(self, user_id: int, source: str = "system") -> dict:
        """Добавить билет пользователю (для системных наград, таких как выигрыш в играх).

        Args:
            user_id: ID пользователя
            source: Источник получения билета (для информации)

        Returns:
            Dict с результатом операции
        """
        # Для системных наград используем специальный системный admin_id = 0
        # В реальной системе можно создать отдельный системный аккаунт
        return await self.admin_add_ticket(user_id, 0)

    async def get_lottery_stats(self) -> dict:
        """Статистика для лотереи."""
        # Total active (not burned) tickets
        total_active = await self.tickets.count_documents(active_ticket_filter())

        # Top holders - users with most active tickets
        pipeline = [
            {"$match": active_ticket_filter()},
            {"$group": {"_id": "$user_id", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 5}
        ]
        cursor = self.tickets.aggregate(pipeline)
        top_holders_raw = await cursor.to_list(length=None)

        # Get user info for top holders
        top_holders = []
        for holder in top_holders_raw:
            user_id = holder["_id"]
            count = holder["count"]
            user = await self.users.find_one({"id": user_id})
            username = user.get("username") if user else f"User {user_id}"
            top_holders.append({
                "user_id": user_id,
                "username": username,
                "ticket_count": count
            })

        return {
            "total_active_tickets": total_active,
            "top_holders": top_holders,
        }