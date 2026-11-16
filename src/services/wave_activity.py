"""Process-local wave state shared by the game and message reward policy.

No global economy settings are changed. Deadline and target checks end the
boost even when the worker has not yet published the final result.
"""
import time
from typing import Dict, Optional

WAVE_MESSAGE_COINS = 30
active_waves: Dict[int, dict] = {}


def wave_message_reward(chat_id: Optional[int]) -> Optional[int]:
    wave = active_waves.get(chat_id)
    if (wave is not None and wave['current'] < wave['target']
            and time.time() < wave['expires']):
        return WAVE_MESSAGE_COINS
    return None
