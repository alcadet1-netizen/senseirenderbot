from io import BytesIO
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, MagicMock, patch
import base64

from PIL import Image
import pytest

from src.bot.sage_vision import image_source, prepare_image, load_image, LimitedBuffer, MAX_DOWNLOAD, ImageUnavailable
from src.bot.sage_context import handle_sage, build_sage_question
from tests.unit.test_sage_context import message


def photo(**overrides):
    return NS(**(dict(file_id='telegram-file', file_size=100, width=100, height=100) | overrides))


def png():
    output = BytesIO()
    Image.new('RGB', (2400, 100), 'red').save(output, 'PNG')
    return output.getvalue()


def test_photo_reply_and_document_selection():
    msg = message(reply=NS(photo=[photo()]))
    assert image_source(msg).file_id == 'telegram-file'
    msg.photo = [photo(width=200), photo(width=300, file_size=MAX_DOWNLOAD + 1)]
    assert image_source(msg).width == 200
    doc = NS(file_id='doc', file_size=10, mime_type='image/png')
    assert image_source(NS(document=doc)) is doc
    assert image_source(NS(document=NS(mime_type='application/pdf'))) is None


def test_prepare_resizes_strips_metadata_and_encodes_jpeg():
    result = prepare_image(png())
    with Image.open(BytesIO(result)) as image:
        assert image.format == 'JPEG' and image.width == 1600
        assert not image.getexif()


def test_corrupt_file_and_download_size_are_bounded():
    with pytest.raises(ImageUnavailable):
        prepare_image(b'not an image')
    with LimitedBuffer() as buffer:
        with pytest.raises(ImageUnavailable):
            buffer.write(b'x' * (MAX_DOWNLOAD + 1))


@pytest.mark.asyncio
async def test_deleted_file_returns_safe_message_and_no_provider_call():
    msg = message(reply=NS(photo=[photo()]))
    msg.bot.download = AsyncMock(side_effect=RuntimeError('secret-token-file-url'))
    service = NS(ai_factory=NS(vision_model='vision'), ask_sensei_image=AsyncMock())
    await handle_sage(msg, NS(digest_service=service))
    service.ask_sensei_image.assert_not_awaited()
    assert 'недоступно' in msg.answer.call_args.args[0]
    assert 'secret-token' not in msg.answer.call_args.args[0]


@pytest.mark.asyncio
async def test_real_image_bytes_reach_vision_not_text_model():
    msg = message('мудрец сенсей, что думаешь?', NS(photo=[photo()], caption='График продаж'))
    async def download(file_id, destination, timeout):
        destination.write(png())
    msg.bot.download = AsyncMock(side_effect=download)
    service = NS(ai_factory=NS(vision_model='vision'), ask_sensei_image=AsyncMock(return_value='Вижу график'), ask_sensei=AsyncMock())
    await handle_sage(msg, NS(digest_service=service))
    service.ask_sensei.assert_not_awaited()
    args = service.ask_sensei_image.call_args.args
    assert args[1].startswith(b'\xff\xd8')
    assert 'График продаж' in args[0]
    assert 'Тебе передано одно изображение' in args[0]
    assert msg.answer.call_args.args[0] == 'Вижу график'


@pytest.mark.asyncio
async def test_missing_vision_configuration_never_downloads_or_pretends_to_see():
    msg = message(reply=NS(photo=[photo()]))
    msg.bot.download = AsyncMock()
    await handle_sage(msg, NS(digest_service=NS(ai_factory=NS(vision_model=''))))
    msg.bot.download.assert_not_awaited()
    assert 'GROQ_VISION_MODEL' in msg.answer.call_args.args[0]


@pytest.mark.asyncio
async def test_provider_payload_uses_data_not_telegram_token_url():
    from src.core.providers import AIProviderFactory
    factory = AIProviderFactory(NS(groq_api_key='secret', groq_vision_model='configured-vision', sambanova_api_key='', gemini_api_key=''))
    response = NS(status=200, json=AsyncMock(return_value={'choices': [{'message': {'content': 'Описание'}}]}))
    response_cm = MagicMock()
    response_cm.__aenter__ = AsyncMock(return_value=response)
    session = MagicMock()
    session.post.return_value = response_cm
    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=session)
    with patch('src.core.providers.aiohttp.ClientSession', return_value=session_cm):
        assert await factory.generate_vision('system', 'question', b'jpeg') == 'Описание'
    payload = session.post.call_args.kwargs['json']
    assert payload['model'] == 'configured-vision'
    url = payload['messages'][1]['content'][1]['image_url']['url']
    assert url == 'data:image/jpeg;base64,' + base64.b64encode(b'jpeg').decode()
    assert 'secret' not in str(payload)
