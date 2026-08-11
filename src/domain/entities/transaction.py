"""
💰 Domain entity: Transaction.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class TransactionTypeEnum(str, Enum):
    """Типы транзакций."""
    MESSAGE_REWARD = "message_reward"
    DAILY_BONUS = "daily_bonus"
    ACHIEVEMENT_REWARD = "achievement_reward"
    ADMIN_GRANT = "admin_grant"
    EXCHANGE_IN = "exchange_in"
    EXCHANGE_OUT = "exchange_out"
    LOTTERY_WIN = "lottery_win"
    REFERRAL_BONUS = "referral_bonus"
    BAN_CONFISCATION = "ban_confiscation"
    STREAK_BONUS = "streak_bonus"
    LEVEL_UP_BONUS = "level_up_bonus"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"
    PURCHASE = "purchase"
    SHOP_PURCHASE = "shop_purchase"
    GAME_WIN = "game_win"
    CASINO_BET = "casino_bet"
    QUIZ_WIN = "quiz_win"


@dataclass
class TransactionEntity:
    """Доменная сущность транзакции."""

    id: Optional[int] = None
    user_id: int = 0
    type: TransactionTypeEnum = TransactionTypeEnum.MESSAGE_REWARD
    xp_change: int = 0
    coins_change: float = 0.0
    description: Optional[str] = None
    created_at: Optional[datetime] = None