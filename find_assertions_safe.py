# Safe search for assertions in test file
with open(r'C:\sensei\tests\unit\test_duel_service.py', 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

# Split by lines and look for assert statements
lines = content.split('\n')
assert_count = 0
for i, line in enumerate(lines):
    if 'assert' in line:
        assert_count += 1
        if assert_count <= 10:  # Show first 10
            # Replace problematic Unicode with description for display
            display_line = line.encode('ascii', errors='replace').decode('ascii')
            print(f"{i+1:3}: {display_line}")

print(f"\nTotal assertions found: {assert_count}")

# Now let's look specifically for the res assertions
print("\n=== Looking for 'assert res ==' statements ===")
for i, line in enumerate(lines):
    if 'assert res ==' in line:
        display_line = line.encode('ascii', errors='replace').decode('ascii')
        print(f"{i+1:3}: {display_line}")

# And for the warning/cross mark ones
print("\n=== Looking for warning/cross mark patterns ===")
for i, line in enumerate(lines):
    if '$' in line and ('accept' in line.lower() or 'warn' in line.lower() or 'cross' in line.lower() or 'declined' in line.lower() or 'отклон' in line.lower() or 'принят' in line.lower()):
        display_line = line.encode('ascii', errors='replace').decode('ascii')
        print(f"{i+1:3}: {display_line}")