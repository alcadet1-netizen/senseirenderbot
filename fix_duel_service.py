# Script to fix the encoding issues in duel_service.py
# by replacing the corrupted strings with correct Unicode

with open(r'C:\sensei\src\services\duel_service.py', 'rb') as f:
    data = f.read()

print("Original file size:", len(data))

# Find and replace the corrupted strings
# The pattern we saw was: ����� ����� ��� �✅ which is \xef\xbf\xbd\xef\xbf\xbd\xe2\x9c\x85
# Should be: � ✅ which is \xe2\x9c\x85

# Also: ����� ����� ��� �⚠ which is \xef\xbf\xbd\xef\xbf\xbd\xe2\x9a\xa0
# Should be: �� ⚠ which is \xe2\x9a\xa0

# And: ����� ����� ��� �❌ which is \xef\xbf\xbd\xef\xbf\xbd\xe2\x9d\x9c
# Should be: �� ❌ which is \xe2\x9d\x9c

# Replace double replacement char + emoji with just the emoji
corrupted_check = b'\xef\xbf\xbd\xef\xbf\xbd\xe2\x9c\x85'  # ����� ����� ��� �✅
correct_check = b'\xe2\x9c\x85'                            # � ✅

corrupted_warning = b'\xef\xbf\xbd\xef\xbf\xbd\xe2\x9a\xa0'  # ����� ����� ��� �⚠
correct_warning = b'\xe2\x9a\xa0'                            # �� ⚠

corrupted_cross = b'\xef\xbf\xbd\xef\xbf\xbd\xe2\x9d\x9c'  # ����� ����� ��� �❌
correct_cross = b'\xe2\x9d\x9c'                            # �� ❌

# Do the replacements
fixed_data = data.replace(corrupted_check, correct_check)
fixed_data = fixed_data.replace(corrupted_warning, correct_warning)
fixed_data = fixed_data.replace(corrupted_cross, correct_cross)

print("Fixed file size:", len(fixed_data))
print("Bytes changed:", len(data) - len(fixed_data))

# Write the fixed file
with open(r'C:\sensei\src\services\duel_service.py', 'wb') as f:
    f.write(fixed_data)

print("File has been fixed and saved.")

# Verify the fix
print("\n=== Verification ===")
with open(r'C:\sensei\src\services\duel_service.py', 'rb') as f:
    verify_data = f.read()

# Check that the corrupted patterns are gone
if corrupted_check in verify_data:
    print("ERROR: Corrupted check mark still found!")
else:
    print("SUCCESS: No corrupted check mark found.")

if corrupted_warning in verify_data:
    print("ERROR: Corrupted warning still found!")
else:
    print("SUCCESS: No corrupted warning found.")

if corrupted_cross in verify_data:
    print("ERROR: Corrupted cross mark still found!")
else:
    print("SUCCESS: No corrupted cross mark found.")

# Check that the correct emojis are present
if correct_check in verify_data:
    print("SUCCESS: Correct check mark found.")
else:
    print("ERROR: Correct check mark not found!")

if correct_warning in verify_data:
    print("SUCCESS: Correct warning found.")
else:
    print("ERROR: Correct warning not found!")

if correct_cross in verify_data:
    print("SUCCESS: Correct cross mark found.")
else:
    print("ERROR: Correct cross mark not found!")