from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, MagicMock

import pytest
from src.services.user_service import UserService
from src.bot.presenters.katana_presenter import send_current_katana


@pytest.mark.asyncio
async def test_position_counts_ahead_and_total_without_writes():
    users = NS(find_one=AsyncMock(return_value={'id':7,'has_katana':True,'katana_length':25}),
               aggregate=MagicMock(return_value=NS(to_list=AsyncMock(return_value=[{'ahead':6,'total':128}]))))
    service = UserService.__new__(UserService)
    service.users = users
    assert await service.get_katana_position(7) == {'rank':7,'total':128,'length':25}
    pipeline = users.aggregate.call_args.args[0]
    assert pipeline[0] == {'$match':{'has_katana':True}}
    comparison = pipeline[1]['$group']['ahead']['$sum']['$cond'][0]['$or']
    assert comparison[0]['$gt'][1] == 25
    assert comparison[1]['$and'][1] == {'$lt':['$id',7]}


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', [False,True])
async def test_absent_owner_or_database_error_never_returns_fake_first_place(failure):
    service = UserService.__new__(UserService)
    service.users = NS(find_one=AsyncMock(return_value=None,side_effect=RuntimeError('offline') if failure else None))
    assert await service.get_katana_position(7) is None


@pytest.mark.asyncio
async def test_top_has_deterministic_tie_order():
    class Cursor:
        def sort(self, value):
            assert value == [('katana_length',-1),('id',1)]
            return self
        def skip(self,value): return self
        def limit(self,value): return self
        def __aiter__(self): return self
        async def __anext__(self): raise StopAsyncIteration
    service = UserService.__new__(UserService)
    service.users = NS(find=MagicMock(return_value=Cursor()),count_documents=AsyncMock(return_value=0))
    assert await service.get_top_by_katana() == {'items':[],'total':0}


@pytest.mark.asyncio
@pytest.mark.parametrize('position', [None,{'rank':7,'total':128}])
async def test_live_rank_is_in_showcase_caption(position):
    message = NS(answer_animation=AsyncMock())
    await send_current_katana(message,25,position=position)
    caption = message.answer_animation.call_args.kwargs['caption']
    if position:
        assert '№7 из 128' in caption
    else:
        assert 'недоступно' in caption and '№1' not in caption


@pytest.mark.asyncio
async def test_owner_caption_is_bounded_plain_text_and_can_disable_animation():
    message = NS(answer_photo=AsyncMock(),answer_animation=AsyncMock())
    await send_current_katana(message,25,position={'rank':2,'total':90},
                              owner_name='<b>Игрок</b>\n'+'X'*200,animate=False)
    message.answer_animation.assert_not_awaited()
    message.answer_photo.assert_awaited_once()
    kwargs = message.answer_photo.call_args.kwargs
    assert kwargs['parse_mode'] is None
    assert len(kwargs['caption'].splitlines()[0]) <= 82
    assert '№2 из 90' in kwargs['caption']


@pytest.mark.asyncio
async def test_command_uses_rank_length_instead_of_stale_profile():
    from src.bot.handlers.user_commands import cmd_mykatana
    from unittest.mock import patch
    message = NS(from_user=NS(id=7,username='User',full_name='Player'),answer=AsyncMock())
    service = NS(get_profile=AsyncMock(return_value={'has_katana':True,'katana_length':19.9}),
                 get_katana_position=AsyncMock(return_value={'rank':3,'total':10,'length':20.2}))
    container = NS(user_service=service,settings=NS(widget_animations_enabled=False))
    with patch('src.bot.handlers.user_commands.send_current_katana',new_callable=AsyncMock) as send:
        await cmd_mykatana(message,container)
    send.assert_awaited_once_with(message,20.2,position={'rank':3,'total':10,'length':20.2},
                                 owner_name='Player',animate=False)


@pytest.mark.asyncio
async def test_ranking_failure_still_delivers_card_without_false_rank():
    from src.bot.handlers.user_commands import cmd_mykatana
    from unittest.mock import patch
    message = NS(from_user=NS(id=7,username='User',full_name='Player'),answer=AsyncMock())
    service = NS(get_profile=AsyncMock(return_value={'has_katana':True,'katana_length':19.9}),
                 get_katana_position=AsyncMock(side_effect=TimeoutError))
    with patch('src.bot.handlers.user_commands.send_current_katana',new_callable=AsyncMock) as send:
        await cmd_mykatana(message,NS(user_service=service))
    send.assert_awaited_once_with(message,19.9,position=None,owner_name='Player',animate=True)
