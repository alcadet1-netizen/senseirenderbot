
import os
import shutil

file_path = r"c:\Users\bot\Desktop\sensei\GPT\sensei\src\texts\phrases.py"
temp_path = file_path + ".tmp"

print(f"Reading file: {file_path}")

with open(file_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}")

new_lines = []
in_welcome_phrases = False
count_replacements = 0
welcome_phrases_found = False

for i, line in enumerate(lines):
    if "WELCOME_PHRASES: List[str] = [" in line:
        print(f"Found WELCOME_PHRASES start at line {i+1}")
        in_welcome_phrases = True
        welcome_phrases_found = True
        new_lines.append(line)
        continue
    
    if in_welcome_phrases:
        if line.strip() == "]":
            print(f"Found WELCOME_PHRASES end at line {i+1}")
            in_welcome_phrases = False
            new_lines.append(line)
            continue
        
        # Replace {name} with @{username} inside the list
        if "{name}" in line:
            new_line = line.replace("{name}", "@{username}")
            new_lines.append(new_line)
            count_replacements += 1
        else:
            new_lines.append(line)
    else:
        new_lines.append(line)

if not welcome_phrases_found:
    print("ERROR: WELCOME_PHRASES block not found!")
    exit(1)

print(f"Replacements prepared: {count_replacements}")

# Write to temp file first
try:
    with open(temp_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    print(f"Written to temp file: {temp_path}")
    
    # Replace original file
    shutil.move(temp_path, file_path)
    print(f"Successfully overwrote {file_path}")
    
except Exception as e:
    print(f"Failed to write file: {e}")
    if os.path.exists(temp_path):
        os.remove(temp_path)
    exit(1)

# Verify content
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()
    if "@{username}" in content and "{name}" not in content[content.find("WELCOME_PHRASES"):content.find("BAN_PHRASES")]:
        print("VERIFICATION SUCCESS: File contains @{username} and no {name} in WELCOME_PHRASES")
    else:
        print("VERIFICATION WARNING: Check file content manually.")
