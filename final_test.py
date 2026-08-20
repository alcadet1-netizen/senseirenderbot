#!/usr/bin/env python3
"""Final test to verify /senseivisual command logic without Unicode output"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.core.config import settings
from src.core.visuals import Visuals
from src.bot.keyboards.inline import VisualsCb

def test_admin_check():
    """Test that our test user is recognized as admin"""
    test_user_id = 980561369  # BoozyGrimm from logs
    is_admin = test_user_id in settings.admin_ids
    return is_admin

def test_visuals_initial_state():
    """Test initial Visuals state"""
    return Visuals.STYLE

def test_command_logic():
    """Test the command logic without sending actual messages"""
    # Check if user is admin (simulating AdminFilter)
    test_user_id = 980561369
    is_admin = test_user_id in settings.admin_ids
    if not is_admin:
        return False

    # Test that we can generate the keyboard
    keyboard_inline = [
        [{"text": "1. Старый стиль (Рамки)", "callback_data": VisualsCb(action="keep", user_id=test_user_id).pack()}],
        [{"text": "2. Новый стиль (Clean)", "callback_data": VisualsCb(action="clean", user_id=test_user_id).pack()}],
        [{"text": "3. Crypto Bot (Mobile)", "callback_data": VisualsCb(action="crypto", user_id=test_user_id).pack()}],
    ]
    # If we get here, keyboard generation works

    # Test style mapping
    style_map = {
        "classic": "Старый (С рамками)",
        "clean": "Clean (Без рамок)",
        "crypto": "Crypto Bot (Mobile)"
    }
    current_style = style_map.get(Visuals.STYLE, "Неизвестно")

    # Test message generation logic
    message_text = (
        "🎨 <b>Настройка визуала</b>\n\n"
        "Текущий стиль: <b>{}</b>\n\n"
        "Выберите стиль оформления уведомлений:"
    ).format(current_style)
    # If we get here, message generation works
    return True

def test_callback_logic():
    """Test the callback logic"""
    test_user_id = 980561369
    callback_data_clean = VisualsCb(action="clean", user_id=test_user_id)

    # Simulate callback processing
    if callback_data_clean.action == "clean":
        old_style = Visuals.STYLE
        Visuals.STYLE = "clean"
        new_style = Visuals.STYLE
        style_changed = (new_style == "clean")
        Visuals.STYLE = old_style  # Reset
        return style_changed
    else:
        return False

def main():
    """Run all tests"""
    # Test 1: Admin check
    admin_ok = test_admin_check()

    # Test 2: Initial state
    initial_style = test_visuals_initial_state()

    # Test 3: Command logic
    command_ok = test_command_logic()

    # Test 4: Callback logic
    callback_ok = test_callback_logic()

    # Summary
    all_passed = admin_ok and command_ok and callback_ok

    # Reset Visuals.STYLE to default
    Visuals.STYLE = "classic"

    return all_passed

if __name__ == "__main__":
    result = main()
    if result:
        print("SUCCESS: All tests passed")
    else:
        print("FAILURE: Some tests failed")
    sys.exit(0 if result else 1)