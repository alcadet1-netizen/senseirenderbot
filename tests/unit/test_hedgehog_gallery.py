from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch
import pytest

from src.services.hedgehog_gallery import select_image
from src.services.hedgehog_service import GameError
from tests.unit.test_paid_hedgehog import fixture, payment


def test_shuffle_bag_has_no_repeats_until_exhausted(tmp_path):
    names = ['a.jpg', 'b.png', 'c.jpeg', 'd.jpg']
    for name in names:
        (tmp_path / name).write_bytes(b'image')
    user = dict(id=7, daily_pet={'image_name': 'a.jpg'}, hedgehog_images_seen=['a.jpg'])
    chosen = []
    for _ in range(3):
        image, seen = select_image(user, tmp_path)
        chosen.append(image)
        user.update(daily_pet={'image_name': image}, hedgehog_images_seen=seen)
    assert set(chosen) == set(names) - {'a.jpg'}
    image, seen = select_image(user, tmp_path)
    assert image != chosen[-1]
    assert len(seen) == 2


def test_missing_and_single_image_gallery(tmp_path):
    with pytest.raises(GameError):
        select_image({'id': 7}, tmp_path)
    (tmp_path / 'one.png').write_bytes(b'image')
    assert select_image({'id': 7}, tmp_path) == ('one.png', ['one.png'])


@pytest.mark.asyncio
async def test_paid_repeat_persists_new_image_and_recovery_does_not_reroll():
    db, free, paid, base = await fixture()
    first = db.users.docs[7]['daily_pet']['image_name']
    with patch('src.services.paid_hedgehog_service.time.time', return_value=120):
        order = await paid.quote(7)
        receipt = await paid.receive(7, payment(order))
        second = db.users.docs[7]['daily_pet']['image_name']
        history = list(db.users.docs[7]['hedgehog_images_seen'])
        assert second != first
        assert {first, second} <= set(history)
        with patch('src.services.hedgehog_gallery.select_image', side_effect=AssertionError('reroll')):
            again = await paid.receive(7, payment(order))
        assert again['pet_token'] == receipt['pet_token']
        assert db.users.docs[7]['daily_pet']['image_name'] == second
        assert db.users.docs[7]['hedgehog_images_seen'] == history


def test_picture_uses_saved_filename_and_rejects_missing_or_traversal(tmp_path):
    from src.bot.presenters.daily_hedgehog import picture
    gallery = tmp_path / 'src/infra/storage/ega'
    gallery.mkdir(parents=True)
    (gallery / 'a.jpg').write_bytes(b'image')
    (gallery / 'b.png').write_bytes(b'image')
    container = NS(settings=NS(BASE_DIR=tmp_path))
    assert picture(container, '7', 'b.png').path.name == 'b.png'
    for name in ('removed.jpg', '../b.png'):
        with pytest.raises(GameError):
            picture(container, '7', name)


@pytest.mark.asyncio
async def test_donate_has_help_and_keeps_tariffs_and_xrocket():
    from src.bot.handlers.donate import show_donate_menu, XROCKET_URL
    message = NS(answer=AsyncMock())
    await show_donate_menu(message, None, NS(id=7))
    call = message.answer.call_args
    buttons = [b for row in call.kwargs['reply_markup'].inline_keyboard for b in row]
    assert [b.callback_data for b in buttons if (b.callback_data or '').startswith('coinbuy:')] == ['coinbuy:1','coinbuy:5','coinbuy:10','coinbuy:50']
    assert any(b.url == XROCKET_URL for b in buttons)
    assert any(b.callback_data == 'coinhelp' for b in buttons)
    assert '/senseidaily' in call.args[0]
