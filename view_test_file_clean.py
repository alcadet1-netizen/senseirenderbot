# View the test file content without trying to decode problematic Unicode
with open(r'C:\sensei\tests\unit\test_duel_service.py', 'rb') as f:
    data = f.read()

# Print as hex and ASCII where possible
i = 0
while i < len(data):
    # Show 16 bytes at a time
    hex_part = ''
    ascii_part = ''
    for j in range(16):
        if i + j < len(data):
            b = data[i + j]
            hex_part += f'{b:02x} '
            if 32 <= b <= 126:  # Printable ASCII
                ascii_part += chr(b)
            else:
                ascii_part += '.'
        else:
            hex_part += '   '
            ascii_part += ' '
    print(f'{i:04x}: {hex_part} {ascii_part}')
    i += 16

    # Stop after reasonable amount
    if i > 200:
        break