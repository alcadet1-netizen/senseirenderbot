"""merge_heads

Revision ID: d65b860576a3
Revises: zz_add_video_to_check, zz_create_quiz_questions
Create Date: 2026-02-08 10:26:46.938064

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd65b860576a3'
down_revision: Union[str, None] = ('zz_add_video_to_check', 'zz_create_quiz_questions')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass