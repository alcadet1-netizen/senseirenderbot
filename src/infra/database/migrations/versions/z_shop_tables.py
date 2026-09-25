"""Add shop_items and user_items tables

Revision ID: z_shop_tables
Revises: f444490d17d6
Create Date: 2026-02-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "z_shop_tables"
down_revision: Union[str, None] = "f444490d17d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Shop items catalog table
    op.create_table(
        "shop_items",
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("price", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_index("ix_shop_items_price", "shop_items", ["price"])

    # User items (purchases) - FK added separately
    op.create_table(
        "user_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("item_key", sa.String(64), nullable=False),
        sa.Column("bought_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("extra", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_items_user_id", "user_items", ["user_id"])
    op.create_index("ix_user_items_item_key", "user_items", ["item_key"])
    op.create_index("ix_user_items_user_key", "user_items", ["user_id", "item_key"])
    
    # Add FK constraints after tables exist
    op.create_foreign_key(
        "fk_user_items_user_id",
        "user_items", "users",
        ["user_id"], ["id"],
        ondelete="CASCADE"
    )
    op.create_foreign_key(
        "fk_user_items_item_key",
        "user_items", "shop_items",
        ["item_key"], ["key"],
        ondelete="CASCADE"
    )


def downgrade() -> None:
    op.drop_index("ix_user_items_user_key", table_name="user_items")
    op.drop_index("ix_user_items_item_key", table_name="user_items")
    op.drop_index("ix_user_items_user_id", table_name="user_items")
    op.drop_table("user_items")
    op.drop_index("ix_shop_items_price", table_name="shop_items")
    op.drop_table("shop_items")
