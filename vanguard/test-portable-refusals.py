#!/usr/bin/env python3
"""Exercise real package refusals and cancellation on its native Linux target."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time


def main():
    def cancelled(signum, frame):
        raise RuntimeError('control harness interrupted; stop its owned tester')
    signal.signal(signal.SIGTERM, cancelled)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    package, out = args.package.resolve(), args.out.resolve()
    assert not out.exists() and out.parent.is_dir()
    out.mkdir(mode=0o700)
    rows = []

    def invoke(root, action='preflight', extra=()):
        return subprocess.run([sys.executable, '-B', str(root / 'tester.py'), action, *extra],
                              capture_output=True, text=True, timeout=60)

    def refuse(name, mutate, reason):
        root = out / name
        shutil.copytree(package, root)
        mutate(root)
        result = invoke(root)
        assert result.returncode != 0 and reason in result.stderr, name + ': ' + result.stderr
        rows.append({'case': name, 'refused': True})

    def change_manifest(root, key, value):
        path = root / 'release.json'
        data = json.loads(path.read_text())
        data[key] = value
        path.write_text(json.dumps(data))

    assert invoke(package).returncode == 0, 'clean native preflight failed'
    refuse('wrong-pin', lambda root: change_manifest(root, 'upstream_commit', '0' * 40), 'wrong source pin')
    arch = json.loads((package / 'release.json').read_text())['architecture']
    refuse('wrong-target', lambda root: change_manifest(root, 'architecture',
           'aarch64' if arch == 'x86_64' else 'x86_64'), 'wrong architecture')
    refuse('changed-binary', lambda root: (root / 'bin/monerod').write_bytes(b'changed'), 'package hash mismatch')
    refuse('unlisted-private-file', lambda root: (root / 'wallet.keys').write_text('disposable sentinel'),
           'package file set mismatch')
    refuse('symlink-directory', lambda root: (root / 'linked').symlink_to(out, target_is_directory=True),
           'package symlink refused')
    refuse('hardlink', lambda root: os.link(root / 'bin/monerod', out / 'extra-hardlink'), 'hard-linked input refused')
    collision = out / 'existing-output'
    collision.mkdir()
    sentinel = collision / 'keep'
    sentinel.write_text('must survive')
    result = invoke(package, 'run', ('--out', str(collision)))
    assert result.returncode != 0 and 'output must be new' in result.stderr and sentinel.read_text() == 'must survive'
    rows.append({'case': 'collision-preservation', 'refused': True, 'sentinel_preserved': True})
    lock = Path(tempfile.gettempdir()) / ('meownero-vanguard-tester-' + str(os.getuid()) + '.lock')
    with lock.open('r+b') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = invoke(package)
        assert result.returncode != 0 and 'tester busy' in result.stderr
    rows.append({'case': 'busy-lock', 'refused': True})
    for name, interruption in [('cancelled', signal.SIGTERM), ('deadline', signal.SIGALRM)]:
        journey = out / name
        with (out / (name + '.log')).open('wb') as log:
            child = None
            mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGINT})
            try:
                child = subprocess.Popen([sys.executable, '-B', str(package / 'tester.py'), 'run', '--out', str(journey)],
                    stdout=log, stderr=subprocess.STDOUT,
                    preexec_fn=lambda: signal.pthread_sigmask(signal.SIG_SETMASK, mask))
                signal.pthread_sigmask(signal.SIG_SETMASK, mask)
                end = time.monotonic() + 60
                while not (journey / 'private/sender.log').exists() and child.poll() is None and time.monotonic() < end:
                    time.sleep(0.1)
                assert child.poll() is None and (journey / 'private/sender.log').exists(), 'no live native interruption fixture'
                child.send_signal(interruption)
                assert child.wait(timeout=60) != 0, 'interrupted attempt passed'
            finally:
                signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGINT})
                if child is not None and child.poll() is None:
                    child.terminate()
                    try:
                        child.wait(timeout=60)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait(timeout=5)
                signal.pthread_sigmask(signal.SIG_SETMASK, mask)
        receipt = json.loads((journey / 'result.json').read_text())
        assert receipt['result'] == 'FAIL_NATIVE_JOURNEY' and receipt['cleanup'] and all(r['removed'] for r in receipt['cleanup'])
        for row in receipt['cleanup']:
            try:
                os.kill(row['pid'], 0)
            except ProcessLookupError:
                pass
            else:
                raise AssertionError('owned process remains')
        rows.append({'case': name + '-owned-cleanup', 'signal': interruption.name,
                     'removed': True, 'process_count': len(receipt['cleanup'])})
    manifest_hash = hashlib.sha256((package / 'release.json').read_bytes()).hexdigest()
    (out / 'controls.json').write_text(json.dumps({'result': 'PASS_REFUSALS',
        'release_manifest_sha256': manifest_hash, 'cases': rows}, indent=2) + '\n')
    print('PASS_REFUSALS', len(rows))


if __name__ == '__main__':
    main()
