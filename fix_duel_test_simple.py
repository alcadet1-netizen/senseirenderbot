# Simple fix: replace wrong cross mark with correct one in test file

with open(r'C:\sensei\tests\unit\test_duel_service.py', 'rb') as f:
    data = f.read()

print("Original test file size:", len(data))

# Replace wrong cross mark (e29d8c) with correct cross mark (e29d9c)
wrong_cross = b'\xe2\x9d\x8c'
correct_cross = b'\xe2\x9d\x9c'

# Count occurrences before
count_before = data.count(wrong_cross)
print(f"Found {count_before} occurrences of wrong cross mark")

# Replace all occurrences
data = data.replace(wrong_cross, correct_cross)

# Count occurrences after
count_after = data.count(wrong_cross)
print(f"After replacement, {count_after} occurrences of wrong cross mark remain")
print(f"Correct cross mark count: {data.count(correct_cross)}")

print("Fixed test file size:", len(data))

# Write the fixed file
with open(r'C:\sensei\tests\unit\test_duel_service.py', 'wb') as f:
    f.write(data)

print("Test file has been fixed and saved.")

# Quick verification
print("\n=== Verification ===")
with open(r'C:\sensei\tests\unit\test_duel_service.py', 'rb') as f:
    verify_data = f.read()

wrong_count = verify_data.count(b'\xe2\x9d\x8c')
correct_count = verify_data.count(b'\xe2\x9d\x9c')
print(f"Wrong cross mark count: {wrong_count}")
print(f"Correct cross mark count: {correct_count}")

if wrong_count == 0:
    print("SUCCESS: All wrong cross marks replaced!")
else:
    print("ERROR: Some wrong cross marks remain")