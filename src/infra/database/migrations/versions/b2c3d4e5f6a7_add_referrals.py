"""Add referrals table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2025-12-28 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "referrals",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("referrer_id", sa.BigInteger(), nullable=False),
        sa.Column("referred_id", sa.BigInteger(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("coins_earned", sa.Float(), nullable=False, server_default="0"),
        sa.Column("xp_earned", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["referrer_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["referred_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("referred_id", name="uq_referred_id"),
    )
    op.create_index("ix_referrals_referrer_id", "referrals", ["referrer_id"])


def downgrade() -> None:
    op.drop_table("referrals")
