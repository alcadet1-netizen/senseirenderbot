
import sys
import os

# Add project root to sys.path
sys.path.append(os.getcwd())

from src.core.visuals import Visuals

print(f"Top: '{Visuals.frame_top(10)}'")
print(f"Line: '{Visuals.frame_line('test', 10)}'")
print(f"Bottom: '{Visuals.frame_bottom(10)}'")
print(f"Separator: '{Visuals.frame_separator(10)}'")
