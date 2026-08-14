# Check what the service file actually returns
with open(r'C:\sensei\src\services\duel_service.py', 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

# Split by lines and look for return statements
lines = content.split('\n')
for i, line in enumerate(lines):
    if 'return' in line and ('"' in line or "'" in line):
        # Clean up the line for display
        display_line = line.strip()
        if len(display_line) > 100:
            display_line = display_line[:100] + "..."
        print(f"{i+1:3}: {display_line}")

# Let's also look for the specific return values we care about
print("\n=== Looking for specific return values ===")

import re

# Look for return statements with strings
pattern = r'return\s+["\'][^"\']*["\']'
matches = re.findall(pattern, content)
for i, match in enumerate(matches):
    # Clean up for display
    clean_match = match.encode('ascii', errors='replace').decode('ascii')
    print(f"{i+1:2}: {clean_match}")

# Let's get more context around the returns
print("\n=== Detailed return statement analysis ===")
for i, line in enumerate(lines):
    if 'return' in line and ('"' in line or "'" in line):
        print(f"\nLine {i+1}:")
        print(f"  Content: {line}")
        # Show surrounding context
        for j in range(max(0, i-2), min(len(lines), i+3)):
            if j == i:
                print(f"  {j+1:3}: >>> {lines[j]}")
            else:
                print(f"  {j+1:3}:     {lines[j]}")