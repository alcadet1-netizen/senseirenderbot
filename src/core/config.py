"""
🔧 Конфигурация приложения через Pydantic Settings v2.
"""

import os
from functools import lru_cache
from typing import List
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    return Settings()


settings = get_settings()