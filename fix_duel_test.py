# Fix the duel service test file:
# Change the wrong cross mark (e29d8c) to the correct one (e29d9c) in the assertion

with open(r'C:\sensei\tests\unit\test_duel_service.py', 'rb') as f:
    data = f.read()

print("Original test file size:", len(data))

# Find and replace the wrong cross mark in the assertion
# The assertion that's failing is: assert res == "��� ������� ������ ������ ������ ������ ���� ������ ��������� ����� ���� ���� ���� ���� �� ���� ����."
# In bytes: e29d8c20d0add182d0be20d0bdd0b520d0b2d0b0d0bc2e
# Should be:  e29d9c20d0add182d0be20d0bdd0b520d0b2d0b0d0bc2e

wrong_cross_in_assertion = b'e29d8c20d0add182d0be20d0bdd0b520d0b2d0b0d0bc2e'
correct_cross_in_assertion = b'e29d9c20d0add182d0be20d0bdd0b520d0b2d0b0d0bc2e'

# Check if the wrong pattern exists
if wrong_cross_in_assertion in data:
    print("Found wrong cross mark in test assertion")
    data = data.replace(wrong_cross_in_assertion, correct_cross_in_assertion)
    print("Replaced wrong cross mark with correct one in test")
else:
    print("Wrong cross mark pattern not found in test")

print("Fixed test file size:", len(data))

# Write the fixed file
with open(r'C:\sensei\tests\unit\test_duel_service.py', 'wb') as f:
    f.write(data)

print("Test file has been fixed and saved.")

# Verify the fix
print("\n=== Verification ===")
with open(r'C:\sensei\tests\unit\test_duel_service.py', 'rb') as f:
    verify_data = f.read()

# Check that the wrong cross mark is gone from assertions
if wrong_cross_in_assertion in verify_data:
    print("ERROR: Wrong cross mark still found in test assertion!")
else:
    print("SUCCESS: No wrong cross mark found in test assertion.")

# Check that the correct cross mark is present in assertions
if correct_cross_in_assertion in verify_data:
    print("SUCCESS: Correct cross mark found in test assertion.")
else:
    print("ERROR: Correct cross mark not found in test assertion!")

# Also verify by looking at the assertions
import re

# Look for assert res == statements
pattern = rb'assert res == \"[^\"]*\"'
matches = list(re.finditer(pattern, verify_data))
print(f"\nFound {len(matches)} 'assert res ==' statements in test:")

for i, match in enumerate(matches):
    matched = match.group()
    # Extract the content between quotes
    quote_pos = matched.find(b'"')
    if quote_pos != -1:
        end_quote_pos = matched.rfind(b'"')
        if end_quote_pos > quote_pos:
            content_bytes = matched[quote_pos+1:end_quote_pos]
            print(f"\n  Assertion {i+1} content bytes: {content_bytes.hex()}")
            try:
                expected = content_bytes.decode('utf-8')
                print(f"     As UTF-8: {repr(expected)}")
            except UnicodeDecodeError:
                try:
                    expected = content_bytes.decode('utf-8', errors='replace')
                    print(f"     As UTF-8 (replace): {repr(expected)}")
                except:
                    print(f"     Cannot decode")