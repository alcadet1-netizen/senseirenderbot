# Examine the test assertions by reading the file as bytes and manually interpreting
with open(r'C:\sensei\tests\unit\test_duel_service.py', 'rb') as f:
    data = f.read()

# Convert to string, replacing problematic bytes
content = data.decode('utf-8', errors='replace')

lines = content.split('\n')
print("=== Test File Assertions ===")
for i, line in enumerate(lines):
    if 'assert' in line:
        print(f"{i+1:3}: {line}")

print("\n=== Looking for specific patterns ===")
# Look for lines that contain the problematic strings
for i, line in enumerate(lines):
    if 'res ==' in line:
        print(f"{i+1:3}: {repr(line)}")
    elif 'accepted' in line:
        print(f"{i+1:3}: {repr(line)}")
    elif 'duel_id' in line:
        print(f"{i+1:3}: {repr(line)}")

# Now let's look at what the service actually returns
print("\n=== Checking service returns ===")
with open(r'C:\sensei\src\services\duel_service.py', 'rb') as f:
    service_data = f.read()

service_content = service_data.decode('utf-8', errors='replace')
service_lines = service_content.split('\n')

# Look for return statements
returns_found = []
for i, line in enumerate(service_lines):
    if 'return' in line and ('"' in line or "'" in line):
        returns_found.append((i+1, line.strip()))

print("Return statements in service:")
for line_num, ret in returns_found:
    print(f"{line_num:3}: {ret}")

# Let's look more carefully at the specific return values by searching for patterns
print("\n=== Detailed return analysis ===")
import re

# Find all return statements with string literals
pattern = r'return\s*([\'"])(.*?)\1'
matches = re.findall(pattern, service_content)
for i, (quote, content) in enumerate(matches):
    print(f"{i+1:2}: {repr(content)} (quote: {quote})")