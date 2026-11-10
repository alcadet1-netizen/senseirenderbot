"""Compare real baseline/current refresh methods against simulated async Mongo I/O.

No production database, network, token or generated financial writes.
Run: BOT_TOKEN=123456:TEST python -m scripts.benchmark_read_refresh
"""
import ast
import asyncio
import json
import subprocess
import time
from types import MethodType, SimpleNamespace as NS

from src.services.economy_service import EconomyService
from src.services.stats_service import StatsService
from src.services.stats_service import settings, logger

BASE = '94d848a7da3eb5f686eeb5d74b3a6c892fcc703b'


class Collection:
    def __init__(self): self.calls = 0
    async def read(self, value):
        self.calls += 1
        await asyncio.sleep(.002)  # simulated I/O, NOT a measured Mongo RTT
        return value
    def aggregate(self, pipeline):
        group = pipeline[0]['$group']
        if group['_id'] == '$tx_type':
            rows = [{'_id':'daily','count':2,'total_amount':100}]
        else:
            rows = [dict(total=450, count=3, coins=450, messages=29)]
            if group.get('total',{}).get('$sum') == '$messages_count': rows[0]['total']=29
        return NS(to_list=lambda **kwargs:self.read(rows))
    async def count_documents(self, query): return await self.read(3)
    async def find_one(self, query): return await self.read({'coins':1000})


def baseline(path, cls, method):
    source = subprocess.check_output(['git','show',f'{BASE}:{path}'], text=True)
    tree = ast.parse(source)
    owner = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls)
    node = next(n for n in owner.body if isinstance(n, ast.AsyncFunctionDef) and n.name == method)
    namespace = dict(time=time, datetime=__import__('datetime').datetime,
                     timezone=__import__('datetime').timezone, settings=settings, logger=logger)
    exec(compile(ast.Module(body=[node],type_ignores=[]),path,'exec'),namespace)
    return namespace[method]


async def measure(cls, method, old=False):
    db = NS(**{key:Collection() for key in ('users','bank','tickets','transactions')})
    svc = cls(NS(database=db))
    if old:
        path = 'src/services/'+('economy_service.py' if cls is EconomyService else 'stats_service.py')
        setattr(svc, method, MethodType(baseline(path,cls.__name__,method),svc))
    started=time.perf_counter()
    await asyncio.gather(*(getattr(svc,method)() for _ in range(32)))
    return dict(database_operations=sum(x.calls for x in vars(db).values()),
                simulated_ms=round((time.perf_counter()-started)*1000,2))


async def main():
    result = {'note':'32 concurrent cold-cache requests; 2ms simulated I/O. Not production latency.'}
    for cls,method in ((EconomyService,'_get_total_coins_in_circulation'),(StatsService,'get_admin_stats')):
        result[cls.__name__] = dict(baseline=await measure(cls,method,True),optimized=await measure(cls,method))
    print(json.dumps(result,indent=2))

if __name__ == '__main__': asyncio.run(main())
