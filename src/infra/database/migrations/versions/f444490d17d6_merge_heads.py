"""merge_heads

Revision ID: f444490d17d6
Revises: a1b2c3d4e5f8, b2c3d4e5f6g7
Create Date: 2026-01-25 00:06:02.952676

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f444490d17d6'
down_revision: Union[str, None] = ('a1b2c3d4e5f8', 'b2c3d4e5f6g7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass