# Referral v2 audit and release notes

## Audit
Existing `/senseireferal` called a stub returning a dict while the presenter expected ReferralStats. Existing registration minted 200/100 Coin and XP without a bank debit, with no transaction or cycle protection. Katana purchases debited/deposited/updated the weapon separately. No historical awards are replayed or clawed back by this change.

## Implemented policy
- New first-start registration only, immutable direct parent, self/cycle rejection. Legacy links remain. Only v2 registrations qualify for the new activation bonus.
- Every paid katana attempt, successful or failed, distributes 10%, 1%, 0.1% to three ancestors. Missing/banned ancestor shares remain in bank. No commission on transfers/rewards. Decimal calculation rounded down to 0.001 Coin; existing balances use the repository's numeric Coin representation (floats). Fractional Coin are credited directly, not accumulated as hidden integer-only balances.
- Debit, weapon outcome/cooldown, bank deposit, commissions and ledger are one snapshot/majority Mongo transaction. Outcome and event ID fixed across transaction retries. Concurrent attempts conflict on purchaser and recheck persisted cooldown. Ledger IDs deterministic within the purchase. No nontransactional fallback.
- Bonus: 100 to inviter, 50 to newcomer, no XP. Three distinct activity days including the paid upgrade day. Reward-enabled message activity records up to three dates. Activation checked on a paid upgrade; at least 150 Coin bank principal required. Short bank leaves bonus pending for next paid upgrade. Activation is transactional and marked once; receipts use user-derived IDs.
- Menu and ad contain real CopyText buttons; ad also has the personalized join URL. Generated ad can be forwarded without inline mode. Choosing another chat uses a personal inline result based solely on query sender identity, cache disabled.
- Network level tabs and income both paginate in pages of 10, fetching 11 to detect a next page. Selected level is highlighted. Income uses date + receipt ID ordering. Unchanged edits are harmless. Coin labels omit trailing zeros and preserve 0.001 precision. Pagination is bounded to page 10000; very large trees should move from offset to cursor pagination. Totals include new tracked earnings, not inferred historical income. No fake top leaderboard in the new menu.

## Release requirements and limitations
MongoDB replica set/sharded deployment with sessions/transactions is mandatory. Startup ensures `users(referrer_id,id)` and `transactions(user_id,tx_type,created_at desc,_id desc)` indexes. Index creation failures fail startup rather than silently serving unindexed traffic. No database reset or migration of money required. No changes applied to production by this coding session.
Enable inline mode in BotFather for Choose chat. Forwarding the generated ad works without it. CopyText requires a Telegram client supporting Bot API copy buttons. A deep link needs the user's Start action; existing profiles are not rebound. Multiple Telegram accounts cannot be reliably attributed to one human.

Manual staging checklist: new user enters via ad; no immediate bonus; parent immutable; three days activity then paid upgrade; exact bank/purchaser/three-parent reconciliation; duplicate callback/concurrent instance; insufficient bank bonus pending; restart; group/private ownership; inline sender isolation; copy/forward on current Telegram clients. Real Mongo rollback/concurrency and Telegram delivery must be verified in staging: unit mocks are not live validation.

The branch also contains the preceding xRocket 403 diagnostic work. This does not use any posted API key, call real transfers or retry old boss awards.


## Follow-up usability and correctness review
- Personal bonus progress displays 0–3 activity days, paid upgrade status, paid/pending explanation; legacy users are not promised a second activation bonus.
- Paid upgrades persist their activity date transactionally, including for users who do not send ordinary chat messages. At most three distinct dates retained.
- Group command opens the private cabinet via `start=referrals_menu`, instead of publishing personal income/network.
- First-start binding is closed before early-return widget routes too. Banned users/bots cannot form new referral bindings.
- Verification includes copy and join buttons, inline sender identity, pagination and escaping, no-op edits, bonus/bank guards, cycle/self/old-profile restrictions, upgrade activity/cooldown, private group entry and startup index declarations.
