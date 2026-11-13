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
    assert await service.get_katana_position(7) == {'rank':7,'total':128}
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
