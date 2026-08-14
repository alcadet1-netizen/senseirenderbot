# Debug the failing test by looking at what the service actually returns
with open(r'C:\sensei\src\services\duel_service.py', 'rb') as f:
    data = f.read()

# Look for the return statement in the failing test
# From the test name: test_duel_process_decision_wrong_user_cannot_accept
# This should be returning the "Это не вам." string with cross mark

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

    # Try to decode as UTF-8
    try:
        decoded = content.decode('utf-8')
        print(f"     As UTF-8: {repr(decoded)}")

        # Check for specific patterns
        if b'\xe2\x9d\x9c' in content:
            print("     --> Contains correct cross mark (\u274c)")
        if b'\xe2\x9d\x8c' in content:
            print("     --> Contains wrong cross mark (\u275c?)")
        if b'\xe2\x9c\x85' in content:
            print("     --> Contains check mark (\u2705)")
        if b'\xe2\x9a\xa0' in content:
            print("     --> Contains warning sign (\u26a0)")

    except UnicodeDecodeError:
        print(f"     Cannot decode as UTF-8")
        # Try with replacement
        try:
            decoded = content.decode('utf-8', errors='replace')
            print(f"     As UTF-8 (replace): {repr(decoded)}")
        except:
            pass

# Let's also look at the specific test that's failing
print("\n" + "="*50)
print("LOOKING AT THE SPECIFIC TEST CASE")
print("="*50)

# Read the test file to see what it's expecting
with open(r'C:\sensei\tests\unit\test_duel_service.py', 'rb') as f:
    test_data = f.read()

# Look for the specific failing test
test_pattern = rb'test_duel_process_decision_wrong_user_cannot_accept'
test_match = re.search(test_pattern, test_data)
if test_match:
    print(f"Found test at position {test_match.start()}")
    # Get some context around it
    start = max(0, test_match.start()-100)
    end = min(len(test_data), test_match.start()+500)
    context = test_data[start:end]
    try:
        print(f"Context: {context.decode('utf-8', errors='replace')}")
    except:
        print(f"Context (bytes): {context.hex()}")

# Now let's look for the assertion in that test
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
            try:
                expected = content_bytes.decode('utf-8')
                print(f"     As UTF-8: {repr(expected)}")
            except UnicodeDecodeError:
                try:
                    expected = content_bytes.decode('utf-8', errors='replace')
                    print(f"     As UTF-8 (replace): {repr(expected)}")
                except:
                    print(f"     Cannot decode")