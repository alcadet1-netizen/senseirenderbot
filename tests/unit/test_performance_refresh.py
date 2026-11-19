"""Deterministic query-count checks, not production throughput claims."""
import asyncio
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock

import pytest
from src.services.economy_service import EconomyService
from src.services.stats_service import StatsService


@pytest.mark.asyncio
async def test_circulation_32_concurrent_cache_misses_scan_once():
    async def result(**kwargs):
        await asyncio.sleep(0)
        return [{'total':12345}]
    users=NS(aggregate=Mock(return_value=NS(to_list=AsyncMock(side_effect=result))))
    svc=EconomyService(NS(database=NS(users=users,transactions=NS(),bank=NS(),tickets=NS())))
    assert await asyncio.gather(*(svc._get_total_coins_in_circulation() for _ in range(32)))==[12345]*32
    assert users.aggregate.call_count==1
    svc._total_circulation_cache=(12345,0)
    assert await svc._get_total_coins_in_circulation()==12345
    assert users.aggregate.call_count==2


@pytest.mark.asyncio
async def test_failed_circulation_refresh_unlocks_and_does_not_cache_failure():
    read=AsyncMock(side_effect=[RuntimeError(),[{'total':7}]])
    users=NS(aggregate=Mock(return_value=NS(to_list=read)))
    svc=EconomyService(NS(database=NS(users=users,transactions=NS(),bank=NS(),tickets=NS())))
    with pytest.raises(RuntimeError): await svc._get_total_coins_in_circulation()
    assert await svc._get_total_coins_in_circulation()==7


@pytest.mark.asyncio
async def test_admin_32_concurrent_requests_one_refresh_four_database_operations(monkeypatch):
    async def tx(mongo, callback): return await callback("snapshot-session")
    monkeypatch.setattr("src.services.stats_service.transaction", tx)
    users=NS(aggregate=Mock(return_value=NS(to_list=AsyncMock(return_value=[dict(count=3,holders=2,coins=450,messages=29)]))))
    bank=NS(find_one=AsyncMock(return_value={'coins':1000}))
    tickets=NS(count_documents=AsyncMock(return_value=4))
    transactions=NS(aggregate=Mock(return_value=NS(to_list=AsyncMock(return_value=[dict(_id='daily',count=2,total_amount=100)]))))
    svc=StatsService(NS(database=NS(users=users,bank=bank,tickets=tickets,transactions=transactions)))
    results=await asyncio.gather(*(svc.get_admin_stats() for _ in range(32)))
    assert all(x==results[0] for x in results)
    assert results[0]['snapshot_at'] == svc._cache_timestamp
    assert (await svc.get_bank_summary())['snapshot_at'] == results[0]['snapshot_at']
    assert results[0]['users']=={'total':3,'holders':2} and results[0]['circulation']==450
    assert results[0]['messages']=={'total':29} and results[0]['tickets']=={'active':4}
    assert users.aggregate.call_count==transactions.aggregate.call_count==1
    assert users.aggregate.call_args.kwargs['session'] == 'snapshot-session'
    assert transactions.aggregate.call_args.kwargs['session'] == 'snapshot-session'
    assert bank.find_one.await_args.kwargs['session'] == 'snapshot-session'
    assert tickets.count_documents.await_args.kwargs['session'] == 'snapshot-session'
    # Only numeric balances greater than zero count as holders; zero, missing,
    # negative and malformed balances do not.
    group = users.aggregate.call_args.args[0][0]['$group']
    assert group['holders'] == {'$sum': {'$cond': [
        {'$and': [{'$isNumber': '$coins'}, {'$gt': ['$coins', 0]}]}, 1, 0]}}
    # one canonical + one legacy bank snapshot per refresh (the two schemas
    # are both shown until the legacy document is migrated)
    assert bank.find_one.await_count==2 and tickets.count_documents.await_count==1
    svc._cache_timestamp=0
    await svc.get_admin_stats()
    assert users.aggregate.call_count==2
    assert bank.find_one.await_count==4


@pytest.mark.asyncio
async def test_empty_admin_stats_and_failed_refresh_retry(monkeypatch):
    async def tx(mongo, callback): return await callback("snapshot-session")
    monkeypatch.setattr("src.services.stats_service.transaction", tx)
    users=NS(aggregate=Mock(return_value=NS(to_list=AsyncMock(side_effect=[RuntimeError(),[]]))))
    db=NS(users=users,bank=NS(find_one=AsyncMock(return_value=None)),tickets=NS(count_documents=AsyncMock(return_value=0)),
          transactions=NS(aggregate=Mock(return_value=NS(to_list=AsyncMock(return_value=[])))))
    svc=StatsService(NS(database=db))
    with pytest.raises(RuntimeError): await svc.get_admin_stats()
    assert svc._cache_timestamp is None
    assert (await svc.get_admin_stats())['circulation']==0
    assert svc._cache_timestamp is not None
