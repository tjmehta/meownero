#!/usr/bin/env python3
"""Exercise actual package refusals and owned cleanup on its runtime target."""
import argparse
import os
if os.name == 'posix':
    import fcntl
import hashlib
import json
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import importlib.util


def main():
    def cancelled(signum, frame):
        raise RuntimeError('control harness interrupted; stop its owned tester')
    signal.signal(signal.SIGTERM, cancelled)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--translated-macos-x86_64', action='store_true')
    args = parser.parse_args()
    package, out = args.package.resolve(), args.out.resolve()
    windows = os.name == 'nt'
    monerod = 'monerod.exe' if windows else 'monerod'
    assert not out.exists() and out.parent.is_dir()
    out.mkdir(mode=0o700)
    rows = []

    def invoke(root, action='preflight', extra=()):
        translated = ['--translated-macos-x86_64'] if args.translated_macos_x86_64 else []
        return subprocess.run([sys.executable, '-B', str(root / 'tester.py'), action, *translated, *extra],
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
           'aarch64' if arch != 'aarch64' else 'x86_64'), 'wrong architecture')
    refuse('changed-binary', lambda root: (root / 'bin' / monerod).write_bytes(b'changed'), 'package hash mismatch')
    refuse('unlisted-private-file', lambda root: (root / 'wallet.keys').write_text('disposable sentinel'),
           'package file set mismatch')
    refuse('symlink-directory', lambda root: (root / 'linked').symlink_to(out, target_is_directory=True),
           'package symlink refused')
    refuse('hardlink', lambda root: os.link(root / 'bin' / monerod, out / 'extra-hardlink'), 'hard-linked input refused')
    collision = out / 'existing-output'
    collision.mkdir()
    sentinel = collision / 'keep'
    sentinel.write_text('must survive')
    result = invoke(package, 'run', ('--out', str(collision)))
    assert result.returncode != 0 and 'output must be new' in result.stderr and sentinel.read_text() == 'must survive'
    rows.append({'case': 'collision-preservation', 'refused': True, 'sentinel_preserved': True})
    if windows:
        spec = importlib.util.spec_from_file_location('windows_backend', package / 'portable_windows.py')
        backend = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(backend)
        with backend.lock(lambda path: path):
            result = invoke(package)
            assert result.returncode != 0 and 'tester busy' in result.stderr
    else:
        lock = Path(tempfile.gettempdir()) / ('meownero-vanguard-tester-' + str(os.getuid()) + '.lock')
        with lock.open('r+b') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = invoke(package)
            assert result.returncode != 0 and 'tester busy' in result.stderr
    rows.append({'case': 'busy-lock', 'refused': True})
    interruptions = [('cancelled', signal.CTRL_BREAK_EVENT), ('deadline', None)] if windows else [('cancelled', signal.SIGTERM), ('deadline', signal.SIGALRM)]
    for name, interruption in interruptions:
        journey = out / name
        with (out / (name + '.log')).open('wb') as log:
            child = None
            mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGINT}) if not windows else None
            try:
                translated = ['--translated-macos-x86_64'] if args.translated_macos_x86_64 else []
                if windows and name == 'deadline':
                    translated += ['--deadline-seconds', '5']
                child = subprocess.Popen([sys.executable, '-B', str(package / 'tester.py'), 'run', '--out', str(journey), *translated],
                    stdout=log, stderr=subprocess.STDOUT,
                    **({'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP} if windows else {'preexec_fn': lambda: signal.pthread_sigmask(signal.SIG_SETMASK, mask)}))
                if not windows:
                    signal.pthread_sigmask(signal.SIG_SETMASK, mask)
                end = time.monotonic() + 60
                fixture = journey / ('private/daemon.log' if windows and name == 'deadline' else 'private/sender.log')
                while not fixture.exists() and child.poll() is None and time.monotonic() < end:
                    time.sleep(0.1)
                assert child.poll() is None and fixture.exists(), 'no live native interruption fixture'
                if interruption is not None:
                    child.send_signal(interruption)
                assert child.wait(timeout=120 if windows and interruption is None else 60) != 0, 'interrupted attempt passed'
            finally:
                if not windows:
                    signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGINT})
                if child is not None and child.poll() is None:
                    child.terminate()
                    try:
                        child.wait(timeout=60)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait(timeout=5)
                if not windows:
                    signal.pthread_sigmask(signal.SIG_SETMASK, mask)
        receipt = json.loads((journey / 'result.json').read_text())
        assert receipt['result'] == 'FAIL_NATIVE_JOURNEY' and receipt['cleanup'] and all(r['removed'] for r in receipt['cleanup'])
        assert not windows or receipt.get('owned_job_cleanup'), 'Windows owned job cleanup not witnessed'
        for row in receipt['cleanup']:
            if windows:
                # Open the recorded PID without creating or signalling anything.
                handle = backend.api(backend.k, 'OpenProcess', backend.W.HANDLE,
                    backend.W.DWORD, backend.W.BOOL, backend.W.DWORD)(0x100000, False, row['pid'])
                if handle:
                    try:
                        assert backend._winapi.WaitForSingleObject(handle, 0) == 0, 'owned process remains'
                    finally:
                        backend.close(handle)
                continue
            try:
                os.kill(row['pid'], 0)
            except ProcessLookupError:
                pass
            else:
                raise AssertionError('owned process remains')
        rows.append({'case': name + '-owned-cleanup', 'signal': ('CTRL_BREAK_EVENT' if windows else interruption.name) if interruption is not None else 'WINDOWS_JOB_TIMER',
                     'removed': True, 'process_count': len(receipt['cleanup'])})
    manifest_hash = hashlib.sha256((package / 'release.json').read_bytes()).hexdigest()
    (out / 'controls.json').write_text(json.dumps({'result': 'PASS_REFUSALS',
        'release_manifest_sha256': manifest_hash, 'cases': rows}, indent=2) + '\n')
    print('PASS_REFUSALS', len(rows))


if __name__ == '__main__':
    main()
