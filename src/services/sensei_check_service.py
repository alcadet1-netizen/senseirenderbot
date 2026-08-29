"""
✅ SenseiCheck Service на MongoDB.
"""

import hashlib
import json
import logging
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any, Union
from enum import Enum

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.domain.repositories.sensei_check_repository import SenseiCheckRepository
from src.infra.mongo.client import MongoClient
from src.core.visuals import Visuals

logger = logging.getLogger(__name__)


class ActivationError(str, Enum):
    """Ошибки активации."""
    NOT_FOUND = "not_found"
    INACTIVE = "inactive"
    EXHAUSTED = "exhausted"
    EXPIRED = "expired"
    ALREADY_ACTIVATED = "already_activated"
    NOT_SUBSCRIBED = "not_subscribed"
    WRONG_PASSWORD = "wrong_password"
    PASSWORD_REQUIRED = "password_required"
    CAPTCHA_REQUIRED = "captcha_required"
    USER_NOT_FOUND = "user_not_found"
    PAYOUT_FAILED = "payout_failed"
    AMOUNT_TOO_SMALL = "amount_too_small"


@dataclass
class ActivationResult:
    """Результат активации чека."""
    success: bool
    error: Optional[ActivationError] = None
    amount_ton: float = 0.0
    referral_paid: bool = False
    referral_amount_ton: float = 0.0
    missing_channels: list[str] | None = None
    all_channels: list[str] | None = None


