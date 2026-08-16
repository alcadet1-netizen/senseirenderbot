import time
from typing import Optional, List, Dict, Any
from src.core.visuals import Visuals
from src.core.constants import BOSSES, BOSS_COOLDOWN_MINUTES

class BossPresenter:
    """
    Presenter for Boss Fights.
    Handles rendering of boss cards, status bars, and battle logs.
    """

    @classmethod
    def render_boss_caption(cls, state: Dict[str, Any], last_action: str | None = None, boss_phrase: str | None = None) -> str:
        """Генерация красивого HTML сообщения босса (Framed Style)."""
        boss_config = BOSSES.get(state["boss_id"], {})
        name = boss_config.get("name", "Unknown Boss")
        hp = max(0, state["hp"])
        max_hp = state["max_hp"]

        width = 30
        lines = [
            Visuals.frame_top_left(width),
            Visuals.frame_line_left(f"👹 {name}", width, "center"),
        ]

        # Intro or Phrase
        phrase = boss_phrase or state.get("intro")
        if phrase:
            # Wrap long phrases
            words = phrase.split()
            current_line = ""
            for word in words:
                if len(current_line) + len(word) + 1 > width - 4:
                    lines.append(Visuals.frame_line_left(f"<i>{current_line}</i>", width, "center"))
                    current_line = word
                else:
                    current_line = f"{current_line} {word}" if current_line else word
            if current_line:
                lines.append(Visuals.frame_line_left(f"<i>{current_line}</i>", width, "center"))

        lines.append(Visuals.frame_separator_left(width))

        # --- HP ---
        percent = int((hp / max_hp) * 100) if max_hp > 0 else 0
        hp_bar = Visuals.progress_bar(hp, max_hp, length=12, style="red_block")
        lines.append(Visuals.frame_line_left(f"🩸 HP: {hp}/{max_hp}", width))
        lines.append(Visuals.frame_line_left(f"{hp_bar} {percent}%", width))

        # --- Shield & Status ---
        break_until = state.get("break_until", 0)
        is_break = time.time() < break_until
        shield = state.get("shield", 0)
        max_shield = state.get("max_shield", 0)

        if is_break:
            remaining = int(break_until - time.time())
            lines.append(Visuals.frame_separator_left(width))
            lines.append(Visuals.frame_line_left(f"🛡️ ЩИТ СЛОМАН! (x2 УРОН)", width, "center"))
            lines.append(Visuals.frame_line_left(f"{Visuals.wait_raw()} СТАН: {remaining} сек", width, "center"))
        elif max_shield > 0:
            shield_bar = Visuals.progress_bar(shield, max_shield, length=12, style="blue_block")
            lines.append(Visuals.frame_line_left(f"🛡️ ЩИТ: {shield}/{max_shield}", width))
            lines.append(Visuals.frame_line_left(f"{shield_bar}", width))

        # --- Combo & Phase ---
        combo_count = state.get("combo_count", 0)

        phase = "I"
        status_text = "Норма"
        if percent <= 10:
            phase = "IV"
            status_text = "💀 СМЕРТЬ"
        elif percent <= 25:
            phase = "III"
            status_text = "🩸 КРОВЬ"
        elif percent <= 50:
            phase = "II"
            status_text = "😡 ЯРОСТЬ"

        lines.append(Visuals.frame_separator_left(width))
        lines.append(Visuals.frame_line_left(f"📊 Фаза {phase}: {status_text}", width))

        if combo_count > 1:
            multiplier = 1.0 + (min(combo_count, 50) * 0.02)
            lines.append(Visuals.frame_line_left(f"{Visuals.fire_raw()} COMBO: x{combo_count} (x{multiplier:.2f})", width))

        if state.get("deadline"):
            remaining_time = int(state["deadline"] - time.time())
            if remaining_time > 0:
                lines.append(Visuals.frame_line_left(f"{Visuals.wait_raw()} Таймер: {remaining_time // 60} мин", width))
            else:
                lines.append(Visuals.frame_line_left(f"{Visuals.wait_raw()} Время вышло...", width))

        # --- Leaderboard ---
        hits = list((state.get("hits") or {}).values())
        if hits:
            lines.append(Visuals.frame_separator_left(width))
            lines.append(Visuals.frame_line_left(f"{Visuals.trophy_raw()} MVP Урона:", width))
            top = sorted(hits, key=lambda x: x.get("dmg", 0), reverse=True)[:3]
            medals = ["🥇", "🥈", "🥉"]
            for i, t in enumerate(top):
                p_name = Visuals.escape((t.get("name") or "")[:12])
                dmg_val = int(t.get("dmg", 0) or 0)
                crits = t.get("crits", 0)
                # Shorten: "User: 5000 (3c)"
                info = f"{dmg_val}"
                if crits > 0: info += f" ({crits}c)"
                lines.append(Visuals.frame_line_left(f"{medals[i]} {p_name}: {info}", width))

        # --- Battle Log ---
        battle_log = state.get("battle_log", [])
        if battle_log:
            lines.append(Visuals.frame_separator_left(width))
            lines.append(Visuals.frame_line_left("📝 Лог битвы:", width))
            # Show last 5
            for entry in battle_log[-5:]:
                user_name = Visuals.escape((entry.get('name') or '')[:10])

                icon = "💥"
                dmg_text = f"-{entry['dmg']}"

                if entry.get("evaded"):
                    icon = "💨"
                    dmg_text = "MISS"
                elif entry.get("is_break"):
                    icon = "💔"
                elif entry.get("is_ult"):
                    icon = "⚡"
                    dmg_text = f"-{entry['dmg']} (ULT)"
                elif entry.get("crit"):
                    icon = "🩸"
                    dmg_text = f"-{entry['dmg']}!"

                if entry.get("is_ton_reward"):
                    amount = entry.get("ton_amount", 0)
                    lines.append(Visuals.frame_line_left(f"💎 {user_name}: +{amount} TON", width))
                else:
                    lines.append(Visuals.frame_line_left(f"{icon} {user_name} {dmg_text}", width))

        lines.append(Visuals.frame_bottom_left(width))

        caption = "<pre>\n" + "\n".join(lines) + "\n</pre>"

        if last_action:
            caption += f"\n{last_action}"

        return caption

    @classmethod
    def fatality_message(cls) -> str:
        """Сообщение о фаталити (killboss)."""
        width = 30
        lines = [
            Visuals.frame_top_left(width),
            Visuals.frame_line_left("💀 FATALITY", width, "center"),
            Visuals.frame_separator_left(width),
            Visuals.frame_line_left("Сенсей убил босса", width),
            Visuals.frame_line_left("с одного удара.", width),
            Visuals.frame_separator_left(width),
            Visuals.frame_line_left(f"{Visuals.cross()} Битва остановлена", width),
            Visuals.frame_bottom_left(width)
        ]
        return "<pre>\n" + "\n".join(lines) + "\n</pre>"