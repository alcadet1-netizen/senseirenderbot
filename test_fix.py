import random

def test_logic(available_count):
    available = list(range(available_count))
    
    # New logic
    min_count = min(5, len(available))
    max_count = min(10, len(available))
    # randint is inclusive
    try:
        num = random.randint(min_count, max_count)
        print(f"available={available_count}: num={num} (OK)")
    except Exception as e:
        print(f"available={available_count}: FAILED {e}")

test_logic(0) # Should be empty range?
test_logic(1)
test_logic(3)
test_logic(5)
test_logic(7)
test_logic(12)
