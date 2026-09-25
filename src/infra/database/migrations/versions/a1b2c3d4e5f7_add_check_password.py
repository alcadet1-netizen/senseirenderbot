"""add_check_password

Revision ID: a1b2c3d4e5f7
Revises: f6a7b8c9d0e1
Create Date: 2026-01-23 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f7'
down_revision: Union[str, None] = 'c4e5f6a7b8c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('sensei_checks', sa.Column('password', sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column('sensei_checks', 'password')
