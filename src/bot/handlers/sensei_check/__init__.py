from aiogram import Router

# Sub-routers
from .admin import router as admin_router
from .user import router as user_router

router = Router(name="sensei_check")
router.include_router(admin_router)
router.include_router(user_router)
