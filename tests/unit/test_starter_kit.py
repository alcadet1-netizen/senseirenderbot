from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest

from src.core.constants import STARTER_XP, STARTER_COINS, STARTER_KATANA_LENGTH
from src.core.visuals import Visuals
from src.services.level_service import LevelService
from src.widgets.katana_models import katana_name, model_caption, model_index


def test_starter_kit_is_level_one_ten_cm_and_ten_thousand_coin():
    assert LevelService().get_level(STARTER_XP) == 1
    assert STARTER_COINS == 10000
    assert STARTER_KATANA_LENGTH == 10
    text = Visuals.welcome_bonus_message('Newcomer')
    assert 'Уровень 1' in text and '10 см' in text and '10 000' in text
    assert '2200' not in text and '20 см' not in text


@pytest.mark.parametrize('length,name', [
    (0, 'НОЖ Дно-Копателя'), (5, 'Шард-лезвие'), (7, 'Великий HODL-Меч'),
    (10, 'Нейронный вакидзаси'), (14, 'КАТАНА ДУРОВА'), (19, 'ГОЙСКИЙ КЛИНОК'),
    (23, 'Red Blood Tanto'), (29, 'Хеш-клинок Сатоши'), (38, 'DAO-клинок'),
    (48, 'НАГАМАКИ ЧЕРНЫЙ-ЛЕБЕДЬ'), (60, 'НАГИНАТО-СБРИВАТОР'), (80, 'УБИЙЦА БОГОВ'),
    (300, 'УБИЙЦА БОГОВ'),
])
def test_original_names_used_in_model_caption(length, name):
    assert katana_name(length) == name
    assert name in model_caption(length)
    assert model_index(length) == min(14, int(length // 20))


@pytest.mark.asyncio
@pytest.mark.parametrize('created,answers', [(True, 2), (False, 1)])
async def test_welcome_only_announces_kit_for_new_profile(created, answers):
    from src.bot.handlers.events import _send_welcome_message
    user = NS(id=7, is_bot=False, username='newuser', first_name='New', last_name=None)
    container = NS(user_service=NS(get_or_create=AsyncMock(return_value={'created': created})))
    event = NS(chat=NS(type='supergroup', username='airchatton'), answer=AsyncMock())
    await _send_welcome_message(user, container, event)
    assert event.answer.await_count == answers
    if created:
        assert 'СТАРТОВЫЙ НАБОР' in event.answer.call_args.args[0]
