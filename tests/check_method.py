
from aiogram.types import ChatMemberUpdated, Chat, User, ChatMemberMember, ChatMemberLeft
from aiogram import Bot

def test_answer_method():
    # Mocking is hard without full objects, but let's check attributes of the class
    print(f"Has answer method: {hasattr(ChatMemberUpdated, 'answer')}")

if __name__ == "__main__":
    test_answer_method()
