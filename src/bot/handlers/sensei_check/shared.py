
import re
from aiogram.types import Message, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext

def _parse_channels_input(text: str) -> list[str]:
    raw = (text or "").strip()
    if not raw:
        return []
    if raw.lower() in ("нет", "no", "0", "none", "-"):
        return []

    # Split by spaces, commas, newlines
    parts = re.split(r"[\s,;]+", raw)
    out: list[str] = []

    for p in parts:
        s = p.strip()
        if not s:
            continue

        # Handle t.me links
        # https://t.me/username -> @username
        # t.me/username -> @username
        match = re.search(r"(?:t\.me|telegram\.me)/([\w_]+)", s, re.IGNORECASE)
        if match:
            username = match.group(1)
            if username != "joinchat": # Skip joinchat links for now (require ID usually)
                out.append("@" + username)
            continue

        if s.startswith("@"):
            if len(s) > 1:
                out.append(s)
            continue
        if re.fullmatch(r"-?\d+", s):
            out.append(s)
            continue

        # Assume it's a username if it looks like one
        if re.fullmatch(r"[a-zA-Z][\w_]{4,}", s):
             out.append("@" + s)

    return list(dict.fromkeys(out))


async def _ui_render(
    *,
    state: FSMContext,
    anchor: Message,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    data = await state.get_data()
    ui_mid = data.get("ui_mid")
    if ui_mid:
        try:
            await anchor.bot.edit_message_text(
                chat_id=anchor.chat.id,
                message_id=int(ui_mid),
                text=text,
                parse_mode="HTML",
                reply_markup=reply_markup,
                disable_web_page_preview=True,
            )
            return
        except Exception:
            pass

    msg = await anchor.answer(
        text,
        parse_mode="HTML",
        reply_markup=reply_markup,
        disable_web_page_preview=True,
    )
    await state.update_data(ui_mid=msg.message_id)
