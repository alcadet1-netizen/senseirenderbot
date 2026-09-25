"""Initialize shop items with necklace_fart, potion_immune, rune_power, gloves_craft

Revision ID: zz_init_shop_items
Revises: z_shop_tables
Create Date: 2026-02-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "zz_init_shop_items"
down_revision: Union[str, None] = "z_shop_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # Insert shop items
    op.execute(sa.text("""
        INSERT INTO shop_items (key, name, price, description, meta) VALUES
        ('gloves_craft', '🧤 Перчатки Ремесла', 50000, 'Сокращает кулдаун удара с 30 до 24 минут. ⚡ ЭФФЕКТ: Атакуй боссов чаще!', '{"type": "gloves", "rarity": "uncommon"}'),
        ('potion_immune', '🧪 Зелье Вечного Пиздежа', 200000, 'Делает тебя невосприимчивым к мьюту. 🛡️ ЭФФЕКТ: Никто не сможет заткнуть твой рот!', '{"type": "potion", "rarity": "rare"}'),
        ('rune_power', '⚡ Руна Ультра Силы', 150000, 'Сокращает кулдаун ульты с 120 до 75 минут. 🔥 ЭФФЕКТ: Чаще используй мощные удары!', '{"type": "rune", "rarity": "rare"}'),
        ('necklace_fart', '✨ Ожерелье Фарта', 205000, 'Увеличивает шанс получить награду в боссе до 99%. 💎 ЭФФЕКТ: Легендарная защита от невезения!', '{"type": "accessory", "rarity": "legendary"}'),
        ('hammer_shinobi', '🔨 Молот Шиноби', 80000, 'Разрешает использовать /upkatana каждый час вместо каждых 2 часов. ⏱️ ЭФФЕКТ: Быстро улучшай свою катану!', '{"type": "weapon", "rarity": "rare"}')
        ON CONFLICT (key) DO NOTHING;
    """))


def downgrade() -> None:
    op.execute(sa.text("""
        DELETE FROM shop_items WHERE key IN ('necklace_fart', 'potion_immune', 'rune_power', 'gloves_craft', 'hammer_shinobi');
    """))
