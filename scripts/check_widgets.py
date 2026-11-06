"""Run our HTML through Telegram's actual QuickJS sandbox (Node >=22).

Downloads pinned upstream sources and dev-only npm dependencies into .cache.
Never runs a browser or evaluates widget code in Python/the host JS context.
"""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / '.cache'
UPSTREAM = CACHE / 'widget-sandbox-v0.6.0'
TOOLS = CACHE / 'widget-tools'
COMMIT = 'd6f39f3bc9a126aa418a1ac74825d84d6144183e'  # v0.6.0
DEPS = ['esbuild@0.28.2', 'tsx@4.23.15', 'quickjs-emscripten-core@0.32.0',
        'css-tree@3.2.1', 'linkedom@0.18.13', 'parse5@8.0.0',
        '@jitl/quickjs-ffi-types@0.32.0']


def run(*args):
    subprocess.run(args, cwd=ROOT, check=True)


def main():
    CACHE.mkdir(exist_ok=True)
    if not UPSTREAM.exists():
        run('git', 'clone', '--depth', '1', '--branch', 'v0.6.0',
            'https://github.com/TelegramMessenger/widget-sandbox.git', str(UPSTREAM))
    actual = subprocess.check_output(['git', '-C', str(UPSTREAM), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != COMMIT:
        raise RuntimeError(f'Unexpected sandbox revision {actual}; expected {COMMIT}')
    run('npm', 'install', '--prefix', str(TOOLS), '--no-audit', '--no-fund', *DEPS)
    modules = TOOLS / 'node_modules'
    namespace = modules / '@telegram'
    namespace.mkdir(exist_ok=True)
    links = {namespace / 'widget-sandbox-quickjs': UPSTREAM / 'packages/quickjs-wasm',
             UPSTREAM / 'node_modules': modules}
    for link, target in links.items():
        if link.is_symlink():
            link.unlink()
        if link.exists():
            raise RuntimeError(f'Refusing to replace existing directory {link}')
        link.symlink_to(target, target_is_directory=True)
    run(sys.executable, '-m', 'scripts.widget_samples')
    harness = UPSTREAM / 'packages/core/scripts/sandbox-node.ts'
    runner = CACHE / 'check-sensei-widgets.mts'
    runner.write_text('''import assert from 'node:assert/strict';
import fs from 'node:fs';
import { runWidget } from ''' + json.dumps(str(harness)) + ''';
for (const name of ['profile', 'top', 'katana-success', 'katana-failure']) {
  const html = fs.readFileSync(new URL('./widget-samples/' + name + '.html', import.meta.url), 'utf8');
  for (const theme of ['light', 'dark']) {
    const result = await runWidget(html, { policy: 'strict', theme, script: [
      {probe: "document.getElementById('stats').style.display"},
      {probe: "(document.getElementById('toggle').click(), document.getElementById('stats').style.display)"},
      {probe: "(document.getElementById('toggle').click(), document.getElementById('stats').style.display)"}
    ]});
    assert.deepEqual(result.diags, [], JSON.stringify(result.diags));
    assert.ok(result.renderOps.length > 0);
    assert.equal(result.probes[1], 'none');
    assert.equal(result.probes[2], 'block');
    assert.equal(result.timers, 0);
    assert.ok(result.actions.every(a => a.kind === 'ready'));
    console.log(name + ' / ' + theme + ': strict sandbox, render ops, toggle OK');
  }
}
''', encoding='utf-8')
    run(str(modules / '.bin/tsx'), str(runner))


if __name__ == '__main__':
    main()
