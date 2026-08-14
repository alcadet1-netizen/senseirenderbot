try:
    import aiogram
    print("aiogram found")
except ImportError:
    print("aiogram NOT found")

try:
    import src
    print("src found")
except ImportError:
    print("src NOT found")
