# Check what the service actually returns by looking at the source
with open(r'C:\sensei\src\services\duel_service.py', 'r', encoding='utf-8', errors='replace') as f:
    lines = f.readlines()

print("=== SERVICE RETURN STATEMENTS (lines) ===")
for i, line in enumerate(lines):
    if 'return' in line and ('"' in line or "'" in line):
        # Clean up whitespace
        cleaned = line.strip()
        if len(cleaned) > 100:
            cleaned = cleaned[:100] + "..."
        print(f"{i+1:4}: {cleaned}")

print("\n=== LOOKING FOR SPECIFIC PATTERNS ===")
# Look for the strings we know should be there
import re

# Join all lines
content = ''.join(lines)

# Look for return statements with emojis
pattern = r'return\s*[\'"]([^\'"]*[\xe2-\xef][\x80-\xbf]{2}[^\'"]*)[\'"]'
matches = re.findall(pattern, content)
print(f"\nFound {len(matches)} return statements with potential emojis:")

for i, match in enumerate(matches):
    print(f"\n  Match {i+1}:")
    print(f"    Raw match: {repr(match)}")
    # Try to understand what it is
    try:
        # This might fail if it's corrupted
        decoded = match.encode('utf-8').decode('utf-8')
        print(f"    As string: {repr(decoded)}")
    except:
        print(f"    Cannot process as UTF-8 string")
        # Show bytes
        try:
            match_bytes = match.encode('utf-8', errors='replace')
            print(f"    Bytes: {match_bytes.hex()}")
        except:
            pass

# Let's also look for the specific strings by searching for known patterns
print("\n=== SEARCHING FOR KNOWN GOOD PATTERNS ===")

# The correct strings should be:
# 1. "��✅ Принято! Смотрите ЛС."  -> \xe2\x9c\x85 + space + Cyrillic
# 2. "Отклонено."  -> Cyrillic only
# 3. "��❌ Это не вам."  -> \xe2\x9d\x9c + space + Cyrillic

# Let's see what the service actually has for these
known_patterns = [
    (b'\xe2\x9c\x85', "CHECK MARK"),
    (b'\xe2\x9d\x9c', "CROSS MARK"),
    (b'\xd0\x9e\xd1\x82\xd0\xba\xd0\xbb\xd0\xbe\xd0\xbd\xd0\xb5\xd0\xbd\xd0\xbe', "OTKAZANO"),
    (b'\xd0\x9f\xd1\x80\xd0\xb8\xd0\xbd\xd1\x8f\xd1\x82\xd0\xbe', "PRINYATO"),
    (b'\xd0\xa1\xd0\xbc\xd0\xbe\xd1\x82\xd1\x80\xd0\xb8\xd1\x82\xd0\xb5', "SMOTRITE"),
    (b'\xd0\x9b\xd0\xa1', "LS"),
    (b'\xd0\xa2\xd0\xb0\xd0\xba\xd0\xC1\xd0\xB5\xd1\x82', "ETO"),  # Это - wait, let me check
]

print("\nSearching for known byte patterns in service:")
for pattern_bytes, name in known_patterns:
    if pattern_bytes in service_data:
        print(f"  Found {name}: {pattern_bytes.hex()}")
        pos = service_data.find(pattern_bytes)
        # Show context
        start = max(0, pos-10)
        end = min(len(service_data), pos+len(pattern_bytes)+10)
        context = service_data[start:end]
        print(f"    Context bytes: {context.hex()}")
        try:
            print(f"    Context: {context.decode('utf-8', errors='replace')}")
        except:
            pass
    else:
        print(f"  NOT FOUND {name}: {pattern_bytes.hex()}")

# Let me also check what the ACTUAL strings look like by extracting them from return statements
print("\n=== EXTRACTING STRING LITERALS FROM RETURNS ===")
# More precise pattern for return statements
return_pattern = r'return\s+([\'"])(.*?)\1'
return_matches = re.findall(return_pattern, content)

valid_returns = []
for quote, string_content in return_matches:
    valid_returns.append((quote, string_content))

print(f"Found {len(valid_returns)} return statements with string literals:")

for i, (quote, string_content) in enumerate(valid_returns):
    print(f"\n  Return {i+1} (quote={quote}):")
    print(f"    Content (raw): {repr(string_content)}")

    # Try to decode as UTF-8
    try:
        decoded = string_content.encode('utf-8').decode('utf-8')
        print(f"    As UTF-8 string: {repr(decoded)}")

        # Check if it contains emojis we care about
        if '��✅' in decoded:
            print("    --> Contains CHECK MARK")
        if '��❌' in decoded:
            print("    --> Contains CROSS MARK")
        if '��⚠' in decoded:
            print("    --> Contains WARNING")

        # Check for Russian words
        if 'Принято' in decoded:
            print("    --> Contains 'Принято'")
        if 'Отклонено' in decoded:
            print("    --> Contains 'Отклонено'")
        if 'Это не вам' in decoded:
            print("    --> Contains 'Это не вам'")
        if 'Смотрите ЛС' in decoded:
            print("    --> Contains 'Смотрите ЛС'")

    except UnicodeDecodeError:
        print(f"    Cannot decode as UTF-8 (corrupted?)")
        # Show the bytes
        try:
            string_bytes = string_content.encode('utf-8', errors='replace')
            print(f"    Bytes: {string_bytes.hex()}")
        except:
            pass