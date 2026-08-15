# Mechanics Checklist: Reserve Bot vs Current Project

## Goal
Verify that all game mechanics from the reserve bot (C:\senseirezerv) are correctly implemented in the current project (C:\sensei) after refactoring to MongoDB.

## Mechanics List

### 1. Level System
- [x] XP per message configuration
- [x] Level XP requirements
- [x] Level names and icons
- [x] Level up rewards (if any)

### 2. Economy
- [x] Coins per message rate
- [x] Halving thresholds and multiplier logic
- [x] Bank system (initial supply, max supply, deposit/withdraw)
- [x] Message reward processing (XP, coins, halving)
- [x] Ticket award threshold (messages per ticket)
- [x] Exchange rates (coins <-> tickets)

### 3. Katana System
- [x] Katana purchase cost
- [x] Katana upgrade cost table (dynamic by length) -> **COMPLETED**: constants present and upgrade_katana now uses dynamic table via _get_katana_upgrade_cost method
- [x] Katana upgrade cooldown
- [x] Katana win chance in duels

### 4. Boss System
- [x] Boss list with HP, damage range, folder, coin reward, ticket chance
- [x] Boss tiers and grouping
- [x] Boss reward logic (coins, ticket chance)

### 5. Achievement System
- [x] List of achievements with criteria and rewards (XP, coins, rarity, icon)
- [x] Achievement unlocking logic (checking conditions)
- [x] Reward granting for achievements (XP, coins, transactions)
- [x] Prevention of duplicate unlocks
- [x] Force-check capability (for testing)

### 6. Throttling & Anti-Spam
- [x] Command throttling (rate limit, warning instead of block)
- [x] Message reward throttling (separate limit for granting rewards)
- [x] Notification cooldowns

### 7. User Activity & Rewards
- [x] Awarding XP and coins for messages (in group chats only)
- [x] Ticket awards based on message count
- [x] Level up notifications and rewards
- [x] Achievement notifications and rewards
- [x] Daily bonus system (base XP/coins, streak bonuses)
- [x] Referral system (rewards for referrer and referee)

### 8. Ticket & Lottery System
- [x] Ticket generation (unique codes)
- [x] Ticket storage and retrieval
- [x] Ticket holders listing
- [x] Ticket exchange (coins <-> tickets)

### 9. Digest Service
- [x] Message summarization (limit, cooldown)
- [x] Trigger conditions (auto-digest threshold)
- [x] Reward for digest generation (if any)

### 10. Banking & Transactions
- [x] Bank balance management (withdrawal/deposit)
- [x] Transaction recording (types: message_reward, achievement_reward, admin_grant, etc.)
- [x] Transaction history

### 11. User Profile & Stats
- [x] User data fields (id, username, first_name, last_name, xp, level, coins, messages_count, streak, tickets, wins, losses, has_katana, katana_length, is_banned, etc.)
- [x] Profile retrieval and display
- [x] User search (by username, random user)
- [x] Leaderboards (XP, coins, messages, streak, katana length)

### 12. Administrative Commands
- [x] Admin coin addition (withdraw from bank)
- [x] Admin katana assignment
- [x] User banning/unbanning
- [x] Broadcast messaging

### 13. Bot Commands (Handlers)
- [x] User commands: /start, /help, /профиль, /баланс, /топ, /Daily, /гейм, /дуель, / katana, /предсказание, /digest, etc.
- [x] Event handlers: new member, left member, message reactions
- [x] Callback handlers: button presses (duel, katana upgrade, boss fight, etc.)

### 14. Data Persistence (MongoDB)
- [x] Collections: users, achievements_def, user_achievements, transactions, tickets, bank, bosses?, etc.
- [x] Indexes and TTL settings
- [x] Connection handling and error resilience

## Progress Tracking
Each mechanic will be checked by:
1. Verifying constants/configuration match reserve
2. Verifying service/logic implementation
3. Ensuring no syntax/import errors
4. (Optional) Running a quick functional test if feasible

## Notes
- Reserve bot location: C:\senseirezerv
- Current project location: C:\sensei
- After each check, update the checkbox and add a brief note.