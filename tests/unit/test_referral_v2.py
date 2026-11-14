from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch
from decimal import Decimal
from datetime import datetime, timezone
import pytest
from src.services.referral_economy import commission, distribute, activate, ancestors, bind
from src.bot.handlers.referral import advert_keyboard, referral_inline, format_stats_card
from src.bot.keyboards.inline import get_referral_keyboard
from src.domain.entities.referral import ReferralStats


def test_exact_split_and_small_amounts():
    parts = [commission(500, Decimal(r)) for r in ('0.1', '0.01', '0.001')]
    assert parts == [50, 5, .5]
    assert sum(parts) + 444.5 == 500
    assert commission(.1, Decimal('.001')) == 0


def test_both_advert_and_menu_have_real_copy_buttons():
    link = 'https://t.me/test?start=ref_7'
    advert = advert_keyboard(link)
    assert advert.inline_keyboard[0][0].url == link
    assert advert.inline_keyboard[1][0].copy_text.text == link
    menu = get_referral_keyboard(link, 7)
    assert menu.inline_keyboard[0][0].copy_text.text == link
    assert any(b.switch_inline_query == 'senseireferal' for row in menu.inline_keyboard for b in row)


@pytest.mark.asyncio
async def test_inline_uses_sender_identity_not_query_payload():
    query = NS(from_user=NS(id=7), bot=NS(get_me=AsyncMock(return_value=NS(username='test'))), answer=AsyncMock())
    await referral_inline(query)
    results = query.answer.call_args.args[0]
    assert results[0].reply_markup.inline_keyboard[0][0].url.endswith('ref_7')
    assert query.answer.call_args.kwargs['is_personal'] is True


@pytest.mark.asyncio
async def test_distribution_preserves_principal_and_session():
    db = NS(users=NS(update_one=AsyncMock()), bank=NS(update_one=AsyncMock()), transactions=NS(insert_one=AsyncMock()))
    with patch('src.services.referral_economy.ancestors', AsyncMock(return_value=[{'id': 1}, {'id': 2}, {'id': 3}])):
        await distribute(db, {'id': 7}, 500, 'purchase1', 'session')
    assert [c.args[1]['$inc']['coins'] for c in db.users.update_one.call_args_list] == [50, 5, .5]
    assert db.bank.update_one.call_args.args[1]['$inc']['coins'] == 444.5
    assert all(c.kwargs['session'] == 'session' for c in db.transactions.insert_one.call_args_list)
    assert len({c.args[0]['_id'] for c in db.transactions.insert_one.call_args_list}) == 3


@pytest.mark.asyncio
async def test_legacy_cycle_does_not_pay_purchaser():
    docs = {7: {'id': 7, 'referrer_id': 8}, 8: {'id': 8, 'referrer_id': 7}}
    db = NS(users=NS(find_one=AsyncMock(side_effect=lambda q, **kw: docs[q['id']])))
    assert [p['id'] for p in await ancestors(db, 7, None)] == [8]


@pytest.mark.asyncio
@pytest.mark.parametrize('paid,version,days', [(True, 2, ['a','b','c']), (False, 1, ['a','b','c']), (False, 2, [])])
async def test_activation_never_replays_or_activates_legacy_or_early(paid, version, days):
    db = NS(users=NS(find_one=AsyncMock()), bank=NS(update_one=AsyncMock()))
    await activate(db, dict(id=7, referral_bonus_paid=paid, referral_version=version, referral_activity_days=days), 'e', None)
    db.bank.update_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_insufficient_bank_keeps_activation_pending():
    db = NS(users=NS(find_one=AsyncMock(return_value={'id': 1}), update_one=AsyncMock()),
        bank=NS(update_one=AsyncMock(return_value=NS(matched_count=0))))
    await activate(db, dict(id=7, referrer_id=1, referral_version=2, referral_activity_days=['a','b','c']), 'e', None)
    db.users.update_one.assert_not_awaited()


