# Check for cross mark in duel service file
with open(r'C:\sensei\src\services\duel_service.py', 'rb') as f:
    data = f.read()

print("File size:", len(data))

# Check for cross mark
cross_correct = b'\xe2\x9d\x9c'
cross_corrupted = b'\xef\xbf\xbd\xef\xbf\xbd\xe2\x9d\x9c'

print('Cross mark correct bytes:', cross_correct.hex())
print('Cross mark corrupted bytes:', cross_corrupted.hex())
print()
print('Correct cross mark in data:', cross_correct in data)
print('Corrupted cross mark in data:', cross_corrupted in data)

# Find positions
if cross_correct in data:
    pos = data.find(cross_correct)
    print(f'Found correct cross mark at position {pos}')
    # Show context
    start = max(0, pos-20)
    end = min(len(data), pos+20)
    context = data[start:end]
    print(f'Context bytes: {context.hex()}')
    try:
        print(f'Context decoded: {context.decode("utf-8")}')
    except Exception as e:
        print(f'Cannot decode context: {e}')

if cross_corrupted in data:
    pos = data.find(cross_corrupted)
    print(f'Found corrupted cross mark at position {pos}')
    # Show context
    start = max(0, pos-20)
    end = min(len(data), pos+20)
    context = data[start:end]
    print(f'Context bytes: {context.hex()}')
    try:
        print(f'Context decoded: {context.decode("utf-8")}')
    except Exception as e:
        print(f'Cannot decode context: {e}')

# Let's also search for the specific strings we know should be there
print('\n=== Searching for known strings ===')

# String that should contain cross mark: "��� ����� ❌ Это не вам."
# In UTF-8: \xe2\x9d\x9c + space + \xd0\x95\xd1\x82\xd0\xbe\x20\xd0\xbd\xd0\xb5\x20\xd0\xb2\xd0\xb0\xd0\xbc\x2e
target_with_cross = b'\xe2\x9d\x9c \xd0\x95\xd1\x82\xd0\xbe\x20\xd0\xbd\xd0\xb5\x20\xd0\xb2\xd0\xb0\xd0\xbc\x2e'
print('Looking for: "��� ����� ❌ Это не вам."')
print('Target bytes:', target_with_cross.hex())
found = False
for i in range(len(data) - len(target_with_cross) + 1):
    if data[i:i+len(target_with_cross)] == target_with_cross:
        print(f'  Found at position {i}')
        start = max(0, i-10)
        end = min(len(data), i+len(target_with_cross)+10)
        context = data[start:end]
        print(f'  Context bytes: {context.hex()}')
        try:
            print(f'  Context decoded: {context.decode("utf-8")}')
        except Exception as e:
            print(f'  Cannot decode context: {e}')
        found = True
        break
if not found:
    print('  Not found')

# String that should contain warning: "��� ���� ��������� �� ����"
# In UTF-8: \xe2\x9a\xa0 + space + \xd0\x9f\xd0\xbe\xd1\x8a\xd0\xba\xd0\xb5\xd0\xbd\xd0\xbd\xd0\xbe\x2e
target_with_warning = b'\xe2\x9a\xa0 \xd0\x9f\xd0\xbe\xd1\x8a\xd0\xba\xd0\xb5\xd0\xbd\xd0\xbd\xd0\xbe\x2e'
print('\\nLooking for: "��� ���� ��������� �� ����."')
print('Target bytes:', target_with_warning.hex())
found = False
for i in range(len(data) - len(target_with_warning) + 1):
    if data[i:i+len(target_with_warning)] == target_with_warning:
        print(f'  Found at position {i}')
        start = max(0, i-10)
        end = min(len(data), i+len(target_with_warning)+10)
        context = data[start:end]
        print(f'  Context bytes: {context.hex()}')
        try:
            print(f'  Context decoded: {context.decode("utf-8")}')
        except Exception as e:
            print(f'  Cannot decode context: {e}')
        found = True
        break
if not found:
    print('  Not found')

# Let's look at the specific area where we saw issues before (around line 5131 from earlier)
print('\\n=== Checking area around position 5131 ===')
start = max(0, 5131-50)
end = min(len(data), 5131+50)
chunk = data[start:end]
print(f'Bytes from {start} to {end}:')
print(chunk.hex())
print()
try:
    decoded = chunk.decode('utf-8')
    print('Decoded:')
    print(decoded)
except Exception as e:
    print(f'Cannot decode as UTF-8: {e}')
    # Try to decode with replacement
    try:
        decoded = chunk.decode('utf-8', errors='replace')
        print('Decoded with replacement:')
        print(decoded)
    except Exception as e2:
        print(f'Even replacement failed: {e2}')