import re

CRYPTO_CALC_PATTERN = re.compile(r'курс\s+(?:№\s*)?([\d\.,]+)\s+(?:№\s*)?([a-zA-Z]+)|курс\s+(?:№\s*)?([a-zA-Z]+)\s+(?:№\s*)?([\d\.,]+)', re.IGNORECASE)

test_cases = [
    "курс 100 ton",
    "курс 100.5 ton",
    "курс 100,5 ton",
    "курс ton 100",
    "курс № ton № 100",
    "курс № 100 № ton", # Less likely but possible with optional №
    "курс TON", # Should not match
    "курс 100", # Should not match
    "курс ton is going up" # Should not match
]

print("Testing CRYPTO_CALC_PATTERN:")
for text in test_cases:
    match = CRYPTO_CALC_PATTERN.search(text)
    if match:
        print(f"MATCH: '{text}' -> {match.groups()}")
    else:
        print(f"NO MATCH: '{text}'")
