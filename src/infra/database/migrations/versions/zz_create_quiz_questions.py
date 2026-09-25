"""create_quiz_questions_table

Revision ID: zz_create_quiz_questions
Revises: zz_update_sensei_checks
Create Date: 2026-02-08 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'zz_create_quiz_questions'
down_revision: Union[str, None] = 'zz_update_sensei_checks'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create quiz_questions table
    op.create_table(
        'quiz_questions',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('answer', sa.String(length=255), nullable=False),
        sa.Column('image_path', sa.String(length=512), nullable=True),
        sa.Column('reward_ton', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('quiz_questions')
