"""Read only the already-owned ARM12 worker; never launch or stop a build."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import stat
import subprocess
import time

os.umask(0o077)
ROOT = Path('~/Developer/tjs1882-5df99f48-arm12')
expected = json.loads((ROOT / 'observer12-expected.json').read_text())
worker = expected['worker']
assert os.getuid() == worker['uid'] == 501
assert ROOT.is_dir() and not ROOT.is_symlink() and stat.S_IMODE(ROOT.stat().st_mode) == 0o700
started = datetime.datetime.fromisoformat(expected['worker_observed_utc'])
deadline = started + datetime.timedelta(minutes=90)


def write(name, value):
    target = ROOT / name
    if target.exists():
        info = target.lstat()
        assert stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == os.getuid()
    temporary = ROOT / (name + '.tmp')
    with temporary.open('x') as stream:
        stream.write(json.dumps(value, indent=2) + '\n')
    temporary.replace(target)


def observe():
    now = datetime.datetime.now(datetime.timezone.utc)
    result = {'schema': 'meownero-arm12-detached-observation/1', 'observed_utc': now.isoformat(),
              'observer_pid': os.getpid(), 'observer_uid': os.getuid(), 'worker_pid': worker['pid'],
              'observer_scope': 'READ_ONLY_EXISTING_WORKER_NO_BUILD_OR_CLEANUP_CONTROL', 'compile_timeout_seconds': 3600}
    process = subprocess.run(['ps', '-p', str(worker['pid']), '-o', 'pid=,uid=,command='],
                             capture_output=True, text=True, timeout=10)
    fields = process.stdout.strip().split(None, 2)
    live = process.returncode == 0 and len(fields) == 3
    if live:
        assert int(fields[0]) == worker['pid'] and int(fields[1]) == worker['uid'] and fields[2] == worker['argv'], 'worker identity changed'
    result['exact_worker_present'] = live
    path = ROOT / 'attempt12/build-receipt.json'
    receipt = json.loads(path.read_text())
    assert receipt['target'] == 'windows-aarch64'
    assert receipt['result'] in {'INCOMPLETE', 'FAILED_ATTEMPT', 'BUILT_UNTESTED'}
    result.update(result=receipt['result'], receipt_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                  commands=[{k: row.get(k) for k in ('label', 'exit', 'reaped', 'wall_seconds')} for row in receipt.get('commands', [])],
                  containers=receipt.get('containers', []), binaries=receipt.get('binaries', {}))
    for cid in expected['container_ids']:
        command = subprocess.run(['docker', '--context', 'colima', 'inspect', cid], capture_output=True, text=True, timeout=10)
        if command.returncode == 0:
            container = json.loads(command.stdout)[0]
            assert container['Id'] == cid
            if cid == expected['build_container']['cid']:
                owner = expected['build_container']
                assert container['Name'] == owner['name'] and container['Image'] == owner['image']
                assert container['Config']['Labels']['meownero.invocation'] == owner['invocation']
                policy = container['HostConfig']
                assert policy['Memory'] == policy['MemorySwap'] == 3221225472
                assert policy['NanoCpus'] == 2000000000 and policy['PidsLimit'] == 256 and policy['NetworkMode'] == 'none'
            result.setdefault('container_observations', []).append({'cid': cid, 'present': True, 'running': container['State']['Running']})
        else:
            absent = 'No such object: ' + cid in command.stderr
            result.setdefault('container_observations', []).append({'cid': cid, 'present': False if absent else 'UNKNOWN'})
    terminal = not live or now >= deadline
    if terminal:
        result['observer_terminal_reason'] = 'WORKER_EXIT_OBSERVED' if not live else 'READ_ONLY_OBSERVER_DEADLINE'
        for name in ('build.log', 'build-receipt.json'):
            path = ROOT / 'attempt12' / name
            with path.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            result.setdefault('terminal_files', {})[name] = {'bytes': path.stat().st_size, 'sha256': digest}
        write('observer12-terminal.json', result)
    write('observer12-latest.json', result)
    return terminal


while not observe():
    time.sleep(45)
