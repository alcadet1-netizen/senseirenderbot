# Fix the duel service file:
# 1. Replace the wrong cross mark (e29d8c) with the correct one (e29d9c)
# 2. Replace sequences of two replacement chars followed by the correct emojis with just the emoji

with open(r'C:\sensei\src\services\duel_service.py', 'rb') as f:
    data = f.read()

print("Original file size:", len(data))

# Step 1: Replace wrong cross mark with correct cross mark
wrong_cross = b'\xe2\x9d\x8c'   # U+274C? Actually, this is not the cross mark, it's a different character
correct_cross = b'\xe2\x9d\x9c' # This is the actual cross mark emoji (��❌)

# Replace all occurrences of the wrong cross mark with the correct one
data = data.replace(wrong_cross, correct_cross)
print(f"Replaced wrong cross mark with correct one. New size: {len(data)}")

# Step 2: Replace sequences of two replacement chars followed by the correct emojis
# We define the corruptions and their corrections
corruptions = [
    (b'\xef\xbf\xbd\xef\xbf\xbd\xe2\x9c\x85', b'\xe2\x9c\x85'),  # ������ ������ ������ � ���� ���� ���� ✅ -> ���� � �� ✅
    (b'\xef\xbf\xbd\xef\xbf\xbd\xe2\x9a\xa0', b'\xe2\x9a\xa0'),  # ������ ������ ������ �� ���� ���� ���� ⚠ -> ���� �� �� ⚠
    (b'\xef\xbf\xbd\xef\xbf\xbd\xe2\x9d\x9c', b'\xe2\x9d\x9c'),  # ������ ������ ������ �� ���� ���� ���� ❌ -> ���� �� �� ❌
]

for corrupt, correct in corruptions:
    while corrupt in data:
        data = data.replace(corrupt, correct)
        print(f"Replaced {corrupt.hex()} with {correct.hex()}")

print("Fixed file size:", len(data))

# Write the fixed file
with open(r'C:\sensei\src\services\duel_service.py', 'wb') as f:
    f.write(data)

print("File has been fixed and saved.")

# Verify the fix
print("\n=== Verification ===")
with open(r'C:\sensei\src\services\duel_service.py', 'rb') as f:
    verify_data = f.read()

# Check that the wrong cross mark is gone
if wrong_cross in verify_data:
    print("ERROR: Wrong cross mark still found!")
else:
    print("SUCCESS: No wrong cross mark found.")

# Check that the correct cross mark is present (we expect at least one)
if correct_cross in verify_data:
    print("SUCCESS: Correct cross mark found.")
else:
    print("ERROR: Correct cross mark not found!")

# Check that the corruptions are gone
for corrupt, _ in corruptions:
    if corrupt in verify_data:
        print(f"ERROR: Corruption {corrupt.hex()} still found!")
    else:
        print(f"SUCCESS: No corruption {corrupt.hex()} found.")

# Let's also check for the specific strings we know
print("\n=== Checking for known strings ===")
# We expect to find:
#   ���� � �� ✅ Принято! Смотрите ЛС.  -> \xe2\x9c\x85 + space + Cyrillic for "Принято! Смотрите ЛС."
#   Отклонено.                    -> Cyrillic for "Отклонено."
#   ���� �� �� ❌ Это не вам.             -> \xe2\x9d\x9c + space + Cyrillic for "Это не вас."

# Check for the check mark string pattern
check_mark_bytes = b'\xe2\x9c\x85'
if check_mark_bytes in verify_data:
    print("Found check mark emoji in service.")
    # Show context around one occurrence
    pos = verify_data.find(check_mark_bytes)
    start = max(0, pos-20)
    end = min(len(verify_data), pos+50)
    context = verify_data[start:end]
    try:
        print(f"  Context: {context.decode('utf-8', errors='replace')}")
    except:
        pass
else:
    print("Check mark emoji NOT found in service.")

# Check for the correct cross mark
if correct_cross in verify_data:
    print("Found correct cross mark emoji in service.")
    pos = verify_data.find(correct_cross)
    start = max(0, pos-20)
    end = min(len(verify_data), pos+50)
    context = verify_data[start:end]
    try:
        print(f"  Context: {context.decode('utf-8', errors='replace')}")
    except:
        pass
else:
    print("Correct cross mark emoji NOT found in service.")

# Check for the "Отклонено." string
otkaz_bytes = b'\xd0\x9e\xd1\x82\xd0\xba\xd0\xbb\xd0\xbe\xd0\xbd\xd0\xb5\xd0\xbd\xd0\xbe\x2e'
if otkaz_bytes in verify_data:
    print("Found 'Отклонено.' string in service.")
else:
    print("'Отклонено.' string NOT found in service.")