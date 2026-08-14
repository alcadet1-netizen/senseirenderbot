with open(r'C:\sensei\src\services\duel_service.py', 'rb') as f:
    data = f.read()

# Find the area around where we think the string is
target_bytes = b'\xd0\x9f\xd1\x80\xd0\xb8\xd0\xbd\xd1\x8f\xd1\x82\xd0\xbe'  # "Принято" in UTF-8
for i in range(len(data) - len(target_bytes)):
    if data[i:i+len(target_bytes)] == target_bytes:
        print(f"Found 'Принято' at position {i}")
        # Show more surrounding bytes
        start = max(0, i - 30)
        end = min(len(data), i + len(target_bytes) + 30)
        chunk = data[start:end]
        print(f"Surrounding bytes: {chunk}")
        print(f"As hex: {chunk.hex()}")
        # Try to decode as UTF-8, replacing errors
        try:
            decoded = chunk.decode('utf-8')
            print(f"As UTF-8: {repr(decoded)}")
        except Exception as e:
            print(f"UTF-8 decode error: {e}")
            # Show what we can decode
            try:
                decoded = chunk.decode('utf-8', errors='replace')
                print(f"As UTF-8 (replace): {repr(decoded)}")
            except Exception as e2:
                print(f"Even replace failed: {e2}")
        break