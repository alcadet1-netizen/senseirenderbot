"""
✅ Репозиторий чеков SenseiCheck на MongoDB.
"""

import json
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Tuple, Dict, Any

from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorDatabase

from src.domain.repositories.base import BaseRepository


class SenseiCheckRepository(BaseRepository):
    """Репозиторий для работы с чеками SenseiCheck на MongoDB."""

    def __init__(self, database: AsyncIOMotorDatabase):
        super().__init__(database["sensei_checks"])
        # Мы также будем нуждаться в коллекции активаций
        self.activation_collection = database["sensei_check_activations"]
        self.initialized = True

    # ==================== CRUD для чеков ====================

    async def create(
        self,
        *,
        code: str,
        created_by: int,
        amount_ton: float,
        activation_limit: int,
        channels: list[str] | None = None,
        referral_percent: int = 0,
        message_text: str | None = None,
        photo_file_id: str | None = None,
        video_file_id: str | None = None,
        password: str | None = None,
        title: str | None = None,
        expires_at: datetime | None = None,
        requires_captcha: bool = False,
    ) -> dict:
        """Создать новый чек."""
        channels_list = channels or []
        if requires_captcha:
            channels_list = ["__CAPTCHA__"] + channels_list

        check = {
            "_id": code,  # используем код как _id для простоты поиска
            "code": code,
            "created_by": created_by,
            "amount_ton": amount_ton,
            "activation_limit": activation_limit,
            "channels": channels_list,  # храним как массив
            "referral_percent": referral_percent,
            "message_text": message_text,
            "photo_file_id": photo_file_id,
            "video_file_id": video_file_id,
            "password": password,
            "title": title,
            "expires_at": expires_at,
            "is_active": True,
            "activations_used": 0,
            "created_at": datetime.now(timezone.utc),
        }
        await self.collection.insert_one(check)
        return check

    async def get_by_code(
        self,
        code: str,
        *,
        for_update: bool = False
    ) -> Optional[dict]:
        """Получить чек по коду."""
        # Для простоты игнорируем for_update (MongoDB транзакции сложнее)
        check = await self.collection.find_one({"_id": code})
        return check

    async def get_by_id(
        self,
        check_id: int,
        *,
        for_update: bool = False
    ) -> Optional[dict]:
        """Получить чек по ID (в нашей схеме ID означает код)."""
        return await self.get_by_code(str(check_id), for_update=for_update)

    async def get_user_checks(
        self,
        user_id: int,
        *,
        only_active: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """Получить чеки пользователя с пагинацией."""
        filter_q = {"created_by": user_id}
        if only_active:
            filter_q["is_active"] = True

        # Count
        total = await self.collection.count_documents(filter_q)

        # Data
        cursor = self.collection.find(filter_q).sort("created_at", -1).skip(offset).limit(limit)
        checks = await cursor.to_list(length=limit)
        return checks, total

    async def get_by_creator(self, user_id: int) -> List[dict]:
        """Alias for compatibility."""
        checks, _ = await self.get_user_checks(user_id, limit=100)
        return checks

    async def get_all_checks(
        self,
        *,
        only_active: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """Получить все чеки с пагинацией (для админа)."""
        filter_q = {}
        if only_active:
            filter_q["is_active"] = True

        total = await self.collection.count_documents(filter_q)

        cursor = self.collection.find(filter_q).sort("created_at", -1).skip(offset).limit(limit)
        checks = await cursor.to_list(length=limit)
        return checks, total

    async def get_all_for_admin(self, limit: int, offset: int) -> Tuple[List[dict], int]:
        """Alias for compatibility."""
        return await self.get_all_checks(limit=limit, offset=offset)

    async def update_check(
        self,
        check: dict,
        **kwargs,
    ) -> dict:
        """Обновить чек."""
        # Убираем _id из обновления, чтобы не конфликтовать
        update_data = {k: v for k, v in kwargs.items() if k != "_id"}
        if not update_data:
            return check
        update_data["updated_at"] = datetime.now(timezone.utc)
        await self.collection.update_one({"_id": check["_id"]}, {"$set": update_data})
        # Обновим локальный объект для возврата
        check.update(update_data)
        return check

    async def delete_check(self, code: str, user_id: int) -> bool:
        """Деактивировать чек (мягкое удаление)."""
        result = await self.collection.update_one(
            {"_id": code, "created_by": user_id},
            {"$set": {"is_active": False, "updated_at": datetime.now(timezone.utc)}}
        )
        return result.modified_count > 0

    async def deactivate(self, check: dict) -> None:
        """Деактивировать чек."""
        await self.collection.update_one(
            {"_id": check["_id"]},
            {"$set": {"is_active": False, "updated_at": datetime.now(timezone.utc)}}
        )

    async def activate(self, check: dict) -> None:
        """Активировать чек."""
        await self.collection.update_one(
            {"_id": check["_id"]},
            {"$set": {"is_active": True, "updated_at": datetime.now(timezone.utc)}}
        )

    async def restore_check(self, code: str, user_id: int) -> bool:
        """Восстановление чека"""
        result = await self.collection.update_one(
            {"_id": code, "created_by": user_id},
            {"$set": {"is_active": True, "updated_at": datetime.now(timezone.utc)}}
        )
        return result.modified_count > 0

    async def admin_restore_check(self, code: str) -> bool:
        """Админское восстановление чека"""
        result = await self.collection.update_one(
            {"_id": code},
            {"$set": {"is_active": True, "updated_at": datetime.now(timezone.utc)}}
        )
        return result.modified_count > 0

    async def admin_delete_check(self, code: str) -> bool:
        """Админское удаление чека"""
        result = await self.collection.update_one(
            {"_id": code},
            {"$set": {"is_active": False, "updated_at": datetime.now(timezone.utc)}}
        )
        return result.modified_count > 0

    async def deactivate_exhausted(self) -> int:
        """Деактивировать все исчерпанные чеки."""
        filter_q = {
            "is_active": True,
            "$expr": {"$gte": ["$activations_used", "$activation_limit"]}
        }
        result = await self.collection.update_many(
            filter_q,
            {"$set": {"is_active": False, "updated_at": datetime.now(timezone.utc)}}
        )
        return result.modified_count

    async def deactivate_expired(self) -> int:
        """Деактивировать просроченные чеки."""
        now = datetime.now(timezone.utc)
        filter_q = {
            "is_active": True,
            "expires_at": {"$exists": True, "$ne": None, "$lt": now}
        }
        result = await self.collection.update_many(
            filter_q,
            {"$set": {"is_active": False, "updated_at": now}}
        )
        return result.modified_count

    # ==================== Активации ====================

    async def get_activation(
        self,
        check_id: int,
        user_id: int,
        *,
        for_update: bool = False
    ) -> Optional[dict]:
        """Получить активацию пользователя."""
        if self.activation_collection is None:
            # Если коллекция не инициализирована, попытаемся получить ее из базы
            # Но проще вернуть None; инициализация должна происходить вне
            return None
        activation = await self.activation_collection.find_one(
            {"check_id": str(check_id), "user_id": user_id}
        )
        return activation

    async def get_user_activation(self, check_id: int, user_id: int) -> Optional[dict]:
        """Alias for compatibility."""
        return await self.get_activation(check_id, user_id, for_update=False)

    async def create_activation(
        self,
        *,
        check: dict,
        user_id: int,
        payout_amount: float,
        referral_user_id: int | None = None,
        referral_amount: float = 0.0,
    ) -> dict:
        """Создать новую активацию."""
        activation = {
            "check_id": str(check["_id"]),
            "user_id": user_id,
            "status": "pending",
            "payout_amount_ton": payout_amount,
            "referral_user_id": referral_user_id,
            "referral_amount_ton": referral_amount,
            "slot_reserved": True,
            "created_at": datetime.now(timezone.utc),
        }
        result = await self.activation_collection.insert_one(activation)
        activation["_id"] = result.inserted_id
        # Увеличиваем счетчик использованных активаций чека
        await self.collection.update_one(
            {"_id": check["_id"]},
            {"$inc": {"activations_used": 1}, "$set": {"updated_at": datetime.now(timezone.utc)}}
        )
        return activation

    async def mark_processing(self, activation: dict) -> None:
        """Отметить активацию как обрабатываемую."""
        await self.activation_collection.update_one(
            {"_id": activation["_id"]},
            {"$set": {"status": "processing", "updated_at": datetime.now(timezone.utc)}}
        )

    async def mark_success(
        self,
        activation: dict,
        *,
        user_transfer_id: str,
        referral_transfer_id: str | None = None,
        referral_paid: bool = False,
    ) -> None:
        """Отметить активацию как успешную."""
        update_data = {
            "status": "success",
            "user_transfer_id": user_transfer_id,
            "referral_transfer_id": referral_transfer_id,
            "referral_paid": referral_paid,
            "updated_at": datetime.now(timezone.utc),
        }
        await self.activation_collection.update_one(
            {"_id": activation["_id"]},
            {"$set": update_data}
        )

    async def confirm_activation(
        self,
        activation: dict,
        tx_id: str,
        ref_tx_id: Optional[str],
        ref_paid: bool
    ):
        """Alias for compatibility."""
        await self.mark_success(activation, user_transfer_id=tx_id, referral_transfer_id=ref_tx_id, referral_paid=ref_paid)

    async def mark_failed(
        self,
        activation: dict,
        check: dict,
    ) -> None:
        """Отметить активацию как неуспешную и вернуть слот."""
        await self.activation_collection.update_one(
            {"_id": activation["_id"]},
            {"$set": {"status": "failed", "slot_reserved": False, "updated_at": datetime.now(timezone.utc)}}
        )
        # Возвращаем слот только если активация не была уже учтена? В нашей логике мы увеличиваем счетчик при создании активации.
        # Если активация провалилась, мы должны уменьшить счетчик.
        await self.collection.update_one(
            {"_id": check["_id"]},
            {"$inc": {"activations_used": -1}, "$set": {"updated_at": datetime.now(timezone.utc)}}
        )

    async def fail_reservation(self, activation: dict, check: dict):
        """Alias for compatibility."""
        await self.mark_failed(activation, check)

    async def get_check_stats(self, check_id: int) -> dict:
        """Получить статистику по чеку."""
        match = {"check_id": str(check_id)}
        # Успешные активации
        success_count = await self.activation_collection.count_documents(
            {**match, "status": "success"}
        )
        # Сумма выплат
        pipeline = [
            {"$match": {**match, "status": "success"}},
            {"$group": {"_id": None, "total": {"$sum": "$payout_amount_ton"}}}
        ]
        cursor = self.activation_collection.aggregate(pipeline)
        result = await cursor.to_list(length=1)
        payout_sum = result[0]["total"] if result else 0.0
        # Реферальные выплаты
        pipeline_ref = [
            {"$match": {**match, "status": "success", "referral_paid": True}},
            {"$group": {"_id": None, "total": {"$sum": "$referral_amount_ton"}}}
        ]
        cursor_ref = self.activation_collection.aggregate(pipeline_ref)
        result_ref = await cursor_ref.to_list(length=1)
        referral_sum = result_ref[0]["total"] if result_ref else 0.0

        return {
            "success_count": int(success_count),
            "payout_sum_ton": float(payout_sum),
            "referral_sum_ton": float(referral_sum),
        }

    async def get_activation_stats(self, check_id: int) -> dict:
        """Alias for compatibility."""
        return await self.get_check_stats(check_id)

    async def get_recent_activations(self, check_id: int, limit: int = 10):
        """Получить последние успешные активации чека (с пользователями)."""
        # Примечание: для joins нам понадобится выполнить два запроса или использовать $lookup.
        # Для простоты возвращаем только активации, а пользователей будем получать отдельно в сервисе.
        cursor = self.activation_collection.find(
            {"check_id": str(check_id), "status": "success"}
        ).sort("created_at", -1).limit(limit)
        activations = await cursor.to_list(length=limit)
        # В текущем виде мы возвращаем только активации; сервис должен дополнить пользователями.
        return activations  # В оригинале возвращалось кортеж (activation, user)

    async def get_user_activations(
        self,
        user_id: int,
        *,
        limit: int = 20,
    ) -> list[dict]:
        """Получить историю активаций пользователя."""
        cursor = self.activation_collection.find(
            {"user_id": user_id}
        ).sort("created_at", -1).limit(limit)
        return await cursor.to_list(length=limit)

    async def reserve_slot(
        self,
        check: dict,
        user_id: int,
        referrer_id: int | None
    ) -> Tuple[dict, bool]:
        """Legacy support logic integrated."""
        existing = await self.get_user_activation(str(check["_id"]), user_id)
        if existing:
            return existing, False

        # Предполагаем, что check заблокирован
        if not check.get("is_active", False):
            raise ValueError("check_inactive")

        if check.get("activations_used", 0) >= check.get("activation_limit", 0):
            raise ValueError("check_exhausted")

        payout = check.get("amount_ton", 0.0)
        ref_amt = 0.0
        final_referrer_id = None

        if referrer_id and referrer_id != user_id and referrer_id != check.get("created_by"):
            if check.get("referral_percent", 0) > 0:
                ref_amt = payout * check["referral_percent"] / 100.0
                final_referrer_id = referrer_id

        activation = await self.create_activation(
            check=check,
            user_id=user_id,
            payout_amount=payout,
            referral_user_id=final_referrer_id,
            referral_amount=ref_amt
        )

        # После создания активации счетчик уже увеличен внутри create_activation
        if check.get("activations_used", 0) >= check.get("activation_limit", 0):
            await self.deactivate(check)

        return activation, True