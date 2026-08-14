
with open(r"c:\Users\bot\Desktop\sensei\GPT\sensei\src\texts\phrases.py", "r", encoding="utf-8") as f:
    lines = f.readlines()
    for i, line in enumerate(lines):
        if "def check_easter_egg" in line:
            print(f"Start at line {i+1}")
            for j in range(i, i+20):
                print(f"{j+1}: {lines[j].rstrip()}")
            break
