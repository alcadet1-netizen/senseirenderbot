"""
🎯 Handlers package.
"""

from aiogram import Router

from src.bot.handlers.user_commands import router as user_router
from src.bot.handlers.callbacks import router as callbacks_router
from src.bot.handlers.admin_commands import router as admin_router
from src.bot.handlers.triggers import router as triggers_router
from src.bot.handlers.events import router as events_router
from src.bot.handlers.errors import router as errors_router
from src.bot.handlers.zov import router as zov_router
from src.bot.handlers.quiz import router as quiz_router
from src.bot.handlers.slots import router as slots_router
from src.bot.handlers.duel_commands import router as duel_router
from src.bot.handlers.fire import router as fire_router
from src.bot.handlers.trade import router as trade_router
from src.bot.handlers.digest import router as digest_router
from src.bot.handlers.referral import router as referral_router
from src.bot.handlers.broadcast import router as broadcast_router
from src.bot.handlers.music import router as music_router
from src.bot.handlers.boss_commands import router as boss_router
from src.bot.handlers.boss_admin import router as boss_admin_router
from src.bot.handlers.boss_editor import router as boss_editor_router
from src.bot.handlers.maintenance import router as maintenance_router
from src.bot.handlers.chat_settings import router as chat_settings_router
from src.bot.handlers.draw import router as draw_router


def setup_routers() -> Router:
    """Настройка и объединение всех роутеров."""
    main_router = Router(name="main")
    
    # Порядок важен!
    # user_router должен быть первым, чтобы команды обрабатывались приоритетно
    main_router.include_router(user_router)
    main_router.include_router(music_router)
    main_router.include_router(boss_router)
    main_router.include_router(boss_admin_router)
    main_router.include_router(boss_editor_router)
    main_router.include_router(draw_router)
    
    main_router.include_router(errors_router)
    main_router.include_router(maintenance_router)
    main_router.include_router(admin_router)
    main_router.include_router(chat_settings_router)
    main_router.include_router(broadcast_router)
    main_router.include_router(fire_router)
    main_router.include_router(quiz_router)
    main_router.include_router(slots_router)
    main_router.include_router(duel_router)
    main_router.include_router(trade_router)
    main_router.include_router(digest_router)
    main_router.include_router(zov_router)
    main_router.include_router(referral_router)
    
    # Callbacks and triggers (low priority)
    main_router.include_router(callbacks_router)
    main_router.include_router(triggers_router)
    main_router.include_router(events_router)
    
    return main_router


__all__ = ["setup_routers"]
