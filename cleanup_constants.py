import os

file_path = 'src/core/constants.py'
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip = False
removed = False

for line in lines:
    if 'EASTER_EGGS: Dict[str, str] = {' in line:
        skip = True
        removed = True
    
    if not skip:
        new_lines.append(line)
        
    if skip and line.strip() == '}':
        skip = False

with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

if removed:
    print("EASTER_EGGS removed successfully.")
else:
    print("EASTER_EGGS not found.")
