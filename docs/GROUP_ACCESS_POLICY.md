# Group access checks: concurrency and failure policy

Ordinary group/supergroup handling requires the bot to be administrator/creator. Private chats and the existing payment receipt reconciliation order are unchanged.

`GroupAdminAccess` uses an in-process LRU cache bounded to 4096 bot/chat keys. Positive and ordinary negative membership results last 60 seconds; permanent Telegram access denials last 300 seconds. Membership updates invalidate the relevant key. Temporary lookup failures raise to the existing caller on the first check and cache a fail-closed result for 5 seconds to prevent retry storms. This can temporarily suppress handling during an outage; it never grants permission from a failed check.

Concurrent cold-cache checks for the same bot/chat share a lock and recheck the cache after acquiring it. Locks are weakly held and disappear when no request owns or waits on them; unrelated chats do not share a lock. Cancellation propagates and releases the lock.

Each active lock has a generation. A membership invalidation or explicit send denial advances it. A previously started lookup cannot cache or return a positive permission after that generation changes. A later check may perform a fresh lookup. Temporary failures likewise cannot overwrite a newer denial with a shorter backoff.

The cache is a local optimization, not persistent state. No database records are deleted or changed by this policy. Multiple processes have independent caches. Positive rights can still be stale for up to 60 seconds if no membership event arrives; Telegram send errors and membership events remain necessary. The LRU bounds cached results, not the number of live Telegram requests across distinct chats.

Tests cover concurrent bursts, stale lookup/invalidation races, permanent denial, transient backoff/recovery, TTL/LRU eviction and cancellation. These use mocked Telegram calls, not live permission changes. Run `python -m pytest tests/unit/test_group_admin_policy.py -q` with the usual test environment.
