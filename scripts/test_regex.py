import re

pattern = r"^\+fire\s+(\d+(?:\.\d+)?)(?:\s+([a-zA-Zа-яА-ЯёЁ]+))?"
texts = [
    "+fire 100",
    "+fire 100 coin",
    "+fire 100 coins",
    "+fire 100 tickets",
    "+fire 100.5",
    "+fire 100.5 coin",
    "+fire 100   coin", # multiple spaces
]

print("Testing regex:", pattern)
for t in texts:
    m = re.search(pattern, t, re.IGNORECASE)
    print(f"'{t}': {m.groups() if m else 'No match'}")
