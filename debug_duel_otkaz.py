with open(r'C:\sensei\src\services\duel_service.py', 'rb') as f:
    data = f.read()

# Find the area around where we think the string is
target_bytes = b'\xd0\x9e\xd1\x82\xd0\xba\xd0\xbb\xd0\xbe\xd0\xbd\xd0\xb5\xd0\xbd\xd0\xbe'  # "Отклонено" in UTF-8
for i in range(len(data) - len(target_bytes)):
    if data[i:i+len(target_bytes)] == target_bytes:
        print(f"Found 'Отклонено' at position {i}")
        # Show more surrounding bytes
        start = max(0, i - 20)
        end = min(len(data), i + len(target_bytes) + 20)
        chunk = data[start:end]
        print(f"Surrounding bytes: {chunk}")
        print(f"As hex: {chunk.hex()}")
        # Try to decode as UTF-8
        try:
            decoded = chunk.decode('utf-8')
            print(f"As UTF-8: {repr(decoded)}")
        except Exception as e:
            print(f"UTF-8 decode error: {e}")
        break