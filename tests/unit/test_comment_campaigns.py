import pytest
from tests.campaign_support import FakeDB, Harness, CampaignCases


@pytest.fixture
async def campaign_env(tmp_path):
    env=await Harness(FakeDB(),tmp_path).open()
    yield env
    await env.close()


class TestCommentCampaignFake(CampaignCases):
    pass
