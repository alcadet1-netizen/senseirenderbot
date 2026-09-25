"""add_is_bot

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-01-04 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('is_bot', sa.Boolean(), server_default='false', nullable=False))


def downgrade() -> None:
    op.drop_column('users', 'is_bot')
