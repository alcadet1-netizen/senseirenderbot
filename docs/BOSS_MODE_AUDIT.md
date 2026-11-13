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
- Added ult button, compact battle log, escaped player names, participation rules,
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
- Deadline is persisted and enforced when an attack arrives. There is no durable
  background timer to edit the card/apply escape processing exactly at deadline.
- Combat updates still use a process-local lock and state read/modify/write;
  running multiple attacking instances is not safe. Launch claim and GRAM pool
  reservation are atomic, but this is not a distributed combat rewrite.
- Existing bank coin victory payouts/escape penalties are separate from GRAM.
  They have no new durable settlement worker here; crashes around these paths
  can require reconciliation. Do not claim all monetary outcomes are fully audited.
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
