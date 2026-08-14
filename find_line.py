
with open(r"c:\Users\bot\Desktop\sensei\GPT\sensei\src\texts\phrases.py", "r", encoding="utf-8") as f:
    lines = f.readlines()
    for i, line in enumerate(lines):
        if "def check_easter_egg" in line:
            print(f"Found at line {i+1}")
            print(f"Content: {line.strip()}")
            print(f"Next line: {lines[i+1].strip() if i+1 < len(lines) else 'EOF'}")
