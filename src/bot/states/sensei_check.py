"""\
✅ FSM для создания SenseiCheck.
"""

from aiogram.fsm.state import State, StatesGroup


class SenseiCheckCreateStates(StatesGroup):
    waiting_channels = State()
    waiting_amount = State()
    waiting_activations = State()
    waiting_referral = State()
    waiting_text = State()
    waiting_photo = State()
    waiting_password = State()
    confirm = State()


class SenseiCheckActivateStates(StatesGroup):
    waiting_password = State()
    waiting_captcha = State()


class SenseiCheckPresetStates(StatesGroup):
    waiting_name = State()
    waiting_channels = State()

