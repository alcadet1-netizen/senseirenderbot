"""Fix referrals constraint v2

Revision ID: zz_fix_ref_v2
Revises: zz_init_shop_items
Create Date: 2026-02-04 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "zz_fix_ref_v2"
down_revision: Union[str, None] = ("zz_init_shop_items", "c9d1e2f3a4b5")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    # 1. Inspect existing constraints
    unique_constraints = inspector.get_unique_constraints("referrals")
    
    # Drop any unique constraint that is strictly on ['referred_id']
    for uq in unique_constraints:
        cols = uq.get('column_names', [])
        if cols == ['referred_id']:
            try:
                with conn.begin_nested():
                    op.drop_constraint(uq['name'], 'referrals', type_='unique')
            except Exception:
                pass

    # 2. Inspect indexes
    indexes = inspector.get_indexes("referrals")
    for idx in indexes:
        cols = idx.get('column_names', [])
        if cols == ['referred_id'] and idx.get('unique', False):
            try:
                with conn.begin_nested():
                    op.execute(f"DROP INDEX IF EXISTS {idx['name']}")
            except Exception:
                pass

    # 3. Create target constraint if not exists
    target_exists = False
    for uq in unique_constraints:
        if set(uq.get('column_names', [])) == {'referred_id', 'level'}:
            target_exists = True
            break
            
    if not target_exists:
        try:
            with conn.begin_nested():
                op.create_unique_constraint("uq_referrals_referred_level", "referrals", ["referred_id", "level"])
        except Exception:
            pass


def downgrade() -> None:
    op.drop_constraint("uq_referrals_referred_level", "referrals", type_="unique")
    op.create_unique_constraint("uq_referred_id", "referrals", ["referred_id"])
