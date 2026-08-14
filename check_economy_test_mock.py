# Check how economy service test mocks the database
with open(r'C:\sensei\tests\unit\test_economy_service.py', 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

# Look for container setup
lines = content.split('\n')
for i, line in enumerate(lines):
    if 'container' in line.lower() and ('mongo' in line.lower() or 'database' in line.lower() or '.users' in line):
        print(f"{i+1:4}: {line}")