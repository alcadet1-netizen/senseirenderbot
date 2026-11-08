"""Run the same scenarios on an actual replica set; CI supplies a disposable one."""
import os
import uuid
import pytest
from motor.motor_asyncio import AsyncIOMotorClient
from tests.campaign_support import Harness, CampaignCases


@pytest.fixture
async def campaign_env(tmp_path):
    uri=os.environ.get('CAMPAIGN_TEST_MONGO_URI')
    if not uri:
        pytest.skip('Set CAMPAIGN_TEST_MONGO_URI for real replica-set integration tests')
    client=AsyncIOMotorClient(uri,tz_aware=True,serverSelectionTimeoutMS=5000)
    name='sensei_campaign_test_'+uuid.uuid4().hex
    db=client[name]
    env=None
    try:
        env=await Harness(db,tmp_path).open()
        yield env
    finally:
        if env: await env.close()
        await client.drop_database(name)
        client.close()


class TestCommentCampaignMongo(CampaignCases):
    pass
