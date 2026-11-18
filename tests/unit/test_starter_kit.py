from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest

from src.core.constants import STARTER_XP, STARTER_COINS, STARTER_KATANA_LENGTH
from src.core.visuals import Visuals
from src.services.level_service import LevelService
from src.widgets.katana_models import MODEL_NAMES, katana_name, model_caption, model_index


def test_starter_kit_is_level_one_ten_cm_and_three_thousand_coin():
    assert LevelService().get_level(STARTER_XP) == 1
    assert STARTER_COINS == 3000
    assert STARTER_KATANA_LENGTH == 10
    text = Visuals.welcome_bonus_message('Newcomer')
    assert 'Уровень 1' in text and '10 см' in text and '3 000' in text
    assert '10 000' not in text and '2200' not in text and '20 см' not in text
    assert "<b>СТАРТОВЫЙ НАБОР</b>" in text
    assert len(text) < 200


@pytest.mark.parametrize('index', range(15))
def test_model_names_follow_the_fifteen_length_levels(index):
    length = index * 20 + 19.99
    assert katana_name(length) == MODEL_NAMES[index]
    assert f'{MODEL_NAMES[index]}' in model_caption(length)
    assert f'Уровень {index + 1}/15' in model_caption(length)
    assert model_index(length) == index


@pytest.mark.asyncio
@pytest.mark.parametrize('created,answers', [(True, 2), (False, 1)])
async def test_welcome_only_announces_kit_for_new_profile(created, answers):
    from src.bot.handlers.events import _send_welcome_message
    user = NS(id=7, is_bot=False, username='newuser', first_name='New', last_name=None)
    container = NS(user_service=NS(get_or_create=AsyncMock(return_value={'created': created, 'user': {'coins': 3000}})))
    event = NS(chat=NS(type='supergroup', username='airchatton'), answer=AsyncMock())
    await _send_welcome_message(user, container, event)
    assert event.answer.await_count == answers
    if created:
        assert 'СТАРТОВЫЙ НАБОР' in event.answer.call_args.args[0]


@pytest.mark.asyncio
async def test_referred_newcomer_is_created_with_the_starter_kit():
    """A /start ref_<id> creates the profile before binding the referrer."""
    from src.services.user_service import UserService

    class Users:
        def __init__(self):
            self.docs = {}

        async def find_one(self, query):
            return self.docs.get(query.get('id'))

        async def insert_one(self, document):
            self.docs[document['id']] = document

    users = Users()
    service = UserService.__new__(UserService)
    service.users = users
    service.emission = NS(
        reserve_starter=AsyncMock(return_value=STARTER_COINS))
    result = await service.get_or_create(
        7, username='newcomer', first_name='New')
    assert result['created'] is True
    user = users.docs[7]
    assert user['coins'] == STARTER_COINS == 3_000
    assert LevelService().get_level(user['xp']) == 1
    assert user['has_katana'] is True
    assert user['katana_length'] == STARTER_KATANA_LENGTH == 10
    # Binding a referrer only sets referrer_id; it never touches the kit.
    assert user['referrer_id'] is None


def test_starter_notice_escapes_name_and_reports_actual_emission():
    text = Visuals.welcome_bonus_message('<Новичок & друг>', 0)
    assert '&lt;Новичок &amp; друг&gt;' in text
    assert '0 Coin' in text and 'не начислены' in text and '3 000' not in text
    assert 'Уровень 1' in text and '10 см' in text
    partial = Visuals.welcome_bonus_message('Name', 12.5)
    assert '+12,5 Coin' in partial and '3 000' not in partial


@pytest.mark.asyncio
@pytest.mark.parametrize('args', [None, 'ref_9', 'pet_abc', 'hedgehog_abc', 'referrals_menu'])
async def test_new_start_announces_starter_before_deep_link(args):
    from unittest.mock import patch
    from src.bot.handlers.user_commands import cmd_start
    message = NS(chat=NS(type='private'), from_user=NS(id=7, username='newuser',
        first_name='New', last_name=None, full_name='New'), answer=AsyncMock())
    container = NS(user_service=NS(get_or_create=AsyncMock(return_value={
        'created': True, 'user': {'coins': 3000}}), users=NS(update_one=AsyncMock())),
        referral_service=NS(process_referral=AsyncMock(return_value=(True, 'Приглашение принято'))),
        settings=NS(dojo_app_url=''))
    with (patch('src.bot.presenters.daily_hedgehog.open_pet', new_callable=AsyncMock),
          patch('src.bot.handlers.user_commands.launch_hedgehog', new_callable=AsyncMock),
          patch('src.bot.handlers.referral.cmd_ref', new_callable=AsyncMock)):
        await cmd_start(message, NS(args=args), container)
    messages = [call.args[0] for call in message.answer.await_args_list]
    notices = [text for text in messages if 'СТАРТОВЫЙ НАБОР' in text]
    assert len(notices) == 1
    assert '+3 000 Coin' in notices[0] and 'Уровень 1' in notices[0] and '10 см' in notices[0]
    assert message.answer.await_args_list[0].kwargs['parse_mode'] == 'HTML'
    container.user_service.get_or_create.assert_awaited_once()


@pytest.mark.asyncio
async def test_existing_start_does_not_announce_or_regrant_kit():
    from src.bot.handlers.user_commands import cmd_start
    message = NS(chat=NS(type='private'), from_user=NS(id=7, username='old',
        first_name='Old', last_name=None, full_name='Old'), answer=AsyncMock())
    container = NS(user_service=NS(get_or_create=AsyncMock(return_value={
        'created': False, 'user': {'coins': 123}})), settings=NS(dojo_app_url=''))
    await cmd_start(message, NS(args=None), container)
    assert all('СТАРТОВЫЙ НАБОР' not in call.args[0] for call in message.answer.await_args_list)


@pytest.mark.asyncio
async def test_zero_starter_coins_notice_on_group_join():
    from src.bot.handlers.events import _send_welcome_message
    user = NS(id=7, is_bot=False, username='newuser', first_name='New', last_name=None)
    event = NS(chat=NS(type='group'), answer=AsyncMock())
    container = NS(user_service=NS(get_or_create=AsyncMock(return_value={
        'created': True, 'user': {'coins': 0}})))
    await _send_welcome_message(user, container, event)
    assert '0 Coin' in event.answer.await_args_list[-1].args[0]
    assert '3 000' not in event.answer.await_args_list[-1].args[0]


@pytest.mark.asyncio
@pytest.mark.parametrize('starter,expected', [(3000, '+3 000 Coin'), (0, '0 Coin'), (None, None)])
async def test_new_message_activity_generates_notice_only_on_profile_creation(starter, expected):
    from aiogram.types import User
    from src.bot.middlewares.user_activity import ActivityProcessor, ActivityConfig, NotificationType
    user = User(id=7, is_bot=False, first_name='New')
    service = NS(process_message_reward=AsyncMock(return_value={
        'success': True, 'starter_coins': starter, 'new_xp': 0, 'new_coins': 0}))
    processor = ActivityProcessor(NS(economy_service=service), ActivityConfig(enable_achievements=False))
    notices = await processor.process_message(user, -100, False)
    starter_notices = [item for item in notices if item.type is NotificationType.STARTER_KIT]
    assert len(starter_notices) == (expected is not None)
    if expected:
        assert expected in starter_notices[0].text
        assert starter_notices[0].priority == 100
    service.process_message_reward.assert_awaited_once()


def test_join_service_message_does_not_precreate_inviter_profile():
    from datetime import datetime, timezone
    from aiogram.types import Chat, Message, User
    from src.bot.middlewares.user_activity import UserActivityMiddleware
    member = User(id=2, is_bot=False, first_name='New')
    inviter = User(id=1, is_bot=False, first_name='Inviter')
    event = Message(message_id=42, date=datetime.now(timezone.utc),
        chat=Chat(id=-100, type='supergroup'), from_user=inviter, new_chat_members=[member])
    middleware = UserActivityMiddleware(NS(throttle_service=NS()))
    assert middleware._is_valid_event(event) is False
