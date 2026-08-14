from src.core.visuals import Visuals

def test_start_menu_link():
    menu = Visuals.start_menu("TestUser")
    expected_link = '<a href="https://telegra.ph/SENSEI-BOT-ULTIMATE-GUIDE-01-05">🏯 SENSEI BOT: ULTIMATE GUIDE</a>'
    
    print("Generated Menu:")
    print(menu)
    
    if expected_link in menu:
        print("\n✅ Verification SUCCESS: Link found in start menu.")
    else:
        print("\n❌ Verification FAILED: Link NOT found in start menu.")

if __name__ == "__main__":
    test_start_menu_link()
