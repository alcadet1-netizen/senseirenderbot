# Simple search for assertions in test file
with open(r'C:\sensei\tests\unit\test_duel_service.py', 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

# Split by lines and look for assert statements
lines = content.split('\n')
for i, line in enumerate(lines):
    if 'assert' in line and ('res' in line or 'duel' in line or 'True' in line):
        print(f"{i+1:3}: {line}")