"""Add video_file_id to sensei_checks

Revision ID: zz_add_video_to_check
Revises: zz_add_check_fields
Create Date: 2026-02-05 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'zz_add_video_to_check'
down_revision: Union[str, None] = 'zz_add_check_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('sensei_checks', sa.Column('video_file_id', sa.String(length=256), nullable=True))


def downgrade() -> None:
    op.drop_column('sensei_checks', 'video_file_id')
