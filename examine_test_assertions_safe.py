# Examine the test assertions safely
with open(r'C:\sensei\tests\unit\test_duel_service.py', 'rb') as f:
    data = f.read()

print("=== Test File Analysis (bytes) ===")
print(f"File size: {len(data)} bytes")

# Look for assertion patterns in bytes
import re

# Pattern for: assert res == "..."
pattern = rb'assert res == \"[^\"]*\"'
matches = list(re.finditer(pattern, data))
print(f"\nFound {len(matches)} 'assert res ==' statements:")
for match in matches:
    # Get the matched bytes
    matched = match.group()
    print(f"  Matched bytes: {matched.hex()}")
    # Try to decode as UTF-8, showing replacement chars
    try:
        decoded = matched.decode('utf-8')
        print(f"  As UTF-8: {repr(decoded)}")
    except UnicodeDecodeError:
        decoded = matched.decode('utf-8', errors='replace')
        print(f"  As UTF-8 (replace): {repr(decoded)}")
    # Show context
    start = max(0, match.start()-20)
    end = min(len(data), match.end()+20)
    context = data[start:end]
    try:
        ctx_decoded = context.decode('utf-8')
        print(f"  Context: {repr(ctx_decoded)}")
    except UnicodeDecodeError:
        ctx_decoded = context.decode('utf-8', errors='replace')
        print(f"  Context (replace): {repr(ctx_decoded)}")
    print()

# Look for other assertion patterns
pattern2 = rb'assert True in [^\]]+'
matches2 = list(re.finditer(pattern2, data))
print(f"Found {len(matches2)} 'assert True in' statements:")
for match in matches2:
    matched = match.group()
    print(f"  Matched bytes: {matched.hex()}")
    try:
        decoded = matched.decode('utf-8')
        print(f"  As UTF-8: {repr(decoded)}")
    except UnicodeDecodeError:
        decoded = matched.decode('utf-8', errors='replace')
        print(f"  As UTF-8 (replace): {repr(decoded)}")
    print()

pattern3 = rb'assert duel\.accepted is True'
matches3 = list(re.finditer(pattern3, data))
print(f"Found {len(matches3)} 'assert duel.accepted is True' statements:")
for match in matches3:
    matched = match.group()
    print(f"  Matched bytes: {matched.hex()}")
    try:
        decoded = matched.decode('utf-8')
        print(f"  As UTF-8: {repr(decoded)}")
    except UnicodeDecodeError:
        decoded = matched.decode('utf-8', errors='replace')
        print(f"  As UTF-8 (replace): {repr(decoded)}")
    print()

# Now let's look at the service file
print("\n" + "="*50)
print("=== SERVICE FILE ANALYSIS ===")
with open(r'C:\sensei\src\services\duel_service.py', 'rb') as f:
    service_data = f.read()

print(f"Service file size: {len(service_data)} bytes")

# Look for return statements with strings
pattern_ret = rb'return\s*([\'"])(.*?)\1'
matches_ret = list(re.finditer(pattern_ret, service_data))
print(f"\nFound {len(matches_ret)} return statements with string literals:")
for match in matches_ret:
    quote = match.group(1)
    content = match.group(2)
    print(f"  Quote: {quote}")
    print(f"  Content bytes: {content.hex()}")
    try:
        content_decoded = content.decode('utf-8')
        print(f"  Content (UTF-8): {repr(content_decoded)}")
    except UnicodeDecodeError:
        content_decoded = content.decode('utf-8', errors='replace')
        print(f"  Content (UTF-8 replace): {repr(content_decoded)}")
    # Show context
    start = max(0, match.start()-20)
    end = min(len(service_data), match.end()+20)
    context = service_data[start:end]
    try:
        ctx_decoded = context.decode('utf-8')
        print(f"  Context: {repr(ctx_decoded)}")
    except UnicodeDecodeError:
        ctx_decoded = context.decode('utf-8', errors='replace')
        print(f"  Context (replace): {repr(ctx_decoded)}")
    print()