"""Explicit, private admin-only real API probes, with no economy operations."""
import asyncio
import zlib

from aiogram import Router
from aiogram.filters import Command

from src.bot.native_widgets import send_native_widget
from src.bot.widget_diagnostics import WIDGET_TRANSPORT_ERRORS, describe_failure
from src.widgets.hedgehog import to_hedgehog_html
from src.widgets.limits import RENDER_SLOTS

router = Router(name='widget_check')
MINIMAL_WIDGET = ('<!doctype html><html><body><p>Проверка нативного виджета: OK</p>'
                  '<script>TelegramWidget.ready();</script></body></html>')


@router.message(Command('senseiwidgetcheck'))
async def cmd_widget_check(message, container):
    if (not message.from_user or message.chat.type != 'private'
            or message.from_user.id not in container.settings.admin_ids):
        await message.answer('Проверка доступна только администратору бота в личном чате.', parse_mode=None)
        return
    # No endpoint URL/token printed and no environment switching.
    mode = ('MTProto layer 233 / production'
            if getattr(container.settings, 'native_widget_transport', 'bot_api') == 'mtproto'
            else ('Bot API beta/test' if container.settings.telegram_widget_beta else 'Bot API production'))
    await message.answer(
        f'Проверка нативного виджета · {mode}.\n'
        'Отправлю минимальный виджет, затем макет Ежа без игровых запросов. '
        'Попытки, серия и балансы не меняются.', parse_mode=None,
    )
    for label in ('minimal', 'hedgehog'):
        try:
            if label == 'minimal':
                html = MINIMAL_WIDGET
            else:
                async with RENDER_SLOTS:
                    html = await asyncio.to_thread(
                        to_hedgehog_html, 'A' * 32,
                        container.settings.BASE_DIR / 'src/infra/storage/ega',
                    )
            await send_native_widget(message.bot, container, message.chat.id, html, allow_queries=False)
        except WIDGET_TRANSPORT_ERRORS as exc:
            failure = describe_failure(exc, message.bot)
            await message.answer(
                f'Проверка {label}: отказ API.\n'
                f'Категория: {failure.category} · код: {failure.reference}\n'
                f'Ответ Telegram (без секретов): {failure.description}\n{failure.advice}\n'
                'Beta автоматически не включена. Если minimal прошёл, а hedgehog нет — '
                'проблема в макете/ограничениях, не в отсутствии метода.', parse_mode=None,
            )
            return
        except (OSError, ValueError):
            await message.answer(f'Проверка {label}: локальная ошибка сборки HTML/картинки. Запрос не отправлен.', parse_mode=None)
            return
        await message.answer(
            f'{label}: API принял виджет. HTML {len(html.encode())} байт, '
            f'zlib-9 {len(zlib.compress(html.encode(), 9))} байт.', parse_mode=None,
        )
    await message.answer(
        'Оба виджета приняты сервером. Если вместо них заглушка — проверьте версию '
        'и поддержку виджетов в клиенте Telegram. Приём API не подтверждает отображение '
        'и работу widget_query. Если виджеты видны, вызовите /senseidaily для проверки игры.',
        parse_mode=None,
    )
