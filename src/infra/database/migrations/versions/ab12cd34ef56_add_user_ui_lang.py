"""add_user_ui_lang

Revision ID: ab12cd34ef56
Revises: f6a7b8c9d0e1
Create Date: 2026-01-20 12:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "ab12cd34ef56"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("ui_lang", sa.String(length=2), nullable=True))
    op.execute("UPDATE users SET ui_lang = 'ru' WHERE ui_lang IS NULL")


def downgrade() -> None:
    op.drop_column("users", "ui_lang")

