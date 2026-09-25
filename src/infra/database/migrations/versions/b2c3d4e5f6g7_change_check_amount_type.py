"""change_check_amount_type

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f7
Create Date: 2026-01-23 12:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b2c3d4e5f6g7'
down_revision: Union[str, None] = 'a1b2c3d4e5f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite does not support ALTER COLUMN well, but Alembic usually handles it with batch_alter_table.
    # However, since this is likely Postgres or standard SQL, we use alter_column.
    # If using SQLite, we might need batch operations. Assuming standard environment.
    with op.batch_alter_table('sensei_checks') as batch_op:
        batch_op.alter_column('amount_ton',
               existing_type=sa.Float(),
               type_=sa.Numeric(20, 9),
               existing_nullable=False)

    with op.batch_alter_table('sensei_check_activations') as batch_op:
        batch_op.alter_column('payout_amount_ton',
               existing_type=sa.Float(),
               type_=sa.Numeric(20, 9),
               existing_nullable=False)
        batch_op.alter_column('referral_amount_ton',
               existing_type=sa.Float(),
               type_=sa.Numeric(20, 9),
               existing_nullable=False)


def downgrade() -> None:
    with op.batch_alter_table('sensei_checks') as batch_op:
        batch_op.alter_column('amount_ton',
               existing_type=sa.Numeric(20, 9),
               type_=sa.Float(),
               existing_nullable=False)

    with op.batch_alter_table('sensei_check_activations') as batch_op:
        batch_op.alter_column('payout_amount_ton',
               existing_type=sa.Numeric(20, 9),
               type_=sa.Float(),
               existing_nullable=False)
        batch_op.alter_column('referral_amount_ton',
               existing_type=sa.Numeric(20, 9),
               type_=sa.Float(),
               existing_nullable=False)
