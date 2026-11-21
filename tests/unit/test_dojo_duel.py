import asyncio
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock

import pytest

from src.bot.handlers.duel_commands import accept_dojo_challenge
from src.services.dojo_duel import publish
from src.services.hedgehog_service import GameError


@pytest.mark.asyncio
@pytest.mark.parametrize('bet', [-1, True, '300', 299])
async def test_untrusted_bet_is_rejected(bet):
    with pytest.raises(GameError):
        await publish(None, 1, 'Player', bet)


@pytest.mark.asyncio
@pytest.mark.parametrize('won', [False, True])
async def test_only_winner_of_atomic_accept_creates_duel(won):
    token = 'a' * 24
    duel = NS(id=9)
    engine = NS(_is_in_active_duel=Mock(return_value=False),
                create_duel=AsyncMock(return_value=duel), process_decision=AsyncMock())
    offers = NS(find_one=AsyncMock(return_value={'bet': 300, 'chat': -10}),
                update_one=AsyncMock(return_value=NS(matched_count=int(won))))
    db = NS(dojo_duel_offers=offers, users=NS(find_one=AsyncMock(return_value={'coins': 500})))
    query = NS(data=f'vs:1:{token}', from_user=NS(id=2, is_bot=False), answer=AsyncMock(),
               message=NS(chat=NS(id=-10), message_id=10))
    await accept_dojo_challenge(query, NS(duel_service=engine, mongo_client=NS(database=db)), 'bot')
    if won:
        engine.create_duel.assert_awaited_once_with(1, 2, 300, -10, 'bot', request_id=f'dojo:{token}')
        engine.process_decision.assert_awaited_once_with(9, 2, 'a')
    else:
        engine.create_duel.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('ready', [True, False])
async def test_dojo_round_never_autofills_on_timeout(ready):
    from src.services.duel_service import DuelService
    actions = {1: {'attack': 'hit_l', 'dodge': 'dodge_r'},
               2: {'attack': 'hit_r' if ready else None, 'dodge': 'dodge_l'}}
    duel = NS(dojo_only=True, round_deadline_mono=0, finished=False, settlement_started=False,
              round_num=1, lock=asyncio.Lock(), actions=actions, challenger_id=1, opponent_id=2)
    engine = NS(duels={7: duel}, _closing=False, _all_ready=lambda d: DuelService._all_ready(None, d),
                _resolve_round=AsyncMock(), _finish_duel=AsyncMock())
    await DuelService._wait_for_round(engine, 7, 1)
    if ready:
        engine._resolve_round.assert_awaited_once_with(duel)
    else:
        engine._resolve_round.assert_not_awaited()
        assert engine._finish_duel.await_args.args[:2] == (duel, None)
        assert actions[2]['attack'] is None


@pytest.mark.asyncio
@pytest.mark.parametrize('katana,coins,allowed', [(True, 300, True), (True, 299, False), (False, 900, False)])
async def test_private_offer_checks_equipment_and_stake_before_accept(katana, coins, allowed):
    offers = NS(find_one=AsyncMock(return_value=dict(chat=2, rival=2, bet=300)),
                update_one=AsyncMock(return_value=NS(matched_count=1)))
    db = NS(dojo_duel_offers=offers, users=NS(find_one=AsyncMock(return_value={'coins': coins, 'has_katana': katana})))
    engine = NS(_is_in_active_duel=Mock(return_value=False), create_duel=AsyncMock(return_value=NS(id=9)),
                process_decision=AsyncMock())
    query = NS(data='vs:1:' + 'a'*24, from_user=NS(id=2, is_bot=False), answer=AsyncMock(),
               message=NS(chat=NS(id=2), message_id=10))
    await accept_dojo_challenge(query, NS(duel_service=engine, mongo_client=NS(database=db)), 'bot')
    assert bool(engine.create_duel.await_count) == allowed
    if not allowed:
        offers.update_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_simultaneous_rematch_clicks_share_one_invitation(monkeypatch):
    from src.services import dojo_duel as vs
    duel = NS(id=8, challenger_id=1, opponent_id=2, bet=300, finished=True, lock=asyncio.Lock())
    monkeypatch.setattr(vs, 'active_battle', lambda *_: duel)
    invitations = {}
    async def find(query):
        return invitations.get((query['_id'], query['rival'], query['rematch']))
    async def send(container, uid, *args):
        await asyncio.sleep(0)
        invitations[(uid, 3-uid, 8)] = {'token': 'abc'}
        return {'phase': 'waiting'}
    monkeypatch.setattr(vs, '_publish', send)
    join = AsyncMock(return_value={'phase': 'connecting'})
    monkeypatch.setattr(vs, 'open_invitation', join)
    container = NS(mongo_client=NS(database=NS(dojo_duel_offers=NS(find_one=find))))
    first, second = await asyncio.gather(*(vs.publish(container, i, 'Player', 300, rematch=8) for i in (1, 2)))
    assert [first['phase'], second['phase']] == ['waiting', 'connecting']
    join.assert_awaited_once_with(container, 2, 1, 'abc', accept=True)


@pytest.mark.asyncio
@pytest.mark.parametrize('bet,valid', [(0, False), (299, False), (300, True), (777, True)])
async def test_inline_duel_draft_and_minimum(bet, valid):
    from src.bot.handlers.duel_commands import inline_duel, sent_inline_duel
    offers = NS(update_one=AsyncMock())
    db = NS(users=NS(find_one=AsyncMock(return_value={'coins': 900})), dojo_duel_offers=offers)
    container = NS(mongo_client=NS(database=db), duel_service=NS(_is_in_active_duel=lambda uid: False))
    query = NS(query=f'dojo_vs {bet}', from_user=NS(id=5, full_name='Ученик'), chat_type='private', answer=AsyncMock())
    await inline_duel(query, container, NS(me=AsyncMock(return_value=NS(username='dojo_bot'))))
    results = query.answer.await_args.args[0]
    assert bool(results) == valid
    if valid:
        draft = offers.update_one.await_args.args[1]['$set']
        assert draft['status'] == 'draft' and draft['inline_private'] and draft['bet'] == bet
        await sent_inline_duel(NS(from_user=query.from_user, result_id=results[0].id, inline_message_id='chat-post'), container)
        key, update = offers.update_one.await_args.args
        assert key['token'] == draft['token'] and key['status'] == 'draft'
        assert update['$set']['status'] == 'open' and update['$set']['inline_arena'] == 'chat-post'
    else:
        offers.update_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_secret_pair_is_atomic_round_scoped_and_locked():
    import time
    from src.services.duel_service import DuelService
    duel = NS(dojo_only=True, challenger_id=1, opponent_id=2, actions={}, lock=asyncio.Lock(),
              accepted=True, finished=False, settlement_started=False, round_num=2,
              round_deadline_mono=time.monotonic()+90)
    async def submit(uid, round_num, attack, dodge):
        return await DuelService.commit_dojo_move(NS(duels={3: duel}), 3, uid, round_num, attack, dodge)
    for args in [(1, 2, 'hit_l', None), (3, 2, 'hit_l', 'dodge_r'), (1, 1, 'hit_l', 'dodge_r')]:
        assert await submit(*args) != 'Принято.' and not duel.actions
    for _ in range(2):
        assert await submit(1, 2, 'hit_l', 'dodge_r') == 'Принято.'
    assert await submit(1, 2, 'hit_r', 'dodge_r') != 'Принято.'
    assert duel.actions == {1: {'attack': 'hit_l', 'dodge': 'dodge_r'}}
