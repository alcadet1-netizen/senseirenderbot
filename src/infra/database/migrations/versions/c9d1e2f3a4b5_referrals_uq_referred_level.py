"""referrals uq (referred_id, level)

Revision ID: c9d1e2f3a4b5
Revises: a1b2c3d4e5f8
Create Date: 2026-01-28 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c9d1e2f3a4b5'
down_revision: Union[str, None] = 'a1b2c3d4e5f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE referrals DROP CONSTRAINT IF EXISTS referrals_referred_id_key")
    op.execute("ALTER TABLE referrals DROP CONSTRAINT IF EXISTS uq_referrals_referred_id")
    op.execute("DROP INDEX IF EXISTS ix_referrals_referred_id")
    op.execute("ALTER TABLE referrals ADD CONSTRAINT uq_referrals_referred_level UNIQUE (referred_id, level)")


def downgrade() -> None:
    op.execute("ALTER TABLE referrals DROP CONSTRAINT IF EXISTS uq_referrals_referred_level")
    op.execute("ALTER TABLE referrals ADD CONSTRAINT uq_referrals_referred_id UNIQUE (referred_id)")
