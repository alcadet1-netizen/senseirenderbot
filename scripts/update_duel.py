import os

path = 'src/services/duel_service.py'
print(f"Reading {path}")
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}")

# Keep 0-20 (lines 1-21)
# Insert import
# Keep 2457-end (lines 2458+)

new_lines = lines[:21]
new_lines.append("\nfrom src.services.duel_resources import (ARENAS, DODGE_GAGS_L, DODGE_GAGS_R, ATTACK_GAGS_L, ATTACK_GAGS_R, HIT_GAGS, MISS_GAGS, DUEL_COOLDOWN_SEC, DUEL_ACCEPT_TIMEOUT_SEC, DUEL_ROUND_TIMEOUT_SEC, LOG_LIMIT, DODGES, HITS, DuelDecisionCb, DuelMoveCb)\n\n")
new_lines.extend(lines[2457:])

print(f"New lines count: {len(new_lines)}")

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Done")
