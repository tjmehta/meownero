#!/usr/bin/env python3
"""Build a fresh native x64 tester with an owned bounded offline compiler."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time
import uuid

from docker_support import cleanup_build, cleanup_signals, proof, query, save as save_receipt
from host_capacity import admit, local_endpoint

ROOT = Path(__file__).resolve().parents[1]
GIB = 1024**3


def bindings(context):
    result = {}
    for path in sorted(context.rglob('*')):
        assert not path.is_symlink(), 'frozen context contains a symlink'
        if path.is_file():
            result[str(path.relative_to(context))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def freeze(context):
    files = [ROOT / name for name in ('source-lock.json', 'portable_licenses.py', 'package-portable.py', 'portable-tester.py')]
    files += [p for p in (ROOT / 'licenses').rglob('*') if p.is_file() or p.is_symlink()]
    files += [p for p in (ROOT / 'docker').iterdir() if p.is_file() or p.is_symlink()]
    files += [ROOT.parent / 'docs' / name for name in ('vanguard-portable-tester.md', 'vanguard-docker-tester.md')]
    expected = {}
    for path in files:
        assert not any(p.is_symlink() for p in (path, *path.parents)), 'source symlink refused'
        assert path.is_file() and path.suffix != '.pyc'
        relative = path.relative_to(ROOT.parent)
        expected[str(relative)] = hashlib.sha256(path.read_bytes()).hexdigest()
        target = context / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        target.chmod(0o444)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected[str(relative)], 'source changed during freeze'
    assert bindings(context) == expected, 'copied context differs from source binding'
    return expected


def verify_context(context, expected):
    assert bindings(context) == expected, 'frozen context changed'
    inputs = json.loads((context / 'vanguard/docker/inputs.json').read_text())
    recipe = (context / 'vanguard/docker/Dockerfile').read_text()
    assert recipe.count('FROM ' + inputs['base'] + ' AS ') == 2
    assert recipe.count(inputs['apt_snapshot']) == 2
    assert inputs['ca_bootstrap']['sha256'] in recipe
    assert inputs['ca_bootstrap']['package'] + '=' + inputs['ca_bootstrap']['version'] in recipe
    return inputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.absolute()
    assert out.parent.is_dir() and not out.exists()
    assert not any(p.is_symlink() for p in (out, *out.parents))
    assert shutil.disk_usage(out.parent).free >= 10 * GIB
    assert os.uname().machine == 'x86_64'
    local_endpoint()  # Refuse remote contexts before any Docker work.
    client_memory = int(next(row.split()[1] for row in Path('/proc/meminfo').read_text().splitlines() if row.startswith('MemAvailable:'))) * 1024
    assert client_memory >= 5 * GIB, 'requires five GiB available client memory'
    out.mkdir(mode=0o700)
    invocation = uuid.uuid4().hex
    name = 'meownero-tjs1882-build-' + invocation
    fetched = 'meownero-tjs1882-fetched:' + invocation
    tag = 'meownero-tjs1882-tester:' + invocation
    receipt = {'schema': 'meownero-docker-build-attempt/2', 'invocation': invocation,
               'result': 'INCOMPLETE', 'commands': [], 'cleanup': [], 'client_available_bytes': client_memory,
               'source_sha256': {}, 'images': {}, 'lock_closed': False}
    context = out / 'context'
    descriptor = None
    fetched_id = None
    def save():
        save_receipt(out / 'build.json', receipt)
    def run(label, argv, seconds):
        row = {'label': label, 'exit': None}
        receipt['commands'].append(row)
        save()
        started = time.monotonic()
        with (out / (label + '.log')).open('wb') as stream:
            child = subprocess.Popen(argv, stdout=stream, stderr=subprocess.STDOUT,
                                     env=dict(os.environ, DOCKER_BUILDKIT='0'), start_new_session=True)
            try:
                row['exit'] = child.wait(timeout=seconds)
            finally:
                with cleanup_signals():
                    try:
                        if child.poll() is None:
                            os.killpg(child.pid, signal.SIGTERM)
                            try:
                                child.wait(timeout=15)
                            except subprocess.TimeoutExpired:
                                os.killpg(child.pid, signal.SIGKILL)
                                child.wait(timeout=15)
                    finally:
                        row['exit'] = child.poll()
                        row['reaped'] = child.poll() is not None
                        row['wall_seconds'] = time.monotonic() - started
                        save()
        assert row['exit'] == 0, label + ' failed; exact log retained'
        print(label, 'PASS', flush=True)
    try:
        save()
        receipt['source_sha256'] = freeze(context)
        pins = verify_context(context, receipt['source_sha256'])
        receipt['inputs'] = pins
        save()
        # Share the established local native workload exclusion inode.
        descriptor = os.open('/tmp/meownero-swarm-20260912-heavy.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        info = os.fstat(descriptor)
        assert info.st_nlink == 1 and info.st_uid == os.getuid()
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Only the small pinned base is fetched before the actual-host witness.
        run('base-pull', ['docker', 'pull', pins['base']], 300)
        admit(pins['base'], invocation, out, receipt, 'before-fetch')
        common = ['docker', 'build', '--force-rm', '--memory=3g', '--memory-swap=3g',
                  '--cpu-period=100000', '--cpu-quota=200000', '--build-arg', 'INVOCATION=' + invocation,
                  '-f', str(context / 'vanguard/docker/Dockerfile')]
        verify_context(context, receipt['source_sha256'])
        run('fetch', [*common, '--target', 'fetched', '-t', fetched, str(context)], 1200)
        fetched_id = query('image', 'inspect', fetched, '--format', '{{.Id}}')
        receipt['images']['fetched'] = fetched_id
        verify_context(context, receipt['source_sha256'])
        admit(pins['base'], invocation, out, receipt, 'before-compile')
        run('compile', ['docker', 'run', '--name', name, '--label', 'meownero.invocation=' + invocation,
             '--pull=never', '--network=none', '--cpus=2', '--memory=3g', '--memory-swap=3g', '--pids-limit=256',
             '--cap-drop=ALL', '--security-opt=no-new-privileges', '--ulimit', 'core=0', fetched_id,
             'timeout', '--signal=TERM', '--kill-after=90', '3600', 'python3', '-B', '/recipe/vanguard/docker/compile.py'], 3720)
        cid = query('inspect', name, '--format', '{{.Id}}')
        proof(cid, 'meownero.invocation', invocation, name=name, image=fetched_id)
        compiled_id = query('commit', cid)
        receipt['images']['compiled'] = compiled_id
        verify_context(context, receipt['source_sha256'])
        run('runtime-image', [*common, '--build-arg', 'COMPILED_IMAGE=' + compiled_id, '--target', 'runtime',
                             '-t', tag, str(context)], 1200)
        receipt['images']['runtime'] = query('image', 'inspect', tag, '--format', '{{.Id}}')
        receipt['result'] = 'BUILT_RUNTIME_UNTESTED'
    except BaseException as error:
        receipt.update(result='FAILED_BUILD_ATTEMPT', failure_type=type(error).__name__)
        raise
    finally:
        with cleanup_signals():
            try:
                receipt['cleanup'] = cleanup_build(invocation, name, fetched_id)
                if any(not row['removed'] for row in receipt['cleanup']):
                    receipt['result'] = 'UNRESOLVED_BUILD_CLEANUP'
            finally:
                try:
                    if descriptor is not None:
                        os.close(descriptor)
                    receipt['lock_closed'] = True
                finally:
                    save()
    assert all(row['removed'] for row in receipt['cleanup']), 'owned build cleanup unresolved; receipt retained'


if __name__ == '__main__':
    def cancelled(signum, frame):
        raise KeyboardInterrupt('owned build cancelled')
    signal.signal(signal.SIGTERM, cancelled)
    signal.signal(signal.SIGINT, cancelled)
    main()
