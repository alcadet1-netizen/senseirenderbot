# Test to check encoding
test_str = "Никто не выиграл"
print("Original string:", repr(test_str))
print("Original string:", test_str)

# Check each character
for i, c in enumerate(test_str):
    print(f"Char {i}: '{c}' (Unicode: {ord(c)})")

# Write to file and read back
with open('test_encoding.txt', 'w', encoding='utf-8') as f:
    f.write(test_str)

with open('test_encoding.txt', 'r', encoding='utf-8') as f:
    read_str = f.read()
    print("Read from file:", repr(read_str))
    print("Read from file:", read_str)