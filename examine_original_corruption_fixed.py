# Examine the original corruption patterns by looking at what we know was corrupted
# Based on the error messages from earlier

print("=== Examining what we know was corrupted ===")

# From the test file error, we saw:
# assert res == "������������������������������������."
# This was supposed to be "Отклонено."

# Let's see what "Отклонено." looks like in UTF-8
otkaz = "Отклонено."
print(f'"{otkaz}" in UTF-8 bytes: {otkaz.encode("utf-8").hex()}')

# And what we saw in the test was asserting against "������������������������������������."
# Let's see what that looks like
corrupted_otkaz = "������������������������������������."
print(f'"{corrupted_otkaz}" would be bytes: {[hex(b) for b in corrupted_otkaz.encode("utf-8", errors="replace")]}')

# But actually, let's look at the test file directly
with open(r'C:\sensei\tests\unit\test_duel_service.py', 'rb') as f:
    test_data = f.read()

print(f'\nTest file size: {len(test_data)}')

# Look for the assertion that was failing
# assert res == "������������������������������������."
look_for = b'assert res == '
for i in range(len(test_data) - len(look_for) + 1):
    if test_data[i:i+len(look_for)] == look_for:
        print(f'Found assertion at position {i}')
        # Get the next 50 bytes
        start = i
        end = min(len(test_data), i + 50)
        chunk = test_data[start:end]
        print(f'Context bytes: {chunk.hex()}')
        try:
            print(f'Context: {chunk.decode("utf-8")}')
        except:
            print(f'Context (replaced): {chunk.decode("utf-8", errors="replace")}')
        break

# Now let's look at what the SERVICE file actually has for the return statement
# We know from earlier debugging that around position 7307 we found:
#   return "\xd0\x9e\xd1\x82\xd0\xba\xd0\xbb\xd0\xbe\xd0\xbd\xd0\xb5\xd0\xbd\xd0\xbe."
# which IS correct "Отклонено."

# But the issue might be elsewhere. Let's look for the emoji patterns in the service file
print('\n=== Checking service file for emoji patterns ===')
with open(r'C:\sensei\src\services\duel_service.py', 'rb') as f:
    service_data = f.read()

# Let's search for patterns of replacement characters followed by emoji-like bytes
import re

# Look for sequences of \xef\xbf\xbd (replacement char) followed by emoji bytes
pattern = b'(\xef\xbf\xbd)+([\xe2-\xef][\x80-\xbf]{2})'
matches = list(re.finditer(pattern, service_data))
print(f'Found {len(matches)} potential replacement+emoji sequences')

for match in matches[:10]:  # Show first 10
    start = match.start()
    end = match.end()
    print(f'  Position {start}-{end}: {service_data[start:end].hex()}')
    try:
        decoded = service_data[start:end].decode('utf-8')
        print(f'    Decoded: {repr(decoded)}')
    except:
        print(f'    Cannot decode')

# Let's also look for the specific strings we expect
print('\n=== Looking for expected strings ===')

# Expected: ������ ��� ���� � ���� � �� ✅ Уже идет дуэль с противником @{challenger_id}.
# UTF-8 for "��� ����������� ��������� ��������� ������ ������ ��������� ������� ������� ���� ���� ��������� ������� ������� ���� ���� ������� ����� ����� �� ✅ Уже идет дуэль с противником @{challenger_id}."
# Would be: \xe2\x9c\x85 + space + \xd0\xa3\xd0\xb6\xd0\xb5\x20\xd0\xb8\xd0\xb5\xd1\x82\x20\xd0\xb4\xd1\x83\xd0\xb5\xd0\xbb\x20\xd1\x81\x20\xd0\xbf\xd1\x80Г\xd0\xb8\xd0\xb2\xd0\xbd\xd0\xbe\x6d\x20\x40\x7b\x63\x68\x61\x6c\x6c\x65\x6e\x67\x65\x72\x5f\x69\x64\x7d

# But let's look for the emoji at least
check_mark = b'\xe2\x9c\x85'
print(f'\nLooking for check mark {check_mark.hex()}:')

for i in range(len(service_data) - len(check_mark) + 1):
    if service_data[i:i+len(check_mark)] == check_mark:
        print(f'  Found at position {i}')
        # Show before and after
        before_start = max(0, i-20)
        after_end = min(len(service_data), i+len(check_mark)+20)
        context = service_data[before_start:after_end]
        print(f'  Context bytes: {context.hex()}')
        try:
            print(f'  Context: {context.decode("utf-8")}')
        except Exception as e:
            print(f'  Cannot decode: {e}')
        break

# Cross mark
cross_mark = b'\xe2\x9d\x9c'
print(f'\nLooking for cross mark {cross_mark.hex()}:')

for i in range(len(service_data) - len(cross_mark) + 1):
    if service_data[i:i+len(cross_mark)] == cross_mark:
        print(f'  Found at position {i}')
        # Show before and after
        before_start = max(0, i-20)
        after_end = min(len(service_data), i+len(cross_mark)+20)
        context = service_data[before_start:after_end]
        print(f'  Context bytes: {context.hex()}')
        try:
            print(f'  Context: {context.decode("utf-8")}')
        except Exception as e:
            print(f'  Cannot decode: {e}')
        break
else:
    print('  Cross mark NOT found')

# Warning sign
warning = b'\xe2\x9a\xa0'
print(f'\nLooking for warning sign {warning.hex()}:')

for i in range(len(service_data) - len(warning) + 1):
    if service_data[i:i+len(warning)] == warning:
        print(f'  Found at position {i}')
        # Show before and after
        before_start = max(0, i-20)
        after_end = min(len(service_data), i+len(warning)+20)
        context = service_data[before_start:after_end]
        print(f'  Context bytes: {context.hex()}')
        try:
            print(f'  Context: {context.decode("utf-8")}')
        except Exception as e:
            print(f'  Cannot decode: {e}')
        break