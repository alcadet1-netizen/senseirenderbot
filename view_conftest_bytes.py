# View conftest.py as bytes
with open(r'C:\sensei\tests\conftest.py', 'rb') as f:
    data = f.read()

print(f"File size: {len(data)} bytes")
print("First 200 bytes:")
print(data[:200])
print()

# Look for mongo or database patterns
import re

# Find lines that mention mongo or database
pattern = rb'(?i)(mongo|database|client|users?)'
matches = list(re.finditer(pattern, data))
print(f"Found {len(matches)} matches for mongo/database patterns:")
for match in matches[:10]:
    start = max(0, match.start()-20)
    end = min(len(data), match.end()+20)
    context = data[start:end]
    print(f"  Context: {context}")
    print()

# Look for AsyncMock or MagicMock usage
pattern2 = rb'(AsyncMock|MagicMock)'
matches2 = list(re.finditer(pattern2, data))
print(f"Found {len(matches2)} matches for Mock patterns:")
for match in matches2[:10]:
    start = max(0, match.start()-20)
    end = min(len(data), match.end()+20)
    context = data[start:end]
    print(f"  Context: {context}")
    print()