# Katana receipt rendering and load behaviour

Command and profile-confirmation paths use the same presenter when widgets are
enabled. It only renders an already completed result; rendering fallbacks never
call the economy service again. Existing `WIDGETS_ENABLED` and
`WIDGET_ANIMATIONS_ENABLED` settings are honoured. The artwork is bundled locally;
no remote asset request occurs while handling an upgrade.

The animated receipt is delivered as a **ready-made GIF**, not a live render.
`scripts/build_katana_receipt_gifs.py` bakes all 15 models × 2 outcomes
(30 files, 760×290, 40-frame timeline with the final hold) into
`src/widgets/assets/katanas/receipts/`; `--check` (run in the baking
environment — GIF bytes are not portable across Pillow/font builds) fails when
they no longer match the renderer. At notification time `to_upgrade_gif` only picks the file for
`model_index(new_length)` and the outcome, so the animation reaches the chat in
milliseconds instead of queueing behind a multi-second Pillow render. The static
PNG fallback still renders live and keeps the real per-user numbers; GIF frames
render directly at their final resolution, avoiding unnecessary 2× supersampling.

A bundled file cannot know one user's numbers, so its tiles are model-scoped
(level `N/15`, growth direction, level length range, attempt-cost span). The
real values — before → after, paid cost, model and rank — stay in the caption
and in `/katanaresult`, exactly as before. Handle caches are keyed by model and
rendering scale.

The bundled GIF is read off-thread but never takes a render slot — like
`/mykatana`, it must not queue behind other widgets' Pillow work — with a
5-second read deadline. The shared two-slot Pillow semaphore still bounds live
rendering: the PNG fallback waits at most 2 seconds for admission and 10 seconds
to render. If the bundled file is missing, the read or PNG render times out, or
Telegram rejects the media, the presenter falls back to PNG and then to a
truthful text receipt.
A timed-out/cancelled thread keeps its slot until it really finishes. A
deployment with either widget setting disabled will not send the GIF. Network
delivery is not retried on ambiguous failures.

Successful delivery logs `source=bundled`, seconds and byte size. Because the
heavy work moved offline, the old 0.47–0.54 s per-uncached-receipt render cost
no longer sits on the notification path; live Telegram delivery and production
load still need verification after deployment.

Для новых попыток результат сохраняется в профиле в той же транзакции, что списание. `/katanaresult` показывает последнюю сохранённую попытку с временем UTC без повторного улучшения. Старые результаты не реконструируются. Для PNG введён отдельный тайм-аут 10 секунд перед текстовым резервом.
