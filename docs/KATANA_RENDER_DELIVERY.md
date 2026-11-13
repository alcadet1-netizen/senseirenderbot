# Katana receipt rendering and load behaviour

Command and profile-confirmation paths use the same presenter when widgets are
enabled. It only renders an already completed result; rendering fallbacks never
call the economy service again. Existing widget/animation settings are honoured.
The artwork is bundled locally; no remote asset request occurs while handling an
upgrade. Five decoded source crops and five resized rigid handles are cached.

The shared two-slot Pillow semaphore still bounds rendering. Each GIF/PNG attempt
waits at most 0.5 seconds for admission. If busy, the presenter falls back to PNG,
then to a truthful text receipt (at most ~1 second total queue wait). Already
running threads are not timed out or abandoned: even cancellation retains the
slot until the rendering thread completes. This bounds render concurrency, not
Telegram request time or the economic service time. Network delivery is not
retried on ambiguous failures by this change.

Successful GIF generation logs `version=reference-v2`, seconds and byte size.
This diagnoses deployment/version issues without assuming Telegram caches the
old file. Local three-uncached-receipt sample: 2.316/2.235/2.132 seconds and about
555 KB per GIF. These are sandbox measurements, not production latency promises.

Full local suite: 672 passed, 52 skipped, 2 xfailed, 2 warnings. No production
load test, deployment or live Telegram delivery verification was performed.
