# /senseiboss audit and changes

## Launch and interface

- Previously /senseiboss ignored its numeric argument and refused group launch.
  `/senseiboss 1` now launches a random configured boss in the invoking group
  for one hour, for a Telegram administrator/creator of that group. Without an
  argument it defaults to one hour; finite positive durations up to 24h accepted.
  Private configuration remains restricted to configured bot administrators.
- The current implementation intentionally has ONE global boss, not one per chat.
  Conditional upsert of canonical boss_state rejects a concurrent active launch.
  No active state is overwritten; after expiry a new launch is permitted.
- Attacks validate the owning chat and callback message, with chat/battle checked
  again under the service lock. Stale buttons do not attack a new battle.
- Added one attack button, unified compact HTML cards, escaped names, participation rules,
  chance-based GRAM wording and disclosure of the existing 100-coin escape penalty.

## GRAM transfers

Old code reset a full pool and attempted transfers with random IDs without a
persistent award record. Now boss_xrocket_rewards stores an award before any
external attempt. Its deterministic 20-character transfer ID derives from battle,
user and event identity. Mongo _id uniqueness rejects a duplicate attempt.

The boss_state gram_reserved counter reserves the configured pool atomically
before calling xRocket, matching the battle start_time. It never resets on an
exhausted drop. xRocket calls have a 12-second total timeout and require explicit
success=true to confirm. Raw provider responses and exception strings are not
logged. Failed/ambiguous outcomes become needs_review, not a successful award.
Reserved budget is not auto-released after ambiguity. Receipts are not deleted.

This is **at-most-one automated attempt**, not guaranteed eventual payout.
A crash between receipt/reservation/call/confirmation can leave prepared/sending
or needs_review records. These require reconciliation with provider records,
not blind retries or budget resets. No automated reconciliation worker or
provider transaction lookup has been added; the stable ID must be retained.
Old in-flight/unrecorded transfers are not reconstructed by this patch.

## Remaining limitations / separate work

- No live xRocket API call, wallet balance check, real transfer, production DB
  access or deployment performed. Mock API tests cannot verify user receipt.
- External network access here does not permit the xRocket API host; current API
  schema/idempotency semantics have not been independently live-verified.
- The runtime checks the persisted deadline every 5 seconds, including after
  restart; outages/Telegram limits can delay the visible update. This is not a
  per-second countdown or an exact-time delivery guarantee.
- Combat updates still use a process-local lock and state read/modify/write;
  running multiple attacking instances is not safe. Launch claim and GRAM pool
  reservation are atomic, but this is not a distributed combat rewrite.
- Coin victory/escape settlement now uses Mongo snapshot/majority transactions
  (replica set required), marked atomically in boss_state with per-user ledger
  IDs. Missing profiles are excluded. Bank-funded win amounts may be reduced to
  available balance. Existing loss policy (-100, including low/negative balances)
  is preserved, not redesigned. Legacy terminal battles without a settlement
  marker are not replayed; old incomplete payouts still need reconciliation.
- Launch publication errors can leave a claimed battle without a bound message;
  inspect/reconcile before restarting, especially after an ambiguous send.
- Current configured boss economics/chances/level and cooldown rules preserved.
  Successful GRAM drop claims require normal hit damage >=20 and player level>=5;
  ult does not enter the drop branch, preserving existing rules.

## Validation

Initial full local run: 782 passed, 52 skipped, 2 xfailed, 2 warnings. Added tests
for explicit xRocket success, ambiguity, duplicate suppression, exhausted pool,
launch claims and escaping. Tests use mocks rather than a live Mongo replica set
or xRocket wallet. See the subsequent full test result in the PR/turn summary.

## UI correction

The boss card now has exactly one button: «⚔️ Атака». Ult is invoked by a text
message «ульта» or /ulta (including addressed Telegram command form). Old
ult_boss callbacks only explain the command; they do not execute an ult.
Targeted boss tests after this correction: 30 passed.


## Unified UI / runtime follow-up

- Shared BossPresenter for editor/live path: full title, HP, shield, actual
  break/weakness state, UTC finish time, participant count/top three, clear rules.
  Removed misleading config-damage line, boxed truncation and duplicate phase /
  victory announcements. One attack button; ult remains a command/text action.
- Final card shows duration, last hit and actual Coin settlement, not an assumed
  reward. GRAM confirmations/review notices remain on individual hit receipts;
  no claim of a complete historical xRocket reconciliation is made.
- Display lock reads latest DB state; active refreshes limited to one per second,
  background checks every 5 seconds, identical content skipped. RetryAfter defers
  until allowed; deleted card is flagged without sending orphan replacements.
- Settlement and its marker commit together. Worker retries after errors/restarts;
  settlement must finish before replacing a marked terminal battle. No monetary
  side effects inside Telegram retries. New launch clears old display/settlement
  metadata. Combat writes exclude gram_reserved to avoid undoing atomic reserves.
- /boss_settings shows reserved budget (not falsely labelled confirmed payout),
  uses correct GRAM currency and valid HTML. /boss_reset_pool no longer claims
  to reset the protected battle reservation. Admin help includes /ulta.
- Test coverage uses rollback-capable fake Mongo transactions, not live Mongo.
  Includes concurrent replay, failed transaction rollback/retry, bank conservation,
  empty bank, legacy/admin stops, expired-card recovery, display deduplication,
  rate limiting, missing cards and protected GRAM reservations.

Final full local run after the UI/runtime follow-up: **825 passed, 52 skipped,
2 xfailed, 2 warnings**. Commands from other chats are not deleted or processed.
No live Telegram/xRocket/production Mongo verification or deployment performed.
