"""Экспорт всех моделей."""

from src.infra.database.models.base import Base, TimestampMixin
from src.infra.database.models.user import User
from src.infra.database.models.transaction import Transaction, TransactionType
from src.infra.database.models.ticket import Ticket
from src.infra.database.models.achievement import Achievement, UserAchievement
from src.infra.database.models.daily import DailyClaim
from src.infra.database.models.bank import Bank
from src.infra.database.models.quiz import QuizQuestion
from src.infra.database.models.muted_user import MutedUser
from src.infra.database.models.referral import Referral

__all__ = [
    "Base",
    "TimestampMixin",
    "User",
    "Transaction",
    "TransactionType",
    "Ticket",
    "Achievement",
    "UserAchievement",
    "DailyClaim",
    "Bank",
    "QuizQuestion",
    "MutedUser",
    "Referral",
]