def test_card_has_three_levels_and_honest_conditions():
    card = format_stats_card(ReferralStats(user_id=7, level_3_count=12), 'Name')
    assert 'III уровень: 12' in card
    assert 'при наличии средств' in card


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['self', 'existing', 'cycle', 'closed', 'valid'])
async def test_binding_constraints(mode):
    user = dict(id=7, created_at=datetime.now(timezone.utc))
    parent = dict(id=8)
    if mode == 'existing':
        from datetime import timedelta
        user['created_at'] -= timedelta(days=1)
    if mode == 'closed':
        user['referral_binding_closed'] = True
    if mode == 'cycle':
        parent['referrer_id'] = 7
    docs = {7: user, 8: parent}
    db = NS(users=NS(find_one=AsyncMock(side_effect=lambda q, **kw: docs.get(q['id'])), update_one=AsyncMock()))
    async def transact(mongo, callback):
        return await callback('tx')
    with patch('src.services.referral_economy.transaction', side_effect=transact):
        result = await bind(NS(database=db), 7, 7 if mode == 'self' else 8)
    assert result['success'] is (mode == 'valid')
    if mode != 'valid':
        db.users.update_one.assert_not_awaited()
    else:
        assert db.users.update_one.call_args_list[0].args[1]['$set']['referrer_id'] == 8
        assert not any('coins' in str(c) for c in db.users.update_one.call_args_list)


@pytest.mark.asyncio
async def test_activation_debits_bank_and_uses_deterministic_receipts():
    db = NS(users=NS(find_one=AsyncMock(return_value={'id': 1}), update_one=AsyncMock()),
        bank=NS(update_one=AsyncMock(return_value=NS(matched_count=1))), transactions=NS(insert_one=AsyncMock()))
    await activate(db, dict(id=7, referrer_id=1, referral_version=2, referral_activity_days=['a','b','c']), 'e', 'tx')
    assert db.bank.update_one.call_args.args[1]['$inc']['coins'] == -150
    assert [c.args[0]['coins_change'] for c in db.transactions.insert_one.call_args_list] == [100, 50]
    assert db.users.update_one.call_args.args[1]['$set']['referral_bonus_paid'] is True


@pytest.mark.parametrize('amount,expected', [(0, '0'), (50, '50'), (.5, '0,5'), (.001, '0,001'), (1234.125, '1 234,125')])
def test_compact_coin_display_preserves_precision(amount, expected):
    from src.bot.handlers.referral import coin_text
    assert coin_text(amount) == expected


def test_pagination_level_highlight_and_bounds():
    from src.bot.handlers.referral import page_keyboard, ReferralPage
    first = page_keyboard(7, 'network', 2, 0, True)
    assert first.inline_keyboard[0][1].text == '● 2 уровень'
    assert len(first.inline_keyboard[1]) == 1
    next_page = ReferralPage.unpack(first.inline_keyboard[1][0].callback_data)
    assert (next_page.page, next_page.level, next_page.user_id) == (1, 2, 7)
    last = page_keyboard(7, 'income', 1, 3, False)
    assert ReferralPage.unpack(last.inline_keyboard[0][0].callback_data).page == 2
    assert max(len(b.callback_data.encode()) for row in first.inline_keyboard for b in row) <= 64


@pytest.mark.asyncio
async def test_network_page_limits_escapes_and_has_navigation():
    from unittest.mock import MagicMock
    from src.bot.handlers.referral import show_network
    cursor = NS(to_list=AsyncMock(return_value=[{'id': n, 'first_name': '<bad>'} for n in range(11)]))
    users = NS(aggregate=MagicMock(return_value=cursor))
    container = NS(referral_service=NS(mongo_client=NS(database=NS(users=users))))
    cb = NS(from_user=NS(id=7), message=NS(edit_text=AsyncMock()), answer=AsyncMock())
    await show_network(cb, container, 3, 2)
    pipeline = users.aggregate.call_args.args[0]
    assert {'$skip': 20} in pipeline
    assert {'$limit': 11} in pipeline
    text = cb.message.edit_text.call_args.args[0]
    assert text.count('&lt;bad&gt;') == 10 and '<bad>' not in text
    assert 'Страница 3' in text and '21.' in text
    cb.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_unchanged_page_is_not_an_error():
    from aiogram.exceptions import TelegramBadRequest
    from aiogram.methods import EditMessageText
    from src.bot.handlers.referral import edit_referral
    cb = NS(message=NS(edit_text=AsyncMock(side_effect=TelegramBadRequest(
        method=EditMessageText(text='same'), message='Bad Request: message is not modified'))), answer=AsyncMock())
    await edit_referral(cb, 'same', None)
    cb.answer.assert_awaited_once()


