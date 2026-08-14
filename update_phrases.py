
import os

file_path = r"c:\Users\bot\Desktop\sensei\GPT\sensei\src\texts\phrases.py"
print(f"Reading file: {file_path}")

with open(file_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
in_welcome_phrases = False
count_replacements = 0

for i, line in enumerate(lines):
    if "WELCOME_PHRASES: List[str] = [" in line:
        print(f"Found WELCOME_PHRASES start at line {i+1}")
        in_welcome_phrases = True
        new_lines.append(line)
        continue
    
    if in_welcome_phrases:
        if line.strip() == "]":
            print(f"Found WELCOME_PHRASES end at line {i+1}")
            in_welcome_phrases = False
            new_lines.append(line)
            continue
        
        # Debug print for first few lines
        if i < 4385:
            print(f"Line {i+1}: {repr(line)}")
            if "{name}" in line:
                print("  Matches {name}")
            else:
                print("  NO MATCH {name}")

        # Replace {name} with @{username} inside the list
        if "{name}" in line:
            new_line = line.replace("{name}", "@{username}")
            new_lines.append(new_line)
            count_replacements += 1
        else:
            new_lines.append(line)
    else:
        # Check for function definition
        if "def get_random_welcome(name: str) -> str:" in line:
            new_lines.append("def get_random_welcome(username: str) -> str:\n")
        elif "return random.choice(WELCOME_PHRASES).format(name=name)" in line:
            new_lines.append("    return random.choice(WELCOME_PHRASES).format(username=username)\n")
        else:
            new_lines.append(line)

print(f"Replacements made: {count_replacements}")

with open(file_path, "w", encoding="utf-8") as f:
    f.writelines(new_lines)
