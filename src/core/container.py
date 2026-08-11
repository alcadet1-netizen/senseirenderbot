"""
🏗️ DI-контейнер приложения.
"""

from dataclasses import dataclass, field
from typing import Optional

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.core.config import Settings


@dataclass
class Container:
    """DI-контейнер для сервисов."""

    settings: Settings
    session_factory: async_sessionmaker[AsyncSession]
    redis: Redis

    _user_service: Optional["UserService"] = field(default=None, init=False, repr=False)
    _economy_service: Optional["EconomyService"] = field(default=None, init=False, repr=False)
    _daily_service: Optional["DailyService"] = field(default=None, init=False, repr=False)
    _exchange_service: Optional["ExchangeService"] = field(default=None, init=False, repr=False)
    _achievement_service: Optional["AchievementService"] = field(default=None, init=False, repr=False)
    _level_service: Optional["LevelService"] = field(default=None, init=False, repr=False)
    _lottery_service: Optional["LotteryService"] = field(default=None, init=False, repr=False)
    _moderation_service: Optional["ModerationService"] = field(default=None, init=False, repr=False)
    _broadcast_service: Optional["BroadcastService"] = field(default=None, init=False, repr=False)
    _crypto_service: Optional["CryptoService"] = field(default=None, init=False, repr=False)
    _stats_service: Optional["StatsService"] = field(default=None, init=False, repr=False)
    _quiz_service: Optional["QuizService"] = field(default=None, init=False, repr=False)
    _trade_service: Optional["TradeService"] = field(default=None, init=False, repr=False)
    _slots_service: Optional["SlotsService"] = field(default=None, init=False, repr=False)
    _duel_service: Optional["DuelService"] = field(default=None, init=False, repr=False)
    _digest_service: Optional["DigestService"] = field(default=None, init=False, repr=False)
    _referral_service: Optional["ReferralService"] = field(default=None, init=False, repr=False)
    _message_cleanup_service: Optional["MessageCleanupService"] = field(default=None, init=False, repr=False)
    _chat_activity_service: Optional["ChatActivityService"] = field(default=None, init=False, repr=False)
    _boss_service: Optional["BossService"] = field(default=None, init=False, repr=False)
    _xrocket_service: Optional["XRocketService"] = field(default=None, init=False, repr=False)

    @property
    def boss_service(self):
        if self._boss_service is None:
            from src.services.boss_service import BossService
            self._boss_service = BossService(self.redis)
        return self._boss_service

    @property
    def xrocket_service(self):
        if self._xrocket_service is None:
            from src.services.xrocket_service import XRocketService
            self._xrocket_service = XRocketService(self.settings.xrocket_pay_token)
        return self._xrocket_service

    @property
    def user_service(self):
        if self._user_service is None:
            from src.services.user_service import UserService
            self._user_service = UserService(self.session_factory, self.redis)
        return self._user_service

    @property
    def economy_service(self):
        if self._economy_service is None:
            from src.services.economy_service import EconomyService
            self._economy_service = EconomyService(self.session_factory, self.redis)
        return self._economy_service

    @property
    def daily_service(self):
        if self._daily_service is None:
            from src.services.daily_service import DailyService
            self._daily_service = DailyService(self.session_factory, self.redis)
        return self._daily_service

    @property
    def exchange_service(self):
        if self._exchange_service is None:
            from src.services.exchange_service import ExchangeService
            self._exchange_service = ExchangeService(self.session_factory)
        return self._exchange_service

    @property
    def achievement_service(self):
        if self._achievement_service is None:
            from src.services.achievement_service import AchievementService
            self._achievement_service = AchievementService(self.session_factory)
        return self._achievement_service

    @property
    def level_service(self):
        if self._level_service is None:
            from src.services.level_service import LevelService
            self._level_service = LevelService()
        return self._level_service

    @property
    def lottery_service(self):
        if self._lottery_service is None:
            from src.services.lottery_service import LotteryService
            self._lottery_service = LotteryService(self.session_factory)
        return self._lottery_service

    @property
    def moderation_service(self):
        if self._moderation_service is None:
            from src.services.moderation_service import ModerationService
            self._moderation_service = ModerationService(self.session_factory)
        return self._moderation_service

    @property
    def broadcast_service(self):
        if self._broadcast_service is None:
            from src.services.broadcast_service import BroadcastService
            self._broadcast_service = BroadcastService(self.session_factory)
        return self._broadcast_service

    @property
    def crypto_service(self):
        if self._crypto_service is None:
            from src.services.crypto_service import CryptoService
            self._crypto_service = CryptoService(self.settings, self.redis)
        return self._crypto_service

    @property
    def stats_service(self):
        if self._stats_service is None:
            from src.services.stats_service import StatsService
            self._stats_service = StatsService(self.session_factory, self.redis)
        return self._stats_service

    @property
    def quiz_service(self):
        if self._quiz_service is None:
            from src.services.quiz_service import QuizService
            self._quiz_service = QuizService(self.session_factory, self.redis)
        return self._quiz_service

    @property
    def trade_service(self):
        if self._trade_service is None:
            from src.services.trade_service import TradeService
            self._trade_service = TradeService(self)
        return self._trade_service

    @property
    def slots_service(self):
        if self._slots_service is None:
            from src.services.slots_service import SlotsService
            self._slots_service = SlotsService(self)
        return self._slots_service

    @property
    def duel_service(self):
        if self._duel_service is None:
            from src.services.duel_service import DuelService
            self._duel_service = DuelService(self)
        return self._duel_service

    @property
    def digest_service(self):
        if self._digest_service is None:
            from src.services.digest_service import DigestService
            self._digest_service = DigestService(self.settings)
        return self._digest_service

    @property
    def referral_service(self):
        if self._referral_service is None:
            from src.services.referral_service import ReferralService
            self._referral_service = ReferralService(self.session_factory, self.redis)
        return self._referral_service

    @property
    def message_cleanup_service(self):
        if self._message_cleanup_service is None:
            from src.services.message_cleanup_service import MessageCleanupService
            self._message_cleanup_service = MessageCleanupService(self.redis)
        return self._message_cleanup_service

    @property
    def chat_activity_service(self):
        if self._chat_activity_service is None:
            from src.services.chat_activity_service import ChatActivityService
            self._chat_activity_service = ChatActivityService(self.redis)
        return self._chat_activity_service


# Type hints for lazy imports
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.services.user_service import UserService
    from src.services.economy_service import EconomyService
    from src.services.daily_service import DailyService
    from src.services.exchange_service import ExchangeService
    from src.services.achievement_service import AchievementService
    from src.services.level_service import LevelService
    from src.services.lottery_service import LotteryService
    from src.services.moderation_service import ModerationService
    from src.services.broadcast_service import BroadcastService
    from src.services.crypto_service import CryptoService
    from src.services.stats_service import StatsService
    from src.services.trade_service import TradeService
    from src.services.slots_service import SlotsService
    from src.services.duel_service import DuelService
    from src.services.xrocket_service import XRocketService
    from src.services.digest_service import DigestService
    from src.services.referral_service import ReferralService
    from src.services.message_cleanup_service import MessageCleanupService
    from src.services.chat_activity_service import ChatActivityService
