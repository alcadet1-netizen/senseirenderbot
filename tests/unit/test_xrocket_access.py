import json
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from src.services.xrocket_service import XRocketService, XRocketTransferRejected
from src.services.boss_reward_service import award_boss_gram
from tests.unit.test_boss_mode import payout_fixture


def http(status, data):
    response=MagicMock(status=status)
    response.content.read=AsyncMock(return_value=json.dumps(data).encode())
    response.json=AsyncMock(return_value=data)
    response.__aenter__=AsyncMock(return_value=response)
    response.__aexit__=AsyncMock(return_value=None)
    session=MagicMock()
    session.post.return_value=response
    session.get.return_value=response
    session.__aenter__=AsyncMock(return_value=session)
    session.__aexit__=AsyncMock(return_value=None)
    return session,response


@pytest.mark.asyncio
async def test_forbidden_transfer_has_safe_diagnostic_without_key_or_links(caplog):
    service=XRocketService('secret-current-api-key')
    session,response=http(403,{'success':False,'message':'Forbidden secret-current-api-key https://secret.example/token'})
    with patch('src.services.xrocket_service.aiohttp.ClientSession',return_value=session):
        with pytest.raises(XRocketTransferRejected) as rejected:
            await service.transfer(7,'GRAM',.01,transfer_id='stable',raise_rejection=True)
    assert rejected.value.status==403
    assert 'Forbidden' in rejected.value.detail
    assert 'secret-current-api-key' not in rejected.value.detail+caplog.text
    assert 'https://' not in rejected.value.detail+caplog.text
    response.content.read.assert_awaited_once_with(4096)
    session.post.assert_called_once()


@pytest.mark.asyncio
async def test_existing_transfer_callers_keep_boolean_failure_contract():
    session,_=http(403,{'message':'Forbidden'})
    with patch('src.services.xrocket_service.aiohttp.ClientSession',return_value=session):
        assert await XRocketService('key').transfer(7,'GRAM',.01) is False


@pytest.mark.asyncio
async def test_boss_rejection_recorded_without_second_transfer_or_budget_release():
    container,db,receipts=payout_fixture()
    container.xrocket_service.transfer.side_effect=XRocketTransferRejected(403,'Forbidden')
    assert await award_boss_gram(container,{'start_time':100},7,.01,'event')=='rejected'
    assert container.xrocket_service.transfer.await_count==1
    assert db.boss_state.update_one.await_count==1
    stored=receipts.update_one.call_args.args[1]['$set']
    assert stored=={'status':'rejected','provider_status':403,'provider_detail':'Forbidden'}


@pytest.mark.asyncio
@pytest.mark.parametrize('status,data,ok',[(200,{'success':True,'data':{'secret':'not exposed'}},True),
                                         (403,{'message':'Forbidden'},False)])
async def test_access_check_is_read_only_and_does_not_disclose_app_details(status,data,ok):
    session,_=http(status,data)
    with patch('src.services.xrocket_service.aiohttp.ClientSession',return_value=session):
        result=await XRocketService('key').access_status()
    session.post.assert_not_called()
    assert session.get.call_args.args[0]=='https://pay.xrocket.tg/app/info'
    assert result['ok']==ok and result['status']==status
    assert 'not exposed' not in str(result)


@pytest.mark.asyncio
async def test_access_check_missing_key_makes_no_http_request():
    with patch('src.services.xrocket_service.aiohttp.ClientSession') as session:
        assert (await XRocketService('').access_status())['ok'] is False
    session.assert_not_called()


@pytest.mark.asyncio
async def test_private_diagnostic_does_not_call_api_from_group():
    from src.bot.handlers.boss_admin import cmd_boss_xrocket_status
    message=NS(chat=NS(type='supergroup'),answer=AsyncMock())
    container=NS(xrocket_service=NS(access_status=AsyncMock()))
    await cmd_boss_xrocket_status(message,container)
    container.xrocket_service.access_status.assert_not_awaited()
