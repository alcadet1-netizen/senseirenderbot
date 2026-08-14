import re

CRYPTO_CALC_PATTERN = re.compile(r'курс\s+№\s*([a-zA-Z0-9]+)\s*№\s*([\d\.,]+)', re.IGNORECASE)
CRYPTO_AMOUNT_PATTERN = re.compile(r'курс\s+(\d+(?:[.,]\d+)?)\s+([a-zA-Z0-9]+)', re.IGNORECASE)
CRYPTO_PRICE_PATTERN = re.compile(r'курс\s+([a-zA-Z0-9]+)', re.IGNORECASE)

def test_patterns():
    test_cases = [
        ("курс 123 ton", "amount", ("123", "ton")),
        ("курс 123.45 btc", "amount", ("123.45", "btc")),
        ("курс ton", "price", ("ton",)),
        ("курс № ton № 100", "calc", ("ton", "100")),
        ("курс 100", "amount", ("100", "")), # Wait, "100" is matched by [a-zA-Z0-9]+? No, regex needs space then symbol
    ]

    print("Testing regex patterns...")
    
    # Simulate Router order: Calc -> Amount -> Price
    
    texts = [
        "курс 123 ton",
        "курс 0.5 eth",
        "курс ton",
        "курс № ton № 100",
        "курс 123" # Ambiguous?
    ]

    for text in texts:
        print(f"\nText: '{text}'")
        
        # Check Calc
        match = CRYPTO_CALC_PATTERN.search(text)
        if match:
            print(f"  Matched CALC: {match.groups()}")
            continue
            
        # Check Amount
        match = CRYPTO_AMOUNT_PATTERN.search(text)
        if match:
            print(f"  Matched AMOUNT: {match.groups()}")
            continue
            
        # Check Price
        match = CRYPTO_PRICE_PATTERN.search(text)
        if match:
            print(f"  Matched PRICE: {match.groups()}")
            continue
            
        print("  NO MATCH")

if __name__ == "__main__":
    test_patterns()
