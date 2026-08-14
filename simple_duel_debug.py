# Simple debug script to check encoding in duel service file
with open(r'C:\sensei\src\services\duel_service.py', 'rb') as f:
    data = f.read()

print("File size:", len(data))
print("First 100 bytes:", data[:100])

# Look for the specific strings mentioned in the error
# "Отклонено." - this is what we saw getting corrupted
otkaz_bytes = b'\xd0\x9e\xd1\x82\xd0\xba\xd0\xbb\xd0\xbe\xd0\xbd\xd0\xb5\xd0\xbd\xd0\xbe\x2e'
print("\nLooking for 'Отклонено.' bytes:", otkaz_bytes.hex())
for i in range(len(data) - len(otkaz_bytes) + 1):
    if data[i:i+len(otkaz_bytes)] == otkaz_bytes:
        print(f"  Found 'Отклонено.' at position {i}")
        # Show context
        start = max(0, i-10)
        end = min(len(data), i+len(otkaz_bytes)+10)
        context = data[start:end]
        print(f"  Context: {context}")
        break

# Look for "Принято! Смотрите ЛС."
prinyato_bytes = b'\xd0\x9f\xd1\x80\xd0\xb8\xd0\xbd\xd1\x8f\xd1\x82\xd0\xbe\x21\x20\xd0\xa1\xd0\xbc\xd0\xbe\xd1\x82\xd1\x80\xd0\xb8\xd1\x82\xd0\xb5\x20\xd0\x9b\xd0\xa1\x2e'
print("\nLooking for 'Принято! Смотрите ЛС.' bytes:", prinyato_bytes.hex())
for i in range(len(data) - len(prinyato_bytes) + 1):
    if data[i:i+len(prinyato_bytes)] == prinyato_bytes:
        print(f"  Found 'Принято! Смотрите ЛС.' at position {i}")
        # Show context
        start = max(0, i-10)
        end = min(len(data), i+len(prinyato_bytes)+10)
        context = data[start:end]
        print(f"  Context: {context}")
        break

# Look for emoji bytes
print("\n--- Looking for emoji bytes ---")
# Check mark U+2705: \xe2\x9c\x85
check_mark = b'\xe2\x9c\x85'
print(f"Looking for check mark {check_mark.hex()}:")
for i in range(len(data) - len(check_mark) + 1):
    if data[i:i+len(check_mark)] == check_mark:
        print(f"  Found check mark at position {i}")
        start = max(0, i-10)
        end = min(len(data), i+len(check_mark)+10)
        context = data[start:end]
        print(f"  Context: {context}")
        break

# Cross mark U+274C: \xe2\x9d\x9c
cross_mark = b'\xe2\x9d\x9c'
print(f"Looking for cross mark {cross_mark.hex()}:")
for i in range(len(data) - len(cross_mark) + 1):
    if data[i:i+len(cross_mark)] == cross_mark:
        print(f"  Found cross mark at position {i}")
        start = max(0, i-10)
        end = min(len(data), i+len(cross_mark)+10)
        context = data[start:end]
        print(f"  Context: {context}")
        break

# Warning sign U+26A0: \xe2\x9a\xa0
warning = b'\xe2\x9a\xa0'
print(f"Looking for warning {warning.hex()}:")
for i in range(len(data) - len(warning) + 1):
    if data[i:i+len(warning)] == warning:
        print(f"  Found warning at position {i}")
        start = max(0, i-10)
        end = min(len(data), i+len(warning)+10)
        context = data[start:end]
        print(f"  Context: {context}")
        break

# Now let's look at the test file to see what's happening there
print("\n\n=== Checking test file ===")
try:
    with open(r'C:\sensei\tests\unit\test_duel_service.py', 'rb') as f:
        test_data = f.read()
    print(f"Test file size: {len(test_data)}")

    # Look for the same strings in the test file
    for i in range(len(test_data) - len(otkaz_bytes) + 1):
        if test_data[i:i+len(otkaz_bytes)] == otkaz_bytes:
            print(f"  Found 'Отклонено.' in test file at position {i}")
            start = max(0, i-20)
            end = min(len(test_data), i+len(otkaz_bytes)+20)
            context = test_data[start:end]
            try:
                print(f"  Context (decoded): {context.decode('utf-8')}")
            except:
                print(f"  Context (bytes): {context}")
            break

except FileNotFoundError:
    print("Test file not found")