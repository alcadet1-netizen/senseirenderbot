"""Initial migration

Revision ID: 001_initial
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users table
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(64), nullable=True),
        sa.Column("first_name", sa.String(128), nullable=False, server_default=""),
        sa.Column("last_name", sa.String(128), nullable=True),
        sa.Column("xp", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("coins", sa.Float(), nullable=False, server_default="0"),
        sa.Column("messages_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("daily_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_daily", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_banned", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("ban_reason", sa.Text(), nullable=True),
        sa.Column("is_muted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("has_katana", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("referrer_id", sa.BigInteger(), nullable=True),
        sa.Column("referral_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("can_receive_broadcast", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_xp", "users", ["xp"])
    op.create_index("ix_users_coins", "users", ["coins"])

    # Transactions table
    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("xp_change", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("coins_change", sa.Float(), nullable=False, server_default="0"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_transactions_user_id", "transactions", ["user_id"])

    # Tickets table
    op.create_table(
        "tickets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("is_burned", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("burned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("burn_reason", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_tickets_user_id", "tickets", ["user_id"])

    # Achievements table
    op.create_table(
        "achievements",
        sa.Column("id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("xp_reward", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("coin_reward", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
    )

    # User achievements table
    op.create_table(
        "user_achievements",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("achievement_id", sa.String(64), nullable=False),
        sa.Column("unlocked_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["achievement_id"], ["achievements.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "achievement_id", name="uq_user_achievement"),
    )

    # Daily claims table
    op.create_table(
        "daily_claims",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("claim_date", sa.Date(), nullable=False),
        sa.Column("xp_received", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("coins_received", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("streak_at_claim", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "claim_date", name="uq_user_daily_claim"),
    )

    # Bank table
    op.create_table(
        "bank",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(64), nullable=False, server_default="Sensei Bank"),
        sa.Column("coins", sa.Float(), nullable=False, server_default="1000000000"),
        sa.Column("total_coins_distributed", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_coins_collected", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("daily_claims")
    op.drop_table("user_achievements")
    op.drop_table("achievements")
    op.drop_table("tickets")
    op.drop_table("transactions")
    op.drop_table("bank")
    op.drop_table("users")