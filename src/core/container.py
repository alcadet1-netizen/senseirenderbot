"""
🏗🏗 DI-контейнер приложения.
"""

from dataclasses import dataclass, field
from typing import Optional

from src.infra.mongo.client import MongoClient
from src.core.config import Settings


@dataclass
class Container:
    """DI-контейнер для сервисов."""

    settings: Settings
    mongo_client: MongoClient
    start_time: float = field(default_factory=lambda: 0.0)

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
    _throttle_service: Optional["ThrottleService"] = field(default=None, init=False, repr=False)
    _popugai_service: Optional["PopugaiService"] = field(default=None, init=False, repr=False)
    _boss_service: Optional["BossService"] = field(default=None, init=False, repr=False)
    _banzai_service: Optional["BanzaiService"] = field(default=None, init=False, repr=False)
    _xrocket_service: Optional["XRocketService"] = field(default=None, init=False, repr=False)

    @property
    def boss_service(self):
        if self._boss_service is None:
            from src.services.boss_service import BossService
            self._boss_service = BossService(self.mongo_client)
        return self._boss_service

    @property
    def xrocket_service(self):
        if self._xrocket_service is None:
            from src.services.xrocket_service import XRocketService
            self._xrocket_service = XRocketService(self.settings.xrocket_pay_token)
        return self._xrocket_service

    @property
    def banzai_service(self):
        if self._banzai_service is None:
            from src.services.banzai_service import BanzaiService
            self._banzai_service = BanzaiService(
                self.mongo_client,
                self.chat_activity_service,
                self.lottery_service,
                self.economy_service,
                self.xrocket_service,
            )
        return self._banzai_service

    @property
    def user_service(self):
        if self._user_service is None:
            from src.services.user_service import UserService
            self._user_service = UserService(self.mongo_client)
        return self._user_service

    @property
    def economy_service(self):
        if self._economy_service is None:
            from src.services.economy_service import EconomyService
            self._economy_service = EconomyService(self.mongo_client)
        return self._economy_service

    @property
    def daily_service(self):
        if self._daily_service is None:
            from src.services.daily_service import DailyService
            self._daily_service = DailyService(self.mongo_client)
        return self._daily_service

    @property
    def exchange_service(self):
        if self._exchange_service is None:
            from src.services.exchange_service import ExchangeService
            self._exchange_service = ExchangeService(self.mongo_client)
        return self._exchange_service

    @property
    def achievement_service(self):
        if self._achievement_service is None:
            from src.services.achievement_service import AchievementService
            self._achievement_service = AchievementService(self.mongo_client)
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
            self._lottery_service = LotteryService(self.mongo_client)
        return self._lottery_service

    @property
    def moderation_service(self):
        if self._moderation_service is None:
            from src.services.moderation_service import ModerationService
            self._moderation_service = ModerationService(self.mongo_client)
        return self._moderation_service

    @property
    def broadcast_service(self):
        if self._broadcast_service is None:
            from src.services.broadcast_service import BroadcastService
            self._broadcast_service = BroadcastService(self.mongo_client)
        return self._broadcast_service

    @property
    def crypto_service(self):
        if self._crypto_service is None:
            from src.services.crypto_service import CryptoService
            self._crypto_service = CryptoService(self.settings)
        return self._crypto_service

    @property
    def stats_service(self):
        if self._stats_service is None:
            from src.services.stats_service import StatsService
            self._stats_service = StatsService(self.mongo_client)
        return self._stats_service

    @property
    def quiz_service(self):
        if self._quiz_service is None:
            from src.services.quiz_service import QuizService
            self._quiz_service = QuizService(self.mongo_client)
        return self._quiz_service

    @property
    def trade_service(self):
        if self._trade_service is None:
            from src.services.trade_service import TradeService
            self._trade_service = TradeService(self.mongo_client)
        return self._trade_service

    @property
    def slots_service(self):
        if self._slots_service is None:
            from src.services.slots_service import SlotsService
            self._slots_service = SlotsService(self.mongo_client)
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
            self._referral_service = ReferralService(self.mongo_client)
            # Set the user_service to avoid circular dependency
            self._referral_service.user_service = self.user_service
        return self._referral_service

    @property
    def message_cleanup_service(self):
        if self._message_cleanup_service is None:
            from src.services.message_cleanup_service import MessageCleanupService
            self._message_cleanup_service = MessageCleanupService()
        return self._message_cleanup_service

    @property
    def chat_activity_service(self):
        if self._chat_activity_service is None:
            from src.services.chat_activity_service import ChatActivityService
            self._chat_activity_service = ChatActivityService(self.mongo_client)
        return self._chat_activity_service

    @property
    def captcha_service(self):
        if self._captcha_service is None:
            from src.services.captcha_service import CaptchaService
            self._captcha_service = CaptchaService(self.mongo_client)
        return self._captcha_service

    @property
    def chat_settings_service(self):
        if self._chat_settings_service is None:
            from src.services.chat_settings_service import ChatSettingsService
            self._chat_settings_service = ChatSettingsService(self.mongo_client)
        return self._chat_settings_service

    @property
    def throttle_service(self):
        if self._throttle_service is None:
            from src.services.throttle_service import ThrottleService
            self._throttle_service = ThrottleService(self.mongo_client)
        return self._throttle_service

    @property
    def popugai_service(self):
        if self._popugai_service is None:
            from src.services.popugai_service import PopugaiService
            self._popugai_service = PopugaiService(self.mongo_client)
        return self._popugai_service


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
    from src.services.quiz_service import QuizService
    from src.services.trade_service import TradeService
    from src.services.slots_service import SlotsService
    from src.services.duel_service import DuelService
    from src.services.xrocket_service import XRocketService
    from src.services.digest_service import DigestService
    from src.services.referral_service import ReferralService
    from src.services.message_cleanup_service import MessageCleanupService
    from src.services.chat_activity_service import ChatActivityService
    from src.services.chat_settings_service import ChatSettingsService
    from src.services.captcha_service import CaptchaService
    from src.services.throttle_service import ThrottleService
    from src.services.popugai_service import PopugaiService
    from src.services.boss_service import BossService