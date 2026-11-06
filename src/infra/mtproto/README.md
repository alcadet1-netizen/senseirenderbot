# Pinned layer-233 protocol runtime

`api-layer233.tl` is the full Telegram API interface schema from the official
Telegram Desktop repository, not a set of hand-written constructor guesses:

https://github.com/telegramdesktop/tdesktop/blob/a6df181ac41763a9ff9edae264dad407fb1c35ec/Telegram/SourceFiles/mtproto/scheme/api.tl

SHA-256: `c2bbefcaec3285ba46c8af8f429c7012fe5aea253fd16d4be089f91c7c3fa71e`.

`bootstrap.py` downloads the pinned MIT-licensed Telethon source + generator from
https://github.com/LonamiWebs/Telethon/tree/dab6bc4d4fc0c7815f6f19c6f643d9f75d2d930c
and checks the archive's SHA-256 before extracting regular files. Telethon's
LICENSE is retained in the generated cache. The complete official schema replaces
Telethon's older API schema; the upstream generator builds both types and
functions, including response and update deserialization. No source monkey
patching, forced layer number on old types, or guessed access_hash is used.

Generated code and build sources live under `.cache/mtproto-layer233`, excluded
from Git. Only this optional runtime imports Telethon. The existing aiogram bot
continues to handle ordinary commands; MTProto authenticates the SAME bot via its
bot token, receives raw widget queries and sends only native widget media/answers.
No phone-based user account, user session export or persistent authorization file
is used. Authorization is in MemorySession and re-established after restart.

Prepare without any Telegram credentials:

```sh
python -m src.infra.mtproto.bootstrap
```

First build requires outbound HTTPS to codeload.github.com. Live operation also
requires Telegram MTProto data-centre connectivity. Build success / offline wire
tests do NOT prove that Telegram permits widget sending by a particular bot.
See `docs/HEDGEHOG_WIDGET.md` for deployment and limits.
