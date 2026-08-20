"""
🎨 Presentation layer for Banzai Game.
"""

import html
import time
from typing import Optional, Dict

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message

from src.core.visuals import Visuals

class BanzaiPresenter:
    """
    Handles all visual representation and message sending for Banzai.
    """

    @staticmethod
    def get_game_keyboard(chat_id: int, active: bool = True, is_private: bool = False) -> InlineKeyboardMarkup:
        # In group chats, only show refresh and rules buttons (no settings)
        if not is_private:
            kb = [
                [
                    InlineKeyboardButton(text="🔄 Обновить", callback_data=f"banzai:refresh:{chat_id}"),
                    InlineKeyboardButton(text="📜 Правила", callback_data=f"banzai:rules:{chat_id}"),
                ]
            ]
            return InlineKeyboardMarkup(inline_keyboard=kb)

        # In private chats, show full keyboard based on game state
        if active:
            kb = [
                [
                    InlineKeyboardButton(text="🔄 Обновить", callback_data=f"banzai:refresh:{chat_id}"),
                ],
                [
                    InlineKeyboardButton(text="➕ 1 мин", callback_data=f"banzai:time:add:1:{chat_id}"),
                    InlineKeyboardButton(text="➖ 1 мин", callback_data=f"banzai:time:sub:1:{chat_id}"),
                ],
                [
                    InlineKeyboardButton(text="🛑 Стоп", callback_data=f"banzai:stop:{chat_id}"),
                    InlineKeyboardButton(text="📜 Правила", callback_data=f"banzai:rules:{chat_id}"),
                ],
                [
                    InlineKeyboardButton(text="💎 +0.1 TON", callback_data=f"banzai:reward:add:0.1:{chat_id}"),
                    InlineKeyboardButton(text="💎 -0.1 TON", callback_data=f"banzai:reward:sub:0.1:{chat_id}"),
                ],
            ]
        else:
            kb = [[InlineKeyboardButton(text="📜 Правила", callback_data=f"banzai:rules:{chat_id}")]]
        return InlineKeyboardMarkup(inline_keyboard=kb)

    @staticmethod
    async def get_user_display(bot: Bot, chat_id: int, user_id: int) -> str:
        """Fetch user display name safely."""
        display = f"User {user_id}"
        try:
            member = await bot.get_chat_member(chat_id, user_id)
            user = member.user
            if user.username:
                display = f"@{user.username}"
            else:
                display = user.first_name or user.full_name or display
        except Exception:
            pass
        return display

    @staticmethod
    def render_game_interface(
        remaining_seconds: int,
        duration_minutes: int,
        leader_name: str,
        is_finished: bool,
        winner_name: Optional[str] = None,
        reward_ton: float = 0.0,
        resets_count: int = 0,
        participants_count: int = 0,
        contenders: list = None,
        reset_makers_count: int = 0,
        silence_seconds: int | None = None
    ) -> str:
        """Render the main game message text."""

        total_seconds = max(1, int(duration_minutes) * 60)
        remaining_seconds_int = int(remaining_seconds)

        width = 30

        safe_leader = html.escape(str(leader_name or "-"))
        safe_winner = html.escape(str(winner_name or ""))

        # Custom Bar
        segments = 15
        ratio = max(0, min(1, remaining_seconds_int / total_seconds))
        filled = int(ratio * segments)

        # Animating hourglass based on ratio
        hourglass = Visuals.wait_raw()
        if ratio < 0.2: hourglass = "⌛"

        bar_str = "🟦" * filled + "⬜" * (segments - filled)

        rem_min = remaining_seconds_int // 60
        rem_sec = remaining_seconds_int % 60
        time_display = f"{rem_min:02d}:{rem_sec:02d}"

        kb_active = True

        if is_finished:
            header = "🏁 БАНЗАЙ ЗАВЕРШЕН"
            status_line = f"{Visuals.trophy_raw()} WIN: {safe_winner}" if winner_name else "😞 Никто не выиграл"
            time_line = "⏱ ВРЕМЯ ВЫШЛО"
            kb_active = False
        else:
            header = "⚔️ BANZAI ULTIMATE"
            status_line = f"👑 KING: {safe_leader}"
            time_line = f"{hourglass} {time_display}"

        contenders_lines: list[str] = []

        if not is_finished and contenders:
            contenders_lines.append(Visuals.frame_separator_left(width))
            contenders_lines.append(Visuals.frame_line_left(f"{Visuals.fire_raw()} Последние ходы:", width))
            for safe_name, ts in contenders[:3]:
                dt = max(0, int(time.time()) - int(ts))
                # Truncate name if too long
                if len(safe_name) > 15: safe_name = safe_name[:14] + "…"
                contenders_lines.append(Visuals.frame_line_left(f"◦ {safe_name} · {dt}s ago", width))

        lines = [
            Visuals.frame_top_left(width),
            Visuals.frame_line_left(header, width, "center"),
            Visuals.frame_separator_left(width),
            Visuals.frame_line_left(f"🤫 Цель: {int(duration_minutes)} мин тишины", width),
            Visuals.frame_line_left("🕶 РЕЖИМ: ULTIMATE", width),
            Visuals.frame_line_left(f"{time_line}", width, "center"),
            Visuals.frame_line_left(bar_str, width, "center"),
            Visuals.frame_separator_left(width),
            Visuals.frame_line_left(status_line, width),
        ]

        if not is_finished:
             lines.append(Visuals.frame_line_left(f"📊 Сбросов: {resets_count} | Люди: {reset_makers_count or participants_count}", width))
             if silence_seconds is not None:
                 lines.append(Visuals.frame_line_left(f"🕯 Тишина идёт: {int(silence_seconds)}s", width))

        lines.extend(contenders_lines)

        lines.extend([
            Visuals.frame_separator_left(width),
            Visuals.frame_line_left("💰 Награда:", width),
            Visuals.frame_line_left("🎫 1 Билет + 500 Coins", width),
        ])

        if reward_ton > 0:
            lines.append(Visuals.frame_line_left(f"💎 {reward_ton} TON", width))

        lines.append(Visuals.frame_bottom_left(width))

        return "<pre>\n" + "\n".join(lines) + "\n</pre>"

    @staticmethod
    def render_one_minute_callout(leader_mention: str) -> str:
        w = 34
        lines = [
            Visuals.frame_top_left(w),
            Visuals.frame_line_left("🚨 ULTIMATE ФИНАЛ", w, "center"),
            Visuals.frame_separator_left(w),
            Visuals.frame_line_left(f"{Visuals.wait_raw()} Осталась 1 минута!", w, "center"),
            Visuals.frame_separator_left(w),
            Visuals.frame_line_left("Текущий Лидер:", w),
            Visuals.frame_line_left(f"👑 {leader_mention}", w),
            Visuals.frame_separator_left(w),
            Visuals.frame_line_left(f"{Visuals.fire_raw()} ПЕРЕБЕЙ ЕГО!", w, "center"),
            Visuals.frame_line_left("Напиши любое сообщение", w, "center"),
            Visuals.frame_bottom_left(w),
        ]
        return "<pre>\n" + "\n".join(lines) + "\n</pre>"