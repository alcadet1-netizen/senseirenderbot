"""One compact, escaped boss-card renderer for editor and live battles."""
import html
import time
from datetime import datetime, timezone
from src.core.constants import BOSSES, BOSS_COOLDOWN_MINUTES


def clean(value, limit=32):
    return html.escape(' '.join(str(value or '').split())[:limit])


class BossPresenter:
    @classmethod
    def render_boss_caption(cls, state, last_action=None, boss_phrase=None):
        config = BOSSES.get(state['boss_id'], {})
        name = clean(config.get('name', 'Босс'), 48)
        hits = state.get('hits') or {}
        lines = [f'👹 <b>{name}</b>']
        settlement = state.get('settlement')
        if state.get('is_expired'):
            lines += ['⏰ <b>Время вышло — босс сбежал.</b>']
        elif state.get('is_dead'):
            lines += ['🏆 <b>Босс повержен!</b>' if state.get('settlement_kind') == 'win'
                      else '⛔ <b>Бой остановлен администратором.</b>' if state.get('stopped_by_admin') else '🏁 <b>Бой завершён.</b>']
        else:
            hp = max(0, state.get('hp', 0))
            maximum = max(1, state.get('max_hp', 1))
            percent = min(100, int(hp / maximum * 100))
            filled = min(10, max(0, round(hp / maximum * 10)))
            lines += [f'❤️ <b>{hp:,} / {maximum:,} HP · {percent}%</b>',
                      '▰' * filled + '▱' * (10-filled)]
            now = time.time()
            shield = max(0, state.get('shield', 0))
            if state.get('break_until', 0) > now:
                lines += [f'💥 <b>Щит разрушен</b> · ещё {max(1,int(state["break_until"]-now))} с']
            elif state.get('max_shield', 0):
                lines += [f'🛡 Щит: <b>{shield} / {state["max_shield"]}</b>']
            phase = 'IV · Последний рывок' if percent <= 10 else 'III · Финальная фаза' if percent <= 25 else 'II · Ярость' if percent <= 50 else 'I · Начало боя'
            lines += [f'🔥 <b>{phase}</b>']
            if state.get('weakness_until', 0) > now:
                lines += ['🎯 <b>Уязвимость · урон ×2</b>']
            if state.get('combo_count', 0) > 1:
                lines += [f'⚔️ Серия: {int(state["combo_count"])}']
            if state.get('deadline'):
                end = datetime.fromtimestamp(state['deadline'], timezone.utc).strftime('%d.%m %H:%M:%S UTC')
                lines += [f'⏳ Завершение: <b>{end}</b>']
            phrase = boss_phrase or state.get('intro')
            if phrase:
                lines += [f'<i>{clean(phrase, 72)}</i>']
        if hits:
            lines += ['', f'👥 Участников: <b>{len(hits)}</b> · 🏆 <b>Лидеры урона</b>']
            top = sorted(hits.items(), key=lambda item: (-item[1].get('dmg', 0), item[0]))[:3]
            for medal, (_, user) in zip(('🥇','🥈','🥉'), top):
                lines += [f'{medal} {clean(user.get("name"), 18)} — {int(user.get("dmg",0)):,}']
        if state.get('ended_at') and state.get('start_time'):
            duration = max(0, int(state['ended_at']-state['start_time']))
            lines += [f'⏱ Длительность: {duration//60} мин. {duration%60} с']
        if state.get('settlement_kind') == 'win' and state.get('battle_log'):
            last = state['battle_log'][-1]
            lines += [f'⚔️ Последний удар: {clean(last.get("name"), 24)}']
        if settlement:
            if settlement['kind'] == 'win':
                lines += [f'💰 Выдано из банка: <b>{settlement["total"]:,.2f} Coin</b> · получателей: {settlement["count"]}']
            else:
                lines += [f'💰 Штраф переведён в банк: <b>{settlement["total"]:,.2f} Coin</b> · участников: {settlement["count"]}']
        elif state.get('settlement_kind'):
            lines += ['⏳ Расчёт монет ожидает подтверждения.']
        if not state.get('is_dead') and not state.get('is_expired'):
            reward = config.get('coins_reward', 0)
            lines += ['', f'🎁 Фонд победы: {reward:,} Coin из банка',
                      f'⚔️ Атака · перерыв {BOSS_COOLDOWN_MINUTES} мин. · ⚡ ульта или /ulta',
                      'Катана + уровень 5+. GRAM — случайный бонус, не гарантия.',
                      '⚠️ При побеге: −100 Coin с участника.']
        if last_action:
            # Public argument is plain text, not trusted HTML.
            lines += [clean(last_action, 64)]
        return '\n'.join(lines)

    @classmethod
    def fatality_message(cls):
        return '⛔ <b>Бой остановлен администратором.</b>\nНаграды не выдаются.'
