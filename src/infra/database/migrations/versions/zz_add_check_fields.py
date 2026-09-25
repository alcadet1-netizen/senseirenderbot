"""Add title and expires_at to sensei_checks

Revision ID: zz_add_check_fields
Revises: zz_update_sensei_checks
Create Date: 2026-02-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'zz_add_check_fields'
down_revision: Union[str, None] = 'zz_update_sensei_checks'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('sensei_checks', sa.Column('title', sa.String(length=128), nullable=True))
    op.add_column('sensei_checks', sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('sensei_checks', 'expires_at')
    op.drop_column('sensei_checks', 'title')
