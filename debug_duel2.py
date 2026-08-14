with open(r'C:\sensei\src\services\duel_service.py', 'rb') as f:
    data = f.read()

# Find the area around the string we're interested in
for i, b in enumerate(data):
    if b == ord('\n'):
        # Look at a window around each newline
        start = max(0, i-50)
        end = min(len(data), i+50)
        chunk = data[start:end]
        if b'Принято' in chunk:
            print(f"Line around {i}: {chunk}")
            # Also print as string
            try:
                print(chunk.decode('utf-8'))
            except:
                print("Cannot decode as utf-8")
            break