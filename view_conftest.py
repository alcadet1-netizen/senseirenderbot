# View the conftest.py to see how fixtures are set up
with open(r'C:\sensei\tests\conftest.py', 'r', encoding='utf-8', errors='replace') as f:
    lines = f.readlines()

print("=== CONFTES.PY CONTENT ===")
for i, line in enumerate(lines):
    print(f"{i+1:4}: {line.rstrip()}")