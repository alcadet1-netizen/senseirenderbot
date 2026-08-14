# Look at the test file to see what's actually there
with open(r'C:\sensei\tests\unit\test_duel_service.py', 'rb') as f:
    data = f.read()

print("Test file size:", len(data))
print("First 200 bytes:", data[:200])
print()

# Let's just look for the assertion lines
import re

# Find all assert lines
assert_pattern = rb'assert .+'
matches = list(re.finditer(assert_pattern, data))
print(f"Found {len(matches)} assert statements:")
for match in matches[:20]:  # First 20
    start = max(0, match.start()-10)
    end = min(len(data), match.end()+10)
    context = data[start:end]
    try:
        print(f"  {context.decode('utf-8', errors='replace')}")
    except:
        print(f"  [Binary data: {context.hex()}]")
    print()

# Now let's look for the specific strings that are in the assertions
print("\n=== Looking for specific strings in assertions ===")

# Look for the pattern: assert res == "...."
pattern = rb'assert res == \"[^\"]*\"'
matches = list(re.finditer(pattern, data))
print(f"Found {len(matches)} res assertions:")
for match in matches:
    start = max(0, match.start()-5)
    end = min(len(data), match.end()+5)
    context = data[start:end]
    try:
        print(f"  {context.decode('utf-8', errors='replace')}")
    except:
        print(f"  [Binary: {context.hex()}]")
    print()

# Also look for assert True in ... patterns
pattern2 = rb'assert True in [^\]]+'
matches = list(re.finditer(pattern2, data))
print(f"Found {len(matches)} True in assertions:")
for match in matches:
    start = max(0, match.start()-5)
    end = min(len(data), match.end()+5)
    context = data[start:end]
    try:
        print(f"  {context.decode('utf-8', errors='replace')}")
    except:
        print(f"  [Binary: {context.hex()}]")
    print()