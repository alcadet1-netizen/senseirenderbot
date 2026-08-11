from aiogram.fsm.state import State, StatesGroup

class GovoriState(StatesGroup):
    waiting_for_chat_selection = State()
    waiting_for_content = State()
