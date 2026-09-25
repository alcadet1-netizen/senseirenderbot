"""add_sensei_checks

Revision ID: c4e5f6a7b8c0
Revises: ab12cd34ef56
Create Date: 2026-01-22 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4e5f6a7b8c0"
down_revision: Union[str, None] = "ab12cd34ef56"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sensei_checks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("channels_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("amount_ton", sa.Float(), nullable=False),
        sa.Column("activation_limit", sa.Integer(), nullable=False),
        sa.Column("activations_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("referral_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("message_text", sa.Text(), nullable=True),
        sa.Column("photo_file_id", sa.String(length=256), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("code", name="uq_sensei_checks_code"),
    )
    op.create_index("ix_sensei_checks_code", "sensei_checks", ["code"], unique=True)
    op.create_index("ix_sensei_checks_created_by", "sensei_checks", ["created_by"], unique=False)

    op.create_table(
        "sensei_check_activations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("check_id", sa.Integer(), sa.ForeignKey("sensei_checks.id"), nullable=False),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="processing"),
        sa.Column("payout_amount_ton", sa.Float(), nullable=False),
        sa.Column("slot_reserved", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("referral_amount_ton", sa.Float(), nullable=False, server_default="0"),
        sa.Column("referral_user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("referral_paid", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("user_transfer_id", sa.String(length=32), nullable=True),
        sa.Column("referral_transfer_id", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("check_id", "user_id", name="uq_sensei_check_activation"),
    )
    op.create_index("ix_sensei_check_activations_check_id", "sensei_check_activations", ["check_id"], unique=False)
    op.create_index("ix_sensei_check_activations_user_id", "sensei_check_activations", ["user_id"], unique=False)
    op.create_index("ix_sensei_check_activations_referral_user_id", "sensei_check_activations", ["referral_user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_sensei_check_activations_referral_user_id", table_name="sensei_check_activations")
    op.drop_index("ix_sensei_check_activations_user_id", table_name="sensei_check_activations")
    op.drop_index("ix_sensei_check_activations_check_id", table_name="sensei_check_activations")
    op.drop_table("sensei_check_activations")

    op.drop_index("ix_sensei_checks_created_by", table_name="sensei_checks")
    op.drop_index("ix_sensei_checks_code", table_name="sensei_checks")
    op.drop_table("sensei_checks")
