# View the economy service test to see how it mocks the database
with open(r'C:\sensei\tests\unit\test_economy_service.py', 'r', encoding='utf-8', errors='replace') as f:
    lines = f.readlines()

# Look for the test setup
in_test = False
for i, line in enumerate(lines):
    if '@pytest.mark.asyncio' in line or 'async def test_' in line:
        in_test = True
        print(f"\n--- Test starting at line {i+1} ---")

    if in_test:
        # Show first 20 lines of each test
        if i < 25:  # Just show beginning of file
            print(f"{i+1:4}: {line.rstrip()}")

# Let's look for the container setup more specifically
print("\n" + "="*50)
print("LOOKING FOR CONTAINER SETUP")
print("="*50)

for i, line in enumerate(lines):
    if 'container' in line and ('=' in line or '.' in line):
        if 'mongo' in line or 'database' in line or 'users' in line or 'collection' in line:
            print(f"{i+1:4}: {line.rstrip()}")