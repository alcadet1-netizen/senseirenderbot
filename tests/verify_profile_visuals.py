import sys
import os

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from core.visuals import Visuals

def test_profile_card_stats():
    print("Testing Visuals.profile_card with wins and losses...")
    
    # Mock data
    username = "SenseiMaster"
    wins = 10
    losses = 5
    
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
        wins=wins,
        losses=losses
    )
    
    print("\nGenerated Card:")
    print(card)
    
    # Verify
    expected_stats = f"⚔ W{wins} / L{losses}"
    if expected_stats in card:
        print(f"\n✅ SUCCESS: Found '{expected_stats}' in profile card.")
    else:
        print(f"\n❌ FAILURE: '{expected_stats}' NOT found in profile card.")
        exit(1)

if __name__ == "__main__":
    test_profile_card_stats()
