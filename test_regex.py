
import re

VANGA_PATTERN = re.compile(r'(сенсей\s+вангуй)', re.IGNORECASE)
text1 = "сенсей вангуй мне"
text2 = "Сенсей вангуй что будет"
text3 = "сенсей вангуй"

def check(text):
    print(f"Testing: '{text}'")
    match = VANGA_PATTERN.search(text)
    if match:
        print("  Match found")
        is_me = re.search(r'\bмне\b', text, re.IGNORECASE)
        if is_me:
            print("  'мне' detected -> self")
        else:
            print("  'мне' NOT detected -> random")
    else:
        print("  No match")

check(text1)
check(text2)
check(text3)
