with open(r'C:\sensei\src\services\duel_service.py', 'rb') as f:
    data = f.read()

# Find the area around where we think the string is
target_bytes = b'\xd0\x9f\xd1\x80\xd0\xb8\xd0\xbd\xd1\x8f\xd1\x82\xd0\xbe'  # "Принято" in UTF-8
for i in range(len(data) - len(target_bytes)):
    if data[i:i+len(target_bytes)] == target_bytes:
        print(f"Found 'Принято' at position {i}")
        # Show surrounding bytes
        start = max(0, i - 20)
        end = min(len(data), i + len(target_bytes) + 20)
        print(f"Surrounding bytes: {data[start:end]}")
        print(f"As hex: {data[start:end].hex()}")
        # Try to decode as UTF-8
        try:
            decoded = data[start:end].decode('utf-8')
            print(f"As UTF-8: {repr(decoded)}")
        except Exception as e:
            print(f"UTF-8 decode error: {e}")
        break