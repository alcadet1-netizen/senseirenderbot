# Check what the service actually returns - safe version
with open(r'C:\sensei\src\services\duel_service.py', 'rb') as f:
    data = f.read()

content = data.decode('utf-8', errors='replace')
lines = content.split('\n')

print("=== SERVICE RETURN STATEMENTS (safe) ===")
for i, line in enumerate(lines):
    if 'return' in line and ('"' in line or "'" in line):
        # Show line number and length, but don't try to decode problematic chars for display
        print(f"{i+1:4}: [line length: {len(line)}]")
        # Show a safe version - replace non-ASCII with dots for display
        safe_line = ''
        for char in line:
            if ord(char) < 128:
                safe_line += char
            else:
                safe_line += '.'
        if len(safe_line) > 100:
            safe_line = safe_line[:100] + "..."
        print(f"     {safe_line}")

print("\n=== EXAMINING STRING LITERALS IN BYTES ===")
import re

# Find all string literals in return statements by looking at bytes
# Pattern: return followed by quote, then content, then same quote
pattern = rb'return\s+([\'"])(.*?)\1'
matches = list(re.finditer(pattern, data))
print(f"Found {len(matches)} return statements with string literals:")

for i, match in enumerate(matches):
    quote = match.group(1)
    content = match.group(2)
    print(f"\n  Match {i+1}:")
    print(f"    Quote: {quote}")
    print(f"    Content bytes: {content.hex()}")

    # Try to decode as UTF-8
    try:
        decoded = content.decode('utf-8')
        print(f"    As UTF-8 string: {repr(decoded)}")
    except UnicodeDecodeError:
        print(f"    Cannot decode as UTF-8")
        # Show what we can decode with replacements
        try:
            decoded = content.decode('utf-8', errors='replace')
            print(f"    As UTF-8 (replace): {repr(decoded)}")
        except:
            pass

    # Check for specific byte patterns we care about
    # Check mark: \xe2\x9c\x85
    if b'\xe2\x9c\x85' in content:
        print("    --> CONTAINS CHECK MARK (correct)")
    # Cross mark: \xe2\x9d\x9c
    if b'\xe2\x9d\x9c' in content:
        print("    --> CONTAINS CROSS MARK (correct)")
    # Wrong cross mark: \xe2\x9d\x8c
    if b'\xe2\x9d\x8c' in content:
        print("    --> CONTAINS WRONG CROSS MARK (\\xe2\x9d\x8c)")
    # Warning sign: \xe2\x9a\xa0
    if b'\xe2\x9a\xa0' in content:
        print("    --> CONTAINS WARNING SIGN")
    # Replacement char: \xef\xbf\xbd
    if b'\xef\xbf\xbd' in content:
        print("    --> CONTAINS REPLACEMENT CHAR (corruption)")

    # Show context
    start = max(0, match.start()-20)
    end = min(len(data), match.end()+20)
    context = data[start:end]
    try:
        context_str = context.decode('utf-8')
        print(f"    Context: {repr(context_str)}")
    except:
        context_str = context.decode('utf-8', errors='replace')
        print(f"    Context (replace): {repr(context_str)}")

print("\n=== CHECKING TEST FILE EXPECTATIONS ===")
with open(r'C:\sensei\tests\unit\test_duel_service.py', 'rb') as f:
    test_data = f.read()

# Look for assert res == statements
pattern = rb'assert res == \"[^\"]*\"'
matches = list(re.finditer(pattern, test_data))
print(f"Found {len(matches)} 'assert res ==' statements in test:")

for i, match in enumerate(matches):
    matched = match.group()
    # Extract the content between quotes
    quote_pos = matched.find(b'"')
    if quote_pos != -1:
        end_quote_pos = matched.rfind(b'"')
        if end_quote_pos > quote_pos:
            content_bytes = matched[quote_pos+1:end_quote_pos]
            print(f"\n  Assertion {i+1} expected content bytes: {content_bytes.hex()}")

            # Try to decode
            try:
                decoded = content_bytes.decode('utf-8')
                print(f"    As UTF-8 string: {repr(decoded)}")
            except UnicodeDecodeError:
                print(f"    Cannot decode as UTF-8")
                try:
                    decoded = content_bytes.decode('utf-8', errors='replace')
                    print(f"    As UTF-8 (replace): {repr(decoded)}")
                except:
                    pass

            # Check what it should be
            if b'\xe2\x9c\x85' in content_bytes:
                print("    --> EXPECTS CHECK MARK")
            if b'\xe2\x9d\x9c' in content_bytes:
                print("    --> EXPECTS CROSS MARK")
            if b'\xe2\x9d\x8c' in content_bytes:
                print("    --> EXPECTS WRONG CROSS MARK (\\xe2\x9d\x8c) - THIS IS THE BUG!")
            if b'\xef\xbf\xbd' in content_bytes:
                print("    --> EXPECTS REPLACEMENT CHAR (corrupted)")