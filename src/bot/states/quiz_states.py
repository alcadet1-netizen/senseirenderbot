from aiogram.fsm.state import State, StatesGroup


class AddQuestionStates(StatesGroup):
    """Состояния для добавления вопроса."""
    waiting_question = State()
    waiting_image = State()
    waiting_answer = State()
