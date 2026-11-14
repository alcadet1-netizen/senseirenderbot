# Stars purchase origin-message reconciliation

## Cause
The old coinbuy:v1 payload identifies payer/package, not an invoice instance. Group invoices were sent without recording Telegram chat/message IDs. `coin_received` used `message.answer`, so success could not update the source invoice in the group. The supplied production log shows menu/help handling but no pre-checkout or successful-payment event; it is not proof of a completed or failed financial settlement.

## Change
- New invoices use unique `coinbuy:v2:<uid>:<stars>:<24 hex>` payloads backed by MongoDB `star_coin_orders` (primary `_id` index).
- Before exposing payment acceptance, the sent/edited invoice notice is bound to the order. Pre-checkout requires the correct payer, Stars/currency, existing bound order, an available profile and sufficient bank balance.
- Settlement retains the durable charge receipt and snapshot/majority transaction. Order consumption, origin notice snapshot and receipt state are written in that same transaction as the bank-funded Coin transfer. Distinct charges for an already-used order are flagged for refund, never credited twice.
- After settlement, the original personal invoice is edited to success + a humorous thanks, removing its keyboard. The shared group menu is not modified. Receipt delivery marker suppresses already-completed notices.
- An uncertain notice edit does not retry the payment, emit a second group message or classify a settled transfer as failed. The notice remains pending in Mongo; `/donate` reconciles it, even if the receipt was already fulfilled. Repeating an identical edit after an ambiguous success is safe (`message is not modified` counts as delivered).
- Old v1 invoices remain accepted and use their legacy reply location: their original source message cannot safely be reconstructed. No historical money replay or database reset.

## Limitations and release checks
Telegram owns its native payment sheet; the bot can edit its own invoice message, not force-close the native sheet. Deleted/inaccessible origin messages retain pending status for manual support; no speculative group fallback. No live Telegram/Mongo validation was performed. Staging must verify group/topic invoice -> private successful-payment event -> exact group invoice edit; two independent payers; duplicate receipt; competing charges for one order; bank shortage/refund; restart with pending notice; edit timeout and inaccessible message. Private invoice behavior remains editing the selected menu message; older invoice links can still exist and are protected by order/charge validation.