class SenseiCheckService:
    MIN_PAYOUT_AMOUNT = Decimal("0.007")  # Минимальная сумма для выплаты

    def __init__(self, mongo: MongoClient, repo: SenseiCheckRepository, xrocket_service, redis):
        self.mongo = mongo
        self._repo = repo
        self.xrocket_service = xrocket_service
        self.redis = redis

    async def create_check(
        self,
        creator_id: int,
        amount_ton: float | Decimal,
        activation_limit: int,
        referral_percent: int = 0,
        message_text: Optional[str] = None,
        password: Optional[str] = None,
        requires_captcha: bool = False,
        channels: Optional[List[str]] = None,
        photo_file_id: Optional[str] = None,
        video_file_id: Optional[str] = None,
        title: Optional[str] = None,
        expires_at: Optional[datetime] = None
    ) -> str:
        """Создать новый чек и вернуть его код."""

        # Конвертируем в Decimal для точных расчетов
        try:
            amount = Decimal(str(amount_ton))
        except Exception as e:
            logger.error(f"Failed to convert amount_ton to Decimal: {e}")
            raise ValueError("Неверный формат суммы чека")

        # Валидация
        if amount < self.MIN_PAYOUT_AMOUNT:
            raise ValueError(f"Минимальная сумма: {self.MIN_PAYOUT_AMOUNT} GRAM")

        if activation_limit <= 0:
            raise ValueError("Лимит активаций должен быть positifным")

        if not 0 <= referral_percent <= 100:
            raise ValueError("Процент реферала должен быть от 0 до 100")

        # Генерируем уникальный код чека
        code = self._generate_check_code()

        # Сохраняем чек в базе данных через репозиторий
        check = await self._repo.create(
            code=code,
            created_by=creator_id,
            amount_ton=float(amount),
            activation_limit=activation_limit,
            channels=channels or [],
            referral_percent=referral_percent,
            message_text=message_text,
            password=password,
            requires_captcha=requires_captcha,
            photo_file_id=photo_file_id,
            video_file_id=video_file_id,
            title=title,
            expires_at=expires_at
        )

        # Кешируем чек
        await self._cache_set(f"scheck:info:{code}", check, ex=3600)

        return code

    async def activate_check(
        self,
        bot: Bot,
        code: str,
        user_id: int,
        password: Optional[str] = None,
        referrer_id: Optional[int] = None,
        captcha_solved: bool = False
    ) -> ActivationResult:
        """Активировать чек пользователем."""
        # Получаем чек из кэша или БД
        check = await self._get_check(code)
        if not check:
            return ActivationResult(success=False, error=ActivationError.NOT_FOUND)

        # Проверяем, активен ли чек
        if not check.get("is_active", False):
            return ActivationResult(success=False, error=ActivationError.INACTIVE)

        # Проверяем, не исчерпан ли лимит активаций
        if check["activations_used"] >= check["activation_limit"]:
            return ActivationResult(success=False, error=ActivationError.EXHAUSTED)

        # Проверяем пароль, если он установлен
        if check.get("password"):
            if not password or password != check["password"]:
                return ActivationResult(success=False, error=ActivationError.WRONG_PASSWORD)

        # Проверяем каптчу, если требуется
        if check.get("requires_captcha") and not captcha_solved:
            return ActivationResult(success=False, error=ActivationError.CAPTCHA_REQUIRED)

        # Проверяем подписку на каналы
        missing_channels = await self._check_subscriptions(user_id, check.get("channels", []))
        if missing_channels:
            return ActivationResult(
                success=False,
                error=ActivationError.NOT_SUBSCRIBED,
                missing_channels=missing_channels,
                all_channels=check.get("channels", [])
            )

        # Вычисляем суммы выплат
        amount = Decimal(str(check["amount_ton"]))
        payout_amount = amount
        referral_amount = amount * Decimal(str(check["referral_percent"])) / Decimal("100")

        # Создаем активацию (это увеличивает счетчик использованных активаций чека)
        # Для реферального бонуса используем переданный referrer_id (если он не None и не равен user_id)
        referral_user_id = None
        if referrer_id is not None and referrer_id != user_id:
            referral_user_id = referrer_id

        activation = await self._repo.create_activation(
            check=check,
            user_id=user_id,
            payout_amount=float(payout_amount),
            referral_user_id=referral_user_id,
            referral_amount=float(referral_amount)
        )

        # Выполняем выплаты пользователю
        user_transfer_id = self._generate_transfer_id("user", check["_id"], user_id)

        # Check xRocket balance
        xrocket_balance = await self.xrocket_service.get_balance()
        if xrocket_balance < float(payout_amount):
            logger.warning(f"Insufficient xRocket balance for user payout: balance={xrocket_balance}, payout_amount={payout_amount}")
            logger.error(f"{Visuals.cross()} [Check:{code}] Payout FAILED for {user_id} (insufficient xRocket balance)")
            # Отмечаем активацию как неуспешную (это вернет слот, уменьшив счетчик использованных активаций)
            await self._repo.mark_failed(activation, check)
            return ActivationResult(success=False, error=ActivationError.PAYOUT_FAILED)

        logger.info(f"💸 [Check:{code}] Attempting payout {payout_amount} GRAM to {user_id} (TransferID: {user_transfer_id})")

        user_payout_ok = await self.xrocket_service.transfer(
            user_id=user_id,
            currency="GRAM",
            amount=float(payout_amount),
            transfer_id=user_transfer_id
        )

        if not user_payout_ok:
            logger.error(f"{Visuals.cross()} [Check:{code}] Payout FAILED for {user_id}")
            # Отмечаем активацию как неуспешную (это вернет слот, уменьшив счетчик использованных активаций)
            await self._repo.mark_failed(activation, check)
            return ActivationResult(success=False, error=ActivationError.PAYOUT_FAILED)

        logger.info(f"✅ [Check:{code}] Payout SUCCESS for {user_id}")

        # Реферальная выплата
        referral_paid = False
        referral_amount_ton = 0.0
        referral_transfer_id = None

        if check["referral_percent"] > 0 and referral_user_id is not None:
            referral_transfer_id = self._generate_transfer_id("referral", check["_id"], referral_user_id)

            # Check xRocket balance for referral
            xrocket_balance = await self.xrocket_service.get_balance()
            if xrocket_balance < float(referral_amount):
                logger.warning(f"Insufficient xRocket balance for referral payout: balance={xrocket_balance}, referral_amount={referral_amount}")
                logger.error(f"❌ [Check:{code}] Referral bonus FAILED for {referral_user_id} (insufficient xRocket balance)")
            else:
                logger.info(f"🤝 [Check:{code}] Attempting referral bonus {referral_amount} GRAM to {referral_user_id} (TransferID: {referral_transfer_id})")

                referral_payout_ok = await self.xrocket_service.transfer(
                    user_id=referral_user_id,
                    currency="GRAM",
                    amount=float(referral_amount),
                    transfer_id=referral_transfer_id
                )

                if referral_payout_ok:
                    logger.info(f"✅ [Check:{code}] Referral bonus SUCCESS for {referral_user_id}")
                    referral_paid = True
                    referral_amount_ton = float(referral_amount)
                else:
                    logger.error(f"❌ [Check:{code}] Referral bonus FAILED for {referral_user_id}")

        # Отмечаем активацию как успешную
        await self._repo.mark_success(
            activation,
            user_transfer_id=user_transfer_id,
            referral_transfer_id=referral_transfer_id,
            referral_paid=referral_paid
        )

        # Уведомляем создателя чека об активации
        await self._notify_creator(
            bot=bot,
            creator_id=check["created_by"],
            user_id=user_id,
            code=code,
            amount=float(payout_amount)
        )

        return ActivationResult(
            success=True,
            amount_ton=float(payout_amount),
            referral_paid=referral_paid,
            referral_amount_ton=referral_amount_ton
        )

    async def _get_check(self, code: str) -> Optional[Dict[str, Any]]:
        """Получить чек по коду из кэша или БД."""
        cached = await self._cache_get(f"scheck:info:{code}")
        if cached:
            return cached

        check = await self._repo.get_by_code(code)
        if check:
            await self._cache_set(f"scheck:info:{code}", check, ex=3600)
        return check

    async def _check_subscriptions(self, user_id: int, channels: List[str]) -> List[str]:
        """Проверить подписку пользователя на каналы."""
        # В реальной реализации здесь должен быть вызов Bot.get_chat_member
        # Для простоты возвращаем пустой список (подразумеваем, что все каналы пройдены)
        return []

    def _generate_check_code(self) -> str:
        """Сгенерировать уникальный код чека."""
        return f"sc_{secrets.token_hex(8)}"

    def _generate_transfer_id(self, prefix: str, check_id: str, user_id: int) -> str:
        """Сгенерировать ID перевода для xRocket."""
        # xRocket требует ID не длиннее 20 символов
        raw = f"{prefix}_{check_id}_{user_id}_{secrets.token_hex(4)}"
        # Обрезаем до 20 символов если нужно
        return raw[:20] if len(raw) > 20 else raw

    async def _notify_creator(
        self,
        bot: Bot,
        creator_id: int,
        user_id: int,
        code: str,
        amount: float
    ) -> None:
        """Уведомить создателя чека об активации."""
        try:
            user_info = await bot.get_chat(user_id)
            name = user_info.first_name or "Unknown"
            if user_info.username:
                name += f" (@{user_info.username})"
        except Exception:
            name = str(user_id)

        text = (
            f"💰 <b>Активация чека!</b>\n\n"
            f"👤 Пользователь: {name}\n"
            f"💵 Сумма: <code>{amount:.4f}</code> GRAM\n"
            f"🎫 Чек: <code>{code}</code>"
        )

        await bot.send_message(creator_id, text, parse_mode="HTML")

    async def burn_check(self, code: str, user_id: int) -> tuple[bool, str, float]:
        """Сжечь чек (вернуть средств создателю)."""

        check = await self._get_check(code)
        if not check:
            return False, "Чек не найден", 0.0

        if check["created_by"] != user_id:
            return False, "Вы не являетесь создателем этого чека", 0.0

        if not check.get("is_active", False):
            return False, "Чек уже неактивен", 0.0

        # Вычисляем сумму возврата
        amount_ton = Decimal(str(check["amount_ton"]))
        remaining_activations = check["activation_limit"] - check["activations_used"]
        refund_ton = amount_ton * Decimal(str(remaining_activations))

        # Деактивируем чек
        await self._repo.deactivate(check)

        if refund_ton > 0:
            transfer_id = self._generate_transfer_id("burn", check["_id"], user_id)
            success = await self.xrocket_service.transfer(
                user_id=user_id,
                currency="GRAM",
                amount=float(refund_ton),
                transfer_id=transfer_id
            )
            if not success:
                logger.error(f"Failed to refund {refund_ton} GRAM for check {code}")
                return False, "🔌 Произошла ошибка при возврате средств P2P.", float(refund_ton)

        await self._cache_delete(f"scheck:info:{code}")
        return True, "🔥 Чек успешно сожжен!", float(refund_ton)

    async def get_all_checks(self) -> List[Dict[str, Any]]:
        """Получить все чеки (для админского списка)."""
        checks, _ = await self._repo.get_all_checks()
        # Ensure we return plain dictionaries with proper .get method
        result = []
        for check in checks:
            if isinstance(check, dict):
                # Create a new plain dictionary to avoid any issues with property conflicts
                plain_check = {}
                for key, value in check.items():
                    plain_check[key] = value
                result.append(plain_check)
            else:
                # If it's not a dict, try to convert it to one
                if hasattr(check, '__dict__'):
                    plain_check = {}
                    for key, value in vars(check).items():
                        plain_check[key] = value
                    result.append(plain_check)
                else:
                    # Last resort: create a dict with string representation
                    result.append({"_str_": str(check)})
        return result

    async def get_check_info(self, bot: Bot, code: str):
        """
        Возвращает объект с информацией о чеке, необходимой для отображения после создания.
        Объект имеет атрибуты:
          - amount_ton: float
          - link: str (реферальная ссылка для partage)
        """
        check = await self._get_check(code)
        if not check:
            return None
        try:
            me = await bot.get_me()
            bot_username = me.username
        except Exception:
            # Fallback if we cannot get bot info
            bot_username = "unknown"
        link = f"https://t.me/{bot_username}?start=check_{code}_{check['created_by']}"
        # Using SimpleNamespace to allow attribute access
        from types import SimpleNamespace
        info = SimpleNamespace()
        info.amount_ton = float(check["amount_ton"])
        info.link = link
        return info

    async def get_check_public_view(self, bot: Bot, code: str) -> Optional[Dict[str, Any]]:
        """
        Возвращает словарь с публично доступной информацией о чеке для детального просмотра.
        Включает основные поля чека и некоторые дополнительные для отображения.
        """
        check = await self._get_check(code)
        if not check:
            return None
        # Create a copy to avoid modifying the original cached dict
        view = check.copy()
        # Ensure we have the fields expected by the presenter
        # If any are missing, provide defaults
        view.setdefault("views_count", None)
        view.setdefault("dropoff_subs", 0)
        view.setdefault("recent_claims", [])
        # Convert datetime to ISO string for JSON serialization if needed (but presenter expects datetime?)
        # The presenter uses the values directly; we keep them as they are (datetime objects)
        # However, if they are going to be cached again, we need them serializable.
        # We'll leave them as is; the presenter uses them for display, not for caching again.
        return view

    async def get_advanced_stats(self, code: str) -> Dict[str, Any]:
        """
        Возвращает дополнительную статистику по чеку.
        Для простоты возвращаем пустой словарь; можно расширить при необходимости.
        """
        # In a full implementation, we would query the activations collection
        # to compute views, dropoffs, recent claims, etc.
        return {}

    async def admin_delete_check(self, code: str) -> bool:
        """
        Админское удаление чека (деактивация).
        """
        return await self._repo.admin_delete_check(code)

    def _json_serial(self, obj):
        """JSON serializer for objects not serializable by default json code"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Type {type(obj)} not serializable")

    def _json_deserial(self, dct):
        """JSON hook to convert ISO format strings back to datetime"""
        for k, v in dct.items():
            if isinstance(v, str):
                try:
                    dct[k] = datetime.fromisoformat(v)
                except ValueError:
                    pass
        return dct

    async def _cache_set(self, key: str, value: Any, ex: int = 3600):
        """Установить значение в кэш."""
        # Always use custom serializer to handle datetime objects
        await self.redis.set(key, json.dumps(value, default=self._json_serial), ex)

    async def _cache_get(self, key: str) -> Optional[Any]:
        """Получить значение из кэша."""
        cached = await self.redis.get(key)
        if cached is None:
            return None
        try:
            return json.loads(cached, object_hook=self._json_deserial)
        except Exception:
            # If not JSON, return as string (fallback)
            return cached.decode() if isinstance(cached, bytes) else cached

    async def _cache_delete(self, key: str):
        """Удалить значение из кэша."""
        await self.redis.delete(key)