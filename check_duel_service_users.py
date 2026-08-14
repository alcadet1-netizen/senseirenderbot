# Check how the duel service accesses the users collection
with open(r'C:\sensei\src\services\duel_service.py', 'r', encoding='utf-8', errors='replace') as f:
    lines = f.readlines()

# Look around line 555
start_line = max(0, 550 - 5)
end_line = min(len(lines), 555 + 5)

print("Lines around 555 in duel_service.py:")
for i in range(start_line, end_line):
    marker = ">>> " if i == 554 else "    "
    print(f"{marker}{i+1:4}: {lines[i].rstrip()}")

# Let's also look for how the service gets the users container
print("\n" + "="*50)
print("LOOKING FOR SERVICE INITIALIZATION")
print("="*50)

# Find the __init__ method
in_init = False
for i, line in enumerate(lines):
    if '__init__' in line:
        in_init = True
        print(f"Found __init__ at line {i+1}")
    if in_init:
        print(f"{i+1:4}: {lines[i].rstrip()}")
        if line.strip() and not line.startswith(' ') and not line.startswith('\t') and i > 0:
            # We've exited the init method
            break