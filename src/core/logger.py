"""
🛠 Настройка логирования (structlog).
"""

import logging
import sys
import structlog
from src.core.config import settings

def setup_logging():
    """Настройка логирования с использованием structlog."""
    
    # Уровень логирования
    log_level = logging.DEBUG if settings.debug else logging.INFO
    
    # Процессоры для structlog
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
    ]
    
    # Рендерер в зависимости от режима
    if settings.debug:
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        processors.append(structlog.processors.JSONRenderer())

    # Конфигурация structlog
    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Настройка стандартного logging для перехвата логов библиотек
    # Мы оставляем стандартный форматер для библиотек, чтобы не ломать их вывод,
    # но можно и перехватывать через structlog.stdlib.ProcessorFormatter, если нужно.
    # Пока оставим базовую настройку, чтобы логи aiogram были видны.
    
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    
    # Можно также настроить перехват корневого логгера, но это может быть избыточно пока.
