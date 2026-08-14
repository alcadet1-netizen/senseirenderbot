import asyncio
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

# Add src to path
sys.path.append(os.getcwd())

from src.bot.handlers.user_commands import cmd_help
from src.bot.handlers.admin_commands import cmd_admin_help
from src.core.config import settings

async def verify_permissions():
    print("🧪 Verifying Help Permissions...")

    admin_id = 123456789
    user_id = 987654321
    
    # Patch settings in user_commands module
    with patch('src.bot.handlers.user_commands.settings') as mock_settings:
        mock_settings.admin_ids = [admin_id]
        
        try:
            # 1. Admin in Private Chat -> Should pass
            print("\n1. Admin in Private Chat:")
            msg = AsyncMock()
            msg.from_user.id = admin_id
            msg.from_user.username = "admin"
            msg.chat.type = "private"
            msg.text = "/senseihelp"
            
            await cmd_help(msg)
            
            if msg.answer.called:
                args, _ = msg.answer.call_args
                text = args[0]
                if "⚠️" in text:
                    print("❌ Admin in Private failed (got warning)")
                else:
                    print("✅ Admin in Private passed")
            else:
                print("❌ Admin in Private: No response")

            # 2. User in Private Chat -> Should fail
            print("\n2. User in Private Chat:")
            msg = AsyncMock()
            msg.from_user.id = user_id
            msg.from_user.username = "user"
            msg.chat.type = "private"
            msg.text = "/senseihelp"
            
            await cmd_help(msg)
            
            if msg.answer.called:
                args, _ = msg.answer.call_args
                text = args[0]
                if "⚠️" in text:
                    print("✅ User in Private blocked correctly")
                else:
                    print(f"❌ User in Private passed (should block). Text: {text[:50]}...")
            else:
                print("❌ User in Private: No response")

            # 3. User in Group Chat -> Should pass
            print("\n3. User in Group Chat:")
            msg = AsyncMock()
            msg.from_user.id = user_id
            msg.from_user.username = "user"
            msg.chat.type = "group"
            msg.text = "/senseihelp"
            
            await cmd_help(msg)
            
            if msg.answer.called:
                args, _ = msg.answer.call_args
                text = args[0]
                if "⚠️" in text:
                     print("❌ User in Group failed (got warning)")
                else:
                     print("✅ User in Group passed")
            else:
                print("❌ User in Group: No response")

            # 4. Verify Admin Help
            print("\n4. Admin Help (Handler Check):")
            msg = AsyncMock()
            msg.from_user.id = admin_id
            msg.text = "/adminhelp"
            
            await cmd_admin_help(msg)
            if msg.answer.called:
                 print("✅ Admin Help executed successfully")
            else:
                 print("❌ Admin Help: No response")

        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(verify_permissions())
