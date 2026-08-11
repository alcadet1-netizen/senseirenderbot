import sys
import os

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from core.visuals import Visuals

def test_profile_card_with_role():
    print("Testing Visuals.profile_card with role argument...")
    
    # Mock data
    username = "SenseiMaster"
    
    try:
        card = Visuals.profile_card(
            username=username,
            level=5,
            level_name="Novice",
            xp=100,
            xp_next=200,
            coins=1000,
            tickets=2,
            messages=50,
            streak=3,
            has_katana=True,
            achievements_count=1,
            katana_length=15.5,
            wins=10,
            losses=5,
            role="Admin"
        )
        print("\nGenerated Card with Role:")
        print(card)
        
        if "👺 Admin" in card:
            print("\n✅ SUCCESS: Found role 'Admin' in profile card.")
        else:
            print("\n❌ FAILURE: Role 'Admin' NOT found in profile card.")
            exit(1)
            
    except TypeError as e:
        print(f"\n❌ FAILURE: TypeError occurred: {e}")
        exit(1)
    except Exception as e:
        print(f"\n❌ FAILURE: Unexpected error: {e}")
        exit(1)

if __name__ == "__main__":
    test_profile_card_with_role()
