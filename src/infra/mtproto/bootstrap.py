"""Build an isolated Telethon with the full official layer-233 schema.

Never patch guessed constructor IDs into a layer-222 client. Source code and
schema are pinned; no credentials are used while building. Artifacts are cache,
not Git files. This optional build requires GitHub access, not Telegram access.
"""
import fcntl
import hashlib
import io
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
SCHEMA = Path(__file__).with_name('api-layer233.tl')
SCHEMA_SHA256 = 'c2bbefcaec3285ba46c8af8f429c7012fe5aea253fd16d4be089f91c7c3fa71e'
TELETHON_COMMIT = 'dab6bc4d4fc0c7815f6f19c6f643d9f75d2d930c'
ARCHIVE_SHA256 = 'f119a5dcf73b65fbefbc6caaec744a0a54d6d5756e7e37ca315828e49cbcc98e'
ARCHIVE_URL = f'https://codeload.github.com/LonamiWebs/Telethon/tar.gz/{TELETHON_COMMIT}'
RUNTIME = ROOT / '.cache/mtproto-layer233'
MARKER = SCHEMA_SHA256 + ':' + ARCHIVE_SHA256 + ':message-compat-v1'


def unpack_source(data, destination):
    if hashlib.sha256(data).hexdigest() != ARCHIVE_SHA256:
        raise RuntimeError('MTProto source checksum mismatch')
    prefix = f'Telethon-{TELETHON_COMMIT}/'
    total = 0
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        for entry in archive:
            if not entry.isfile() or not entry.name.startswith(prefix):
                continue
            relative = entry.name[len(prefix):]
            if not (relative.startswith(('telethon/', 'telethon_generator/')) or relative in {'setup.py', 'LICENSE'}):
                continue
            target = (destination / relative).resolve()
            target.relative_to(destination.resolve())
            total += entry.size
            if total > 32 * 1024 * 1024:
                raise RuntimeError('MTProto source exceeds extraction limit')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.extractfile(entry).read())


def prepare_runtime():
    if hashlib.sha256(SCHEMA.read_bytes()).hexdigest() != SCHEMA_SHA256:
        raise RuntimeError('MTProto layer-233 schema checksum mismatch')
    RUNTIME.parent.mkdir(parents=True, exist_ok=True)
    with (RUNTIME.parent / 'mtproto-build.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        marker = RUNTIME / '.ready'
        if marker.is_file() and marker.read_text() == MARKER and (RUNTIME / 'telethon/tl/alltlobjects.py').is_file():
            return RUNTIME
        with urllib.request.urlopen(ARCHIVE_URL, timeout=60) as response:
            data = response.read(2 * 1024 * 1024 + 1)
        if len(data) > 2 * 1024 * 1024:
            raise RuntimeError('MTProto source download exceeds limit')
        scratch = Path(tempfile.mkdtemp(prefix='mtproto-build-', dir=RUNTIME.parent))
        try:
            unpack_source(data, scratch)
            shutil.copyfile(SCHEMA, scratch / 'telethon_generator/data/api.tl')
            subprocess.run([sys.executable, 'setup.py', 'gen', 'tl', 'errors'],
                           cwd=scratch, check=True, timeout=90, capture_output=True)
            # Import in a child process to catch generator/client incompatibility
            # before a live process ever uses the generated namespace.
            subprocess.run([sys.executable, '-c',
                            'from telethon import TelegramClient, types, functions; '
                            'from telethon.tl.alltlobjects import LAYER; '
                            'assert LAYER == 233; assert types.InputMediaWidget; '
                            'assert functions.messages.SetBotWidgetQueryAnswerRequest; '
                            f'import sys; sys.path.insert(0, {str(ROOT)!r}); '
                            'from src.infra.mtproto.compat import adapt_message_constructor; '
                            'import telethon; adapt_message_constructor(telethon); '
                            'from datetime import datetime, timezone; '
                            'from telethon.extensions import BinaryReader; '
                            'raw = next(c for c in types.Message.__mro__ if c.__module__ == "telethon.tl.types"); '
                            'blob = bytes(raw(id=1, peer_id=types.PeerUser(1), date=datetime.now(timezone.utc), message="smoke")); '
                            'decoded = BinaryReader(blob).tgread_object(); assert bytes(decoded) == blob'],
                           cwd=scratch, check=True, timeout=30, capture_output=True)
            (scratch / '.ready').write_text(MARKER)
            if RUNTIME.exists():
                shutil.rmtree(RUNTIME)
            scratch.rename(RUNTIME)
        finally:
            if scratch.exists():
                shutil.rmtree(scratch)
    return RUNTIME


def load_runtime():
    runtime = prepare_runtime()
    if 'telethon' in sys.modules:
        from telethon.tl.alltlobjects import LAYER
        if LAYER != 233 or Path(sys.modules['telethon'].__file__).resolve().parent.parent != runtime:
            raise RuntimeError('Another Telethon runtime is already loaded; restart with the pinned layer-233 runtime')
    else:
        sys.path.insert(0, str(runtime))
    import telethon
    from .compat import adapt_message_constructor
    adapt_message_constructor(telethon)
    return telethon


if __name__ == '__main__':
    print(prepare_runtime())
