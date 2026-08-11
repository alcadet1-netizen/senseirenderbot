import logging
import os
from alembic import command, config
from src.core.config import settings
from src.infra.database import engine

logger = logging.getLogger(__name__)

async def run_migrations() -> None:
    """Run database migrations."""
    logger.info(f"🔄 Running database migrations on {settings.database_url}...")
    
    # Construct path to alembic.ini
    base_dir = settings.BASE_DIR
    # settings.BASE_DIR points to project root (where .env is)
    alembic_cfg_path = os.path.join(base_dir, "alembic.ini")
    
    if not os.path.exists(alembic_cfg_path):
        logger.warning(f"⚠️ alembic.ini not found at {alembic_cfg_path}, trying default lookup")
        alembic_cfg_path = "alembic.ini"

    alembic_cfg = config.Config(alembic_cfg_path)
    alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)
    
    async with engine.begin() as conn:
        await conn.run_sync(run_alembic_upgrade, alembic_cfg)

def run_alembic_upgrade(connection, cfg):
    cfg.attributes["connection"] = connection
    command.upgrade(cfg, "head")
