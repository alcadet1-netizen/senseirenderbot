
import os

path = r'c:\Users\bot\Desktop\sensei\GPT\sensei\src\core\constants.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Remove lines 1237-1853 (0-based indices)
# Keep 0..1236
# Keep 1854..end
new_lines = lines[:1237] + lines[1854:]

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Done")
