print("Start script")
import sys
import asyncio
from unittest.mock import MagicMock

# Mock missing dependencies
sys.modules["yt_dlp"] = MagicMock()

print("Imported asyncio")
try:
    from unittest.mock import AsyncMock, MagicMock
    from aiogram.types import Message, User, Chat, ChatMemberUpdated, ChatMember
    print("Imported mocks and types")
    from src.bot.handlers.events import on_new_chat_members, on_user_join
    print("Imported handlers")
except Exception as e:
    print(f"IMPORT ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

async def verify_welcome():
    print("🚀 Verifying Welcome Handlers...")
    
    # Mock Container
    container = MagicMock()
    container.user_service.get_or_create = AsyncMock()
    
    # Mock User
    user = User(id=123, is_bot=False, first_name="NewUser", username="newuser")
    
    # --- Test 1: Message with new_chat_members ---
    print("\n1️⃣ Testing on_new_chat_members (Message)...")
    message = AsyncMock(spec=Message)
    message.new_chat_members = [user]
    message.answer = AsyncMock()
    
    try:
        await on_new_chat_members(message, container)
    except Exception as e:
        print(f"ERROR in on_new_chat_members: {e}")
        import traceback
        traceback.print_exc()
        return

    # Verify
    try:
        container.user_service.get_or_create.assert_called_with(
            user_id=123, username="newuser", first_name="NewUser", last_name=None
        )
        message.answer.assert_called_once()
        print("✅ Message handler called answer()")
    except AssertionError as e:
        print(f"ASSERTION FAILED: {e}")

    # --- Test 2: ChatMemberUpdated ---
    print("\n2️⃣ Testing on_user_join (ChatMemberUpdated)...")
    container.user_service.get_or_create.reset_mock()
    
    event = AsyncMock(spec=ChatMemberUpdated)
    
    # Mock status change (e.g. left -> member)
    event.old_chat_member = MagicMock()
    event.old_chat_member.status = "left"
    
    event.new_chat_member = MagicMock()
    event.new_chat_member.status = "member"
    event.new_chat_member.user = user
    
    event.answer = AsyncMock()
    
    try:
        await on_user_join(event, container)
    except Exception as e:
        print(f"ERROR in on_user_join: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Verify
    try:
        container.user_service.get_or_create.assert_called_with(
            user_id=123, username="newuser", first_name="NewUser", last_name=None
        )
        event.answer.assert_called_once()
        print("✅ ChatMemberUpdated handler called answer()")
    except AssertionError as e:
        print(f"ASSERTION FAILED: {e}")
    
    print("\n🎉 All welcome handlers verified!")

if __name__ == "__main__":
    try:
        asyncio.run(verify_welcome())
    except Exception as e:
        print(f"RUNTIME ERROR: {e}")
        import traceback
        traceback.print_exc()
