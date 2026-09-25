"""add_quiz_reward

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-01-20 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Check if quiz_questions table exists before adding column
    inspector = sa.inspect(op.get_context().connection)
    if 'quiz_questions' in inspector.get_table_names():
        op.add_column('quiz_questions', sa.Column('reward_ton', sa.Float(), server_default='0.0', nullable=False))


def downgrade() -> None:
    inspector = sa.inspect(op.get_context().connection)
    if 'quiz_questions' in inspector.get_table_names():
        op.drop_column('quiz_questions', 'reward_ton')
