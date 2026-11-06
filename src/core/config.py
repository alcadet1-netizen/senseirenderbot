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

    # Legacy Mini App links remain usable, but daily now sends a native widget.
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