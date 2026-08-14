with open(r'C:\sensei\src\services\duel_service.py', 'rb') as f:
    data = f.read()

# Look for the specific strings we care about
print("Looking for emoji strings in the service file...")

# Check around line 203-204 (the "Отклонено" string)
# Actually, let's look for the specific return statements

# Find "return \"Отклонено.\""
target = b'return "\\xd0\x9e\xd1\x82\xd0\xba\xd0\xbb\xd0\xbe\xd0\xbd\xd0\xb5\xd0\xa0\xd1\x80\xd0\xbe"'
print("Looking for 'return \"Отклонено.\"' pattern...")
for i in range(len(data) - 20):
    if data[i:i+2] == b'return':
        # Found return statement, show context
        start = max(0, i-10)
        end = min(len(data), i+50)
        context = data[start:end]
        try:
            decoded = context.decode('utf-8', errors='replace')
            if 'Отклонено' in decoded or 'return' in decoded:
                print(f"Found return statement at {i}: {decoded}")
        except:
            pass

print("\nLooking for specific patterns...")
# Look for the emoji patterns
for i in range(len(data)):
    if i+2 < len(data) and data[i] == 0xEF and data[i+1] == 0xBF and data[i+2] == 0xBD:
        # This is the UTF-8 encoding of the replacement character ��� �
        start = max(0, i-10)
        end = min(len(data), i+10)
        context = data[start:end]
        print(f"Replacement char at {i}: {context.hex()}")

# Look for actual emoji bytes
emoji_bytes = [
    (0xE2, 0x9C, 0x85, "��✅"),  # U+2705
    (0xE2, 0x9D, 0x97, "��❌"),  # U+274C
    (0xE2, 0x9A, 0xA1, "��⚠"),  # U+26A0
]

for b1, b2, b3, emoji in emoji_bytes:
    print(f"\nLooking for {emoji} ({b1:02x}{b2:02x}{b3:02x}):")
    for i in range(len(data)-2):
        if data[i] == b1 and data[i+1] == b2 and data[i+2] == b3:
            start = max(0, i-10)
            end = min(len(data), i+10)
            context = data[start:end]
            try:
                decoded = context.decode('utf-8', errors='replace')
                print(f"  Found at {i}: {decoded}")
            except:
                print(f"  Found at {i}: {context.hex()}")