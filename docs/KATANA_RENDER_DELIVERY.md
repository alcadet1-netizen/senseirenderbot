# Katana receipt rendering and load behaviour

Command and profile-confirmation paths use the same presenter when widgets are
enabled. It only renders an already completed result; rendering fallbacks never
call the economy service again. Existing `WIDGETS_ENABLED` and
`WIDGET_ANIMATIONS_ENABLED` settings are honoured. The artwork is bundled locally;
no remote asset request occurs while handling an upgrade.

The animated receipt is 760×290, keeps its result and actual named model visible,
and no longer includes the schematic-forging line. The static PNG remains
supersampled; GIF frames render directly at their final resolution, avoiding
unnecessary 2× supersampling on every frame. The 40-frame timeline and final
hold are retained. Handle caches are keyed by model and rendering scale.

The shared two-slot Pillow semaphore bounds rendering. Each GIF/PNG attempt waits
at most 2 seconds for admission. GIF rendering has a 20-second deadline; if busy,
timed out or rejected by Telegram, the presenter falls back to PNG and then a
truthful text receipt. A timed-out/cancelled thread keeps its slot until it really
finishes. A deployment with either widget setting disabled will not send the GIF.
Network delivery is not retried on ambiguous failures.

Successful GIF generation logs `version=compact-v3`, seconds and byte size. A
local sample of three uncached receipts took 0.47–0.54 seconds each (around
350–371 KB); this is not a production latency guarantee. Live Telegram delivery
and production load still need verification after deployment.

Для новых попыток результат сохраняется в профиле в той же транзакции, что списание. `/katanaresult` показывает последнюю сохранённую попытку с временем UTC без повторного улучшения. Старые результаты не реконструируются. Для PNG введён отдельный тайм-аут 10 секунд перед текстовым резервом.
