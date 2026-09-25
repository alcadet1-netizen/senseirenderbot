"""Update sensei checks columns

Revision ID: zz_update_sensei_checks
Revises: zz_fix_ref_v2
Create Date: 2026-02-04 23:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'zz_update_sensei_checks'
down_revision: Union[str, None] = 'zz_fix_ref_v2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Resize code in sensei_checks
    with op.batch_alter_table('sensei_checks') as batch_op:
        batch_op.alter_column('code',
               existing_type=sa.String(length=32),
               type_=sa.String(length=64),
               existing_nullable=False)

    # 2. Resize transfer IDs in sensei_check_activations
    with op.batch_alter_table('sensei_check_activations') as batch_op:
        batch_op.alter_column('user_transfer_id',
               existing_type=sa.String(length=32),
               type_=sa.String(length=64),
               existing_nullable=True)
        batch_op.alter_column('referral_transfer_id',
               existing_type=sa.String(length=32),
               type_=sa.String(length=64),
               existing_nullable=True)


def downgrade() -> None:
    # Revert changes
    with op.batch_alter_table('sensei_check_activations') as batch_op:
        batch_op.alter_column('referral_transfer_id',
               existing_type=sa.String(length=64),
               type_=sa.String(length=32),
               existing_nullable=True)
        batch_op.alter_column('user_transfer_id',
               existing_type=sa.String(length=64),
               type_=sa.String(length=32),
               existing_nullable=True)

    with op.batch_alter_table('sensei_checks') as batch_op:
        batch_op.alter_column('code',
               existing_type=sa.String(length=64),
               type_=sa.String(length=32),
               existing_nullable=False)
