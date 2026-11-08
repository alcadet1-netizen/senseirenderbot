"""
🔧 Конфигурация приложения через Pydantic Settings v2.
"""

import logging
import os
from functools import lru_cache
from typing import List, Literal
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Главный класс настроек приложения."""

    # PATHS
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # TELEGRAM
    bot_token: str = Field(alias="BOT_TOKEN")
    admin_ids_str: str = Field(default="", alias="ADMIN_IDS")
    main_chat_id: int = Field(default=0, alias="MAIN_CHAT_ID")
    proxy_url: str = Field(default="", alias="PROXY_URL")

    # Native widgets can use production MTProto instead of Bot API sendWidget.
    native_widget_transport: Literal['bot_api', 'mtproto'] = Field(default='bot_api', alias='NATIVE_WIDGET_TRANSPORT')
    telegram_api_id: int = Field(default=0, ge=0, alias='TELEGRAM_API_ID')
    telegram_api_hash: SecretStr = Field(default=SecretStr(''), alias='TELEGRAM_API_HASH', repr=False)

    # MONGODB
    mongo_uri: str = Field(
        default="mongodb://localhost:27017/sensei",
        alias="MONGO_URI",
    )
    mongo_db: str = Field(default="", alias="MONGO_DB")

    # Channel comment campaigns: opt-in, numeric IDs resolved/pinned at startup.
    comment_campaigns_enabled: bool = Field(default=False, alias='COMMENT_CAMPAIGNS_ENABLED')
    target_channel_id: int = Field(default=0, le=0, alias='TARGET_CHANNEL_ID')
    discussion_chat_id: int = Field(default=0, le=0, alias='DISCUSSION_CHAT_ID')
    campaign_duration_hours: float = Field(default=4, gt=0, le=168, alias='CAMPAIGN_DURATION_HOURS')
    base_reward: int = Field(default=100, ge=0, le=1_000_000_000, alias='BASE_REWARD')
    winner_reward: int = Field(default=2000, ge=0, le=1_000_000_000, alias='WINNER_REWARD')
    reward_per_unique_user: bool = Field(default=False, alias='REWARD_PER_UNIQUE_USER')
    winner_reward_mode: Literal['total', 'bonus'] = Field(default='total', alias='WINNER_REWARD_MODE')
    campaign_inbox_path: str = Field(default='var/comment_campaign_inbox.sqlite3', alias='CAMPAIGN_INBOX_PATH')
    campaign_poll_seconds: float = Field(default=5, ge=.1, le=60, alias='CAMPAIGN_POLL_SECONDS')
    campaign_lease_seconds: int = Field(default=180, ge=60, le=3600, alias='CAMPAIGN_LEASE_SECONDS')
    campaign_retry_seconds: int = Field(default=60, ge=1, le=3600, alias='CAMPAIGN_RETRY_SECONDS')
    campaign_settlement_grace_seconds: int = Field(default=30, ge=0, le=600, alias='CAMPAIGN_SETTLEMENT_GRACE_SECONDS')
    campaign_batch_size: int = Field(default=25, ge=1, le=200, alias='CAMPAIGN_BATCH_SIZE')
    campaign_allowed_content_types: str = Field(default='text,photo,video,animation,audio,voice,video_note,document,sticker,poll,contact,location,venue,dice', alias='CAMPAIGN_ALLOWED_CONTENT_TYPES')

    # CRYPTO API
    ton_api_key: str = Field(default="", alias="TON_API_KEY")
    xrocket_pay_token: str = Field(default="", alias="XROCKET_PAY_TOKEN")

    # APP
    debug: bool = Field(default=False, alias="DEBUG")
    maintenance_mode: bool = Field(default=False, alias="MAINTENANCE_MODE")

    # Widget-compatible cards; native HTML still requires a layer-233 transport.
    widgets_enabled: bool = Field(default=True, alias="WIDGETS_ENABLED")

    widget_animations_enabled: bool = Field(default=True, alias="WIDGET_ANIMATIONS_ENABLED")

    # Explicit opt-in: the upstream native widget beta uses Telegram TEST chats.
    telegram_widget_beta: bool = Field(default=False, alias="TELEGRAM_WIDGET_BETA")

    # Private HD hedgehog Mini App; falls back to Render RENDER_EXTERNAL_URL when empty.
    mini_app_url: str = Field(default="", alias="MINI_APP_URL")

    # BANK
    bank_initial_coins: float = Field(default=1_000_000_000.0, alias="BANK_INITIAL_COINS")

    # TRADE
    trade_cost: int = Field(default=20, alias="TRADE_COST")
    trade_win_chance: float = Field(default=0.25, alias="TRADE_WIN_CHANCE")

    # DIGEST / VESTNIK
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    sambanova_api_key: str = Field(default="", alias="SAMBANOVA_API_KEY")
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    max_messages: int = Field(default=1000, alias="MAX_MESSAGES")
    auto_digest_threshold: int = Field(default=1000, alias="AUTO_DIGEST_THRESHOLD")
    digest_cooldown: int = Field(default=600, alias="DIGEST_COOLDOWN")
    allowed_chats_str: str = Field(default="", alias="ALLOWED_CHATS")

    @property
    def allowed_chats(self) -> List[int]:
        """Парсинг списка разрешенных чатов из строки."""
        if not self.allowed_chats_str:
            return []
        try:
            return [int(x.strip()) for x in self.allowed_chats_str.split(",") if x.strip()]
        except ValueError:
            return []


    @property
    def admin_ids(self) -> List[int]:
        """Парсинг списка админов из строки."""
        if not self.admin_ids_str:
            return []
        try:
            return [int(x.strip()) for x in self.admin_ids_str.split(",") if x.strip()]
        except ValueError:
            return []


@lru_cache()
def get_settings() -> Settings:
    settings = Settings()
    logger.info(f"[SETTINGS] Loaded settings: admin_ids_str='{settings.admin_ids_str}', admin_ids={settings.admin_ids}")
    return settings


settings = get_settings()