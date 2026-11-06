"""Send the daily game directly as a native chat widget, never as a Mini App."""
import asyncio
import logging

from src.bot.widget_diagnostics import WIDGET_TRANSPORT_ERRORS, describe_failure, widget_chat_advice

from src.bot.native_widgets import send_native_widget
from src.core.exceptions import DailyAlreadyClaimedError
from src.services.hedgehog_service import GameError
from src.widgets.hedgehog import to_hedgehog_html
from src.widgets.limits import RENDER_SLOTS

logger = logging.getLogger(__name__)


async def launch_hedgehog(message, user, container, token=None):
    try:
        await container.user_service.get_or_create(
            user_id=user.id, username=user.username, first_name=user.first_name or '',
            last_name=user.last_name, is_bot=user.is_bot,
        )
        game = (await container.hedgehog_service.owned(token, user.id) if token else
                await container.hedgehog_service.issue(user.id))
        async with RENDER_SLOTS:
            html = await asyncio.to_thread(
                to_hedgehog_html, game['token'],
                container.settings.BASE_DIR / 'src/infra/storage/ega',
            )
        # Direct media in THIS chat, including groups. No WebAppInfo, URL or
        # private-chat deep link. The roll does not start until a widget tap.
        await send_native_widget(message.bot, container, message.chat.id, html)
    except DailyAlreadyClaimedError as exc:
        await message.answer(f'🦔 Сегодня вы уже встречались с ежом. Следующая попытка: {exc.next_claim_time}', parse_mode=None)
    except GameError as exc:
        await message.answer(str(exc), parse_mode=None)
    except WIDGET_TRANSPORT_ERRORS as exc:
        failure = describe_failure(exc, message.bot)
        text = failure.public_text()
        if failure.category in {'widget_policy', 'permissions'} and message.chat.type != 'private':
            text += '\n\n' + await widget_chat_advice(message)
        await message.answer(text, parse_mode=None)
    except (OSError, ValueError):
        logger.exception('Could not build native hedgehog widget')
        await message.answer(
            '🦔 Ёж запутался в колючках при подготовке виджета. Попробуй позже. '
            'Попытка не потрачена.', parse_mode=None,
        )
