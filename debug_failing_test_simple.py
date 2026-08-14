# Debug the failing test - simple byte version
with open(r'C:\sensei\src\services\duel_service.py', 'rb') as f:
    data = f.read()

# Look for the return statement in the failing test
import re

# Find all return statements
pattern = rb'return\s+([\'"])(.*?)\1'
matches = list(re.finditer(pattern, data))

print("All return statements in service:")
for i, match in enumerate(matches):
    quote = match.group(1)
    content = match.group(2)
    print(f"\n  {i+1}. Quote: {quote}")
    print(f"     Content bytes: {content.hex()}")

    # Check for specific byte patterns we care about
    if b'\xe2\x9d\x9c' in content:
        print("     --> Contains correct cross mark (\\xe2\\x9d\\x9c)")
    if b'\xe2\x9d\x8c' in content:
        print("     --> Contains wrong cross mark (\\xe2\\x9d\\x8c)")
    if b'\xe2\x9c\x85' in content:
        print("     --> Contains check mark (\\xe2\\x9c\\x85)")
    if b'\xe2\x9a\xa0' in content:
        print("     --> Contains warning sign (\\xe2\\x9a\\xa0)")

# Let's also look at the specific test that's failing
print("\n" + "="*50)
print("LOOKING AT THE SPECIFIC TEST CASE")
print("="*50)

# Read the test file to see what it's expecting
with open(r'C:\sensei\tests\unit\test_duel_service.py', 'rb') as f:
    test_data = f.read()

# Look for the assertion in the failing test
assert_pattern = rb'assert res == \"[^\"]*\"'
assert_matches = list(re.finditer(assert_pattern, test_data))
print(f"\nFound {len(assert_matches)} assertions in test file:")

for i, match in enumerate(assert_matches):
    matched = match.group()
    # Extract the quoted part
    quote_pos = matched.find(b'"')
    if quote_pos != -1:
        end_quote_pos = matched.rfind(b'"')
        if end_quote_pos > quote_pos:
            content_bytes = matched[quote_pos+1:end_quote_pos]
            print(f"\n  Assertion {i+1} expects: {content_bytes.hex()}")

# Now let's look at what the specific failing test expects
# Based on the error message, it expects: '\u274c \u042d\u0442\u043e \u043d\u0435 \u0432\u0430\u043c.'
# Which in UTF-8 is: \xe2\x9d\x9c + space + \xd0\xad\xd1\x82\xd0\xbe\x20\xd0\xbd\xd0\xb5\x20\xd0\xb2\xd0\xb0\xd0\xbc\x2e
expected_bytes = b'\xe2\x9d\x9c \xd0\xad\xd1\x82\xd0\xbe\x20\xd0\xbd\xd0\xb5\x20\xd0\xb2\xd0\xb0\xd0\xbc\x2e'
print(f"\nExpected bytes for failing test: {expected_bytes.hex()}")

# Let's see if we can find this exact sequence in the service
if expected_bytes in data:
    print("SUCCESS: Found expected sequence in service!")
    pos = data.find(expected_bytes)
    print(f"  Position: {pos}")
    # Show context
    start = max(0, pos-20)
    end = min(len(data), pos+len(expected_bytes)+20)
    context = data[start:end]
    print(f"  Context bytes: {context.hex()}")
else:
    print("Expected sequence NOT found in service")
    # Let's see what's close
    # Look for the cross mark + space
    cross_space = b'\xe2\x9d\x9c '
    if cross_space in data:
        print("Found cross mark + space in service")
        pos = data.find(cross_space)
        # Show what comes after
        after_start = pos + len(cross_space)
        after_end = min(len(data), after_start + 50)
        after_bytes = data[after_start:after_end]
        print(f"  Bytes after cross+space: {after_bytes.hex()}")
        try:
            after_text = after_bytes.decode('utf-8', errors='replace')
            print(f"  Text after: {repr(after_text)}")
        except:
            pass
    else:
        print("Cross mark + space NOT found in service")

    # Look for the wrong cross mark + space
    wrong_cross_space = b'\xe2\x9d\x8c '
    if wrong_cross_space in data:
        print("Found WRONG cross mark + space in service")
        pos = data.find(wrong_cross_space)
        print(f"  Position: {pos}")
        # Show what comes after
        after_start = pos + len(wrong_cross_space)
        after_end = min(len(data), after_start + 50)
        after_bytes = data[after_start:after_end]
        print(f"  Bytes after wrong cross+space: {after_bytes.hex()}")
        try:
            after_text = after_bytes.decode('utf-8', errors='replace')
            print(f"  Text after: {repr(after_text)}")
        except:
            pass