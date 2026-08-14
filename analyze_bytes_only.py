# Analyze the bytes only, no string conversion for output
with open(r'C:\sensei\tests\unit\test_duel_service.py', 'rb') as f:
    test_data = f.read()

with open(r'C:\sensei\src\services\duel_service.py', 'rb') as f:
    service_data = f.read()

print("=== TEST FILE ANALYSIS ===")
print(f"Test file size: {len(test_data)} bytes")

# Find assert res == statements
import re
pattern = rb'assert res == \"[^\"]*\"'
matches = list(re.finditer(pattern, test_data))
print(f"\nFound {len(matches)} 'assert res ==' statements:")

for i, match in enumerate(matches):
    matched = match.group()
    print(f"\n  Match {i+1}:")
    print(f"    Bytes: {matched.hex()}")
    # Show the ASCII parts we can safely print
    ascii_parts = []
    for b in matched:
        if 32 <= b <= 126:
            ascii_parts.append(chr(b))
        else:
            ascii_parts.append(f'\\x{b:02x}')
    ascii_str = ''.join(ascii_parts)
    print(f"    As ASCII-escaped: {ascii_str}")

# Now let's look at the specific bytes that differ
print("\n=== COMPARING ASSERTION BYTES TO EXPECTED ===")

# What we expect for the strings:
# "� �� ✅ Уже идет дуэль с противником @{challenger_id}."
# Should be: \xe2\x9c\x85 + space + Cyrillic text

# "������������� ����������������� ��" (Declined)
# Should be: Cyrillic text for "Отклонено."

# "��� ����� ❌ Это не вам."
# Should be: \xe2\x9d\x9c + space + Cyrillic text for "Это не вам."

# Let's manually decode what we think the assertions should be
expected_ok = "������ ��� ���� ������ ��� ���� ������� � �� ���� � �� ✅ Уже идет дуэль с противником @{challenger_id}."
# Actually, let's look at the service to see what it returns

print("\n=== SERVICE FILE RETURN STATEMENTS ===")
pattern_ret = rb'return\s*([\'"])(.*?)\1'
matches_ret = list(re.finditer(pattern_ret, service_data))
print(f"Found {len(matches_ret)} return statements:")

for i, match in enumerate(matches_ret):
    quote = match.group(1)
    content = match.group(2)
    print(f"\n  Return {i+1}:")
    print(f"    Quote: {quote}")
    print(f"    Content bytes: {content.hex()}")
    # Try to decode as UTF-8 for understanding
    try:
        content_str = content.decode('utf-8')
        print(f"    As UTF-8 string: {content_str}")
    except:
        print(f"    Cannot decode as UTF-8")

    # Show context
    start = max(0, match.start()-30)
    end = min(len(service_data), match.end()+30)
    context = service_data[start:end]
    try:
        context_str = context.decode('utf-8')
        print(f"    Context: {context_str[:100]}...")
    except:
        pass

# Let's look at the specific area around where we saw returns before
print("\n=== LOOKING AT SPECIFIC RETURN VALUES ===")
# From earlier debug, we saw around position 7307 and 8190
positions_to_check = [7307, 8190, 5131, 8253]
for pos in positions_to_check:
    if pos < len(service_data):
        start = max(0, pos-20)
        end = min(len(service_data), pos+20)
        chunk = service_data[start:end]
        print(f"\n  Position {pos} area:")
        print(f"    Bytes: {chunk.hex()}")
        try:
            decoded = chunk.decode('utf-8')
            print(f"    As UTF-8: {repr(decoded)}")
        except:
            print(f"    Cannot decode as UTF-8")

# Now let's look at what the test file expects
print("\n=== WHAT THE TEST FILE EXPECTS ===")
for i, match in enumerate(matches):
    matched = match.group()
    # Extract the string content between quotes
    # Pattern: assert res == "..."
    quote_pos = matched.find(b'"')
    if quote_pos != -1:
        # Find the closing quote
        end_quote_pos = matched.rfind(b'"')
        if end_quote_pos > quote_pos:
            content_bytes = matched[quote_pos+1:end_quote_pos]
            print(f"\n  Assertion {i+1} expected content bytes: {content_bytes.hex()}")
            try:
                expected_str = content_bytes.decode('utf-8')
                print(f"    As UTF-8 string: {repr(expected_str)}")
            except:
                print(f"    Cannot decode as UTF-8")