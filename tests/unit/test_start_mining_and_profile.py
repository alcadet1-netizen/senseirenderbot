"""Start/profile mining entry points, live katana preview and removed triggers."""
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

import pytest

from src.bot.keyboards.inline import get_profile_keyboard, get_start_keyboard
from src.texts.easter_eggs import EASTER_EGGS
from src.texts.phrases import check_easter_egg


def _buttons(markup):
    return [button for row in markup.inline_keyboard for button in row]


def test_start_keyboard_opens_the_miner_mini_app():
    url = 'https://example.test/miniapp/dojo'
    button, = [b for b in _buttons(get_start_keyboard(7, dojo_url=url))
               if b.text == '⛏ Майнинг']
    assert button.web_app is not None and button.web_app.url == url


def test_start_keyboard_without_public_url_has_no_dead_mining_button():
    assert all(b.text != '⛏ Майнинг' for b in _buttons(get_start_keyboard(7)))


def test_profile_keyboard_uses_the_same_mining_label():
    url = 'https://example.test/miniapp/dojo'
    button, = [b for b in _buttons(get_profile_keyboard(7, dojo_url=url))
               if b.text == '⛏ Майнинг']
    assert button.web_app is not None and button.web_app.url == url


@pytest.mark.parametrize('word', ['привет', 'про', 'один'])
def test_common_words_are_not_easter_egg_triggers(word):
    assert word not in EASTER_EGGS
    assert check_easter_egg(word) is None
    assert check_easter_egg(f'ну {word} и что') is None


def test_other_easter_eggs_still_work():
    assert check_easter_egg('путь самурая') is not None


@pytest.mark.asyncio
async def test_mysensei_sends_the_current_katana_gif_and_live_length():
    from src.bot.handlers.user_commands import show_profile

    profile = {
        'username': 'Ronin',
        'level': 7,
        'level_name': 'Жертва Рагпулла',
        'xp': 5_000,
        'xp_next': 5_500,
        'coins': 1_234.56,
        'tickets': 3,
        'messages': 444,
        'streak': 5,
        'achievements_count': 12,
        'wins': 19,
        'losses': 4,
        'role': 'Ронин',
        'has_katana': True,
        'katana_length': 245.5,
    }
    position = {'rank': 7, 'total': 128, 'length': 250.4}
    user_service = NS(
        get_profile=AsyncMock(return_value=profile),
        get_katana_position=AsyncMock(return_value=position),
    )
    container = NS(
        user_service=user_service,
        settings=NS(dojo_app_url='', widget_animations_enabled=True),
    )
    message = NS(
        chat=NS(type='private'),
        from_user=NS(id=7, username='Ronin', first_name='Ronin',
                     last_name=None, is_bot=False),
        answer=AsyncMock(),
        edit_text=AsyncMock(),
    )
    user = NS(id=7, username='Ronin', full_name='Ronin')

    with patch('src.bot.handlers.user_commands.send_current_katana',
               new_callable=AsyncMock) as send:
        await show_profile(message, container, user)

    message.answer.assert_awaited_once()
    text = message.answer.call_args.args[0]
    assert 'Кровавая луна' in text
    assert '250.4 см · уровень 13/15' in text
    send.assert_awaited_once_with(
        message, 250.4, position=position, owner_name='Ronin', animate=True,
    )


@pytest.mark.asyncio
async def test_mysensei_skips_the_gif_without_a_katana():
    from src.bot.handlers.user_commands import show_profile

    profile = {
        'username': 'Ronin', 'level': 1, 'level_name': 'Башмак Сатоши',
        'xp': 10, 'xp_next': 100, 'coins': 10, 'tickets': 0, 'messages': 1,
        'streak': 0, 'achievements_count': 0, 'wins': 0, 'losses': 0,
        'role': None, 'has_katana': False, 'katana_length': 0,
    }
    get_position = AsyncMock()
    container = NS(
        user_service=NS(
            get_profile=AsyncMock(return_value=profile),
            get_katana_position=get_position,
        ),
        settings=NS(dojo_app_url='', widget_animations_enabled=True),
    )
    message = NS(chat=NS(type='private'), answer=AsyncMock(), edit_text=AsyncMock())
    user = NS(id=7, username='Ronin', full_name='Ronin')

    with patch('src.bot.handlers.user_commands.send_current_katana',
               new_callable=AsyncMock) as send:
        await show_profile(message, container, user)

    send.assert_not_awaited()
    get_position.assert_not_awaited()


@pytest.mark.asyncio
async def test_start_command_wires_the_mining_button_to_the_mini_app():
    from src.bot.handlers.user_commands import cmd_start

    url = 'https://example.test/miniapp/dojo'
    message = NS(
        chat=NS(type='private'),
        from_user=NS(id=7, username='Ronin', first_name='Ronin',
                     last_name=None, is_bot=False, full_name='Ronin'),
        answer=AsyncMock(),
    )
    container = NS(
        user_service=NS(get_or_create=AsyncMock(return_value={'created': False})),
        settings=NS(dojo_app_url=url),
    )
    await cmd_start(message, NS(args=None), container)

    markup = message.answer.await_args_list[-1].kwargs['reply_markup']
    button, = [b for b in _buttons(markup) if b.text == '⛏ Майнинг']
    assert button.web_app.url == url
