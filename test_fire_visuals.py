
import asyncio
import os
import sys

# Добавляем корневую директорию в путь поиска модулей
sys.path.append(os.getcwd())

from src.core.visuals import Visuals
from src.bot.handlers.fire import _frame, build_fire_drop_html, FIRE_EMOJI_POOL

def test_visuals():
    print("Testing visuals...")
    
    # Test _frame
    lines = ["Line 1", "Line 2", "Longer Line 3"]
    frame = _frame(lines, width=20)
    print(f"Frame:\n{frame}")
    
    # Test build_fire_drop_html
    tags = [
        (123456789, "user1", 100),
        (987654321, "user2", 200),
        (111222333, None, 150),
    ]
    html = build_fire_drop_html("Admin", True, "Bank", tags)
    print(f"HTML Output:\n{html}")
    
    print("Visuals test passed!")

if __name__ == "__main__":
    test_visuals()