def test_bonus_progress_distinguishes_legacy_pending_and_paid():
    from src.bot.handlers.referral import bonus_progress
    assert bonus_progress(ReferralStats(user_id=7)) == ''
    pending = bonus_progress(ReferralStats(user_id=7, bonus_eligible=True, activity_days=2))
    assert '●●○' in pending and '2/3' in pending
    waiting = bonus_progress(ReferralStats(user_id=7, bonus_eligible=True, activity_days=3, paid_upgrade=True))
    assert 'нужны средства банка' in waiting
    paid = bonus_progress(ReferralStats(user_id=7, bonus_eligible=True, bonus_paid=True))
    assert 'получен' in paid and '50 Coin' in paid


@pytest.mark.asyncio
async def test_group_command_does_not_expose_personal_statistics():
    from src.bot.handlers.referral import cmd_ref
    message = NS(from_user=NS(id=7), chat=NS(type='supergroup'),
        bot=NS(get_me=AsyncMock(return_value=NS(username='test'))), answer=AsyncMock())
    service = NS(get_stats=AsyncMock())
    await cmd_ref(message, NS(referral_service=service))
    service.get_stats.assert_not_awaited()
    button = message.answer.call_args.kwargs['reply_markup'].inline_keyboard[0][0]
    assert button.url == 'https://t.me/test?start=referrals_menu'


@pytest.mark.asyncio
async def test_referral_indexes_cover_tree_and_income_queries():
    from src.services.referral_service import ReferralService
    db = NS(users=NS(create_index=AsyncMock()), transactions=NS(create_index=AsyncMock()))
    await ReferralService(NS(database=db)).ensure_indexes()
    assert db.users.create_index.call_args.args[0] == [('referrer_id', 1), ('id', 1)]
    assert db.transactions.create_index.call_args.args[0][-1] == ('_id', -1)


@pytest.mark.asyncio
async def test_paid_upgrade_itself_records_activity_day_atomically():
    from src.services.economy_service import EconomyService
    from unittest.mock import MagicMock
    from src.core.exceptions import CooldownError
    user = dict(id=7, coins=1000, has_katana=True, katana_length=1, referral_version=2,
        referral_activity_days=['2020-01-01', '2020-01-02'])
    async def update(query, changes, **kwargs):
        user.update(changes.get('$set', {}))
        for key, value in changes.get('$inc', {}).items():
            user[key] = user.get(key, 0) + value
        return NS(matched_count=1)
    db = NS(users=NS(find_one=AsyncMock(side_effect=lambda q, **kw: user.copy()), update_one=AsyncMock(side_effect=update)),
        bank=NS(update_one=AsyncMock()), transactions=NS(insert_one=AsyncMock()), tickets=MagicMock())
    async def transact(mongo, callback):
        return await callback('tx')
    service = EconomyService(NS(database=db))
    with patch('src.services.referral_economy.transaction', side_effect=transact), \
         patch('src.services.referral_economy.distribute', AsyncMock()), \
         patch('src.services.referral_economy.activate', AsyncMock()) as activation:
        await service.upgrade_katana(7)
        assert user['referral_paid_upgrade'] is True
        assert len(user['referral_activity_days']) == 3
        assert datetime.now(timezone.utc).date().isoformat() in user['referral_activity_days']
        assert activation.call_args.args[1]['referral_paid_upgrade'] is True
        assert db.users.update_one.call_args.kwargs['session'] == 'tx'
        with pytest.raises(CooldownError):
            await service.upgrade_katana(7)
    assert db.transactions.insert_one.await_count == 1
