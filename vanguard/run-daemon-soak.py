#!/usr/bin/env python3
"""Run two fresh native 30-minute trials on build-mac using the verified ARM build."""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parent.parent
IMAGE = 'sha256:345b4ccbee39f1231271234eddcc38e9e7c492114744ca21796b517913ee544b'
SOURCES = ('vanguard/source-lock.json', 'vanguard/daemon-p2p.py',
           'vanguard/prepare-soak-build-mac.py', 'vanguard/daemon-soak.py',
           'vanguard/run-daemon-soak.py', 'vanguard/verify-daemon-soak.py',
           'vanguard/test-daemon-soak-refusals.py', 'research/vanguard-soak-tjs1816-protocol-2026-10-08.md')


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def output(argv):
    return subprocess.check_output(argv, text=True).strip()


def manifest(out):
    (out / 'MANIFEST.sha256').write_text(''.join(sha(p) + '  ' + str(p.relative_to(out)) + '\n'
        for p in sorted(out.rglob('*')) if p.is_file() and 'private' not in p.relative_to(out).parts
        and p.name != 'MANIFEST.sha256'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--src', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    src, out = args.src.resolve(), args.out.resolve()
    assert platform.system() == 'Darwin' and platform.machine() == 'arm64'
    assert output(['hostname']).split('.')[0] == 'build-mac', 'heavy work must be on build-mac'
    assert not out.exists(), 'fresh evidence directory required'
    assert not output(['git', '-C', str(ROOT), 'status', '--porcelain']), 'commit clean candidate first'
    pin = json.loads((ROOT / 'vanguard/source-lock.json').read_text())
    build = json.loads((src / 'preparation/receipt.json').read_text())
    assert build['result'] == 'PASS_BUILD' and build['image'] == IMAGE and build['rustc'] == pin['builder']['rustc']
    assert build['upstream_commit'] == pin['upstream']['commit'] and build['submodules'] == pin['upstream']['submodules']
    assert build['cargo_lock_sha256'] == pin['rust']['cargo_lock_sha256']
    up = src / 'monero-fcmp'
    assert output(['git', '-C', str(up), 'rev-parse', 'HEAD']) == pin['upstream']['commit']
    assert not output(['git', '-C', str(up), 'status', '--porcelain', '--untracked-files=no'])
    assert sha(up / pin['rust']['cargo_lock_path']) == pin['rust']['cargo_lock_sha256']
    for path, rev in pin['upstream']['submodules'].items():
        assert output(['git', '-C', str(up / path), 'rev-parse', 'HEAD']) == rev
        assert not output(['git', '-C', str(up / path), 'status', '--porcelain'])
    binary = {name: {'sha256': sha(up / 'build/vanguard/bin' / name),
                     'bytes': (up / 'build/vanguard/bin' / name).stat().st_size}
              for name in ('monerod', 'monero-wallet-rpc')}
    assert binary == build['binary'], 'built executable changed'
    with open('/tmp/meownero-swarm-20260912-heavy.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        out.mkdir(parents=True)
        receipt = {'schema': 'meownero-vanguard-soak/1',
                   'candidate_commit': output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD']),
                   'source_sha256': {name: sha(ROOT / name) for name in SOURCES},
                   'source_lock': pin, 'builder_image': IMAGE, 'architecture': 'linux/arm64',
                   'build_receipt_sha256': sha(src / 'preparation/receipt.json'), 'binary': binary,
                   'started_utc': datetime.now(timezone.utc).isoformat(),
                   'commands': [], 'trials': [], 'result': 'INCOMPLETE'}
        shutil.copytree(src / 'preparation', out / 'preparation')
        shutil.copy2(ROOT / 'vanguard/source-lock.json', out / 'source-lock.json')

        def save():
            (out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')

        began = time.monotonic()
        try:
            for number in (1, 2):
                assert time.monotonic() - began < 7000, 'whole trial runner deadline'
                memory = output(['colima', 'ssh', '--', 'cat', '/proc/meminfo'])
                available = int(next(line.split()[1] for line in memory.splitlines() if line.startswith('MemAvailable:')))
                assert available >= 5 * 1024**2 and shutil.disk_usage(out).free >= 5 * 1024**3
                assert not output(['docker', '--context', 'colima', 'ps', '-q']), 'another container active'
                stage = out / f'run{number}'
                stage.mkdir()
                (stage / 'vm-memory-before.txt').write_text(memory + '\n')
                name = f'tjs1816-soak-{os.getpid()}-{number}'
                script = "trap 'cat /sys/fs/cgroup/memory.peak > /out/final.memory; cat /sys/fs/cgroup/memory.events > /out/final.memory-events; cat /sys/fs/cgroup/cpu.stat > /out/final.cpu' EXIT\n" + \
                         'timeout --signal=TERM 3340 python3 -B /harness/daemon-soak.py'
                argv = ['docker', '--context', 'colima', 'run', '--rm', '--name', name,
                        '--pull=never', '--network=none', '--cap-drop=ALL', '--security-opt=no-new-privileges',
                        '--cpus=2', '--memory=4g', '--memory-swap=4g', '--pids-limit=256', '--ulimit', 'core=0',
                        '-u', f'{os.getuid()}:{os.getgid()}', '-v', f'{up}:/src:ro',
                        '-v', f'{ROOT / "vanguard"}:/harness:ro', '-v', f'{stage}:/out',
                        '-w', '/out', IMAGE, 'bash', '-euc', script]
                receipt['commands'].append(argv)
                row = {'number': number, 'name': name, 'started_utc': datetime.now(timezone.utc).isoformat(), 'status': 'started'}
                receipt['trials'].append(row)
                save()
                trial_began = time.monotonic()
                with (stage / 'docker.stdout.log').open('wb') as stdout, (stage / 'docker.stderr.log').open('wb') as stderr:
                    proc = subprocess.Popen(argv, stdout=stdout, stderr=stderr)
                    try:
                        # Capture the actual running container, excluding secret-bearing env.
                        for _ in range(100):
                            inspected = subprocess.run(['docker', '--context', 'colima', 'inspect', name,
                                '--format', '{{json .Id}}\n{{json .Image}}\n{{json .Platform}}\n{{json .State}}\n{{json .HostConfig}}\n{{json .Mounts}}'], capture_output=True)
                            if inspected.returncode == 0:
                                (stage / 'container-live.jsonl').write_bytes(inspected.stdout)
                                break
                            assert proc.poll() is None, 'container failed to start'
                            time.sleep(0.1)
                        else:
                            raise AssertionError('live container identity unavailable')
                        code = proc.wait(timeout=3380)
                        row['exit'] = code
                        (stage / 'docker.exit').write_text(str(code) + '\n')
                    finally:
                        subprocess.run(['docker', '--context', 'colima', 'stop', '--time=30', name],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        subprocess.run(['docker', '--context', 'colima', 'rm', '-f', name],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        if proc.poll() is None:
                            proc.wait(timeout=40)
                        row['status'] = 'finished'
                        row['wall_seconds'] = time.monotonic() - trial_began
                        row['container_absent'] = subprocess.run(['docker', '--context', 'colima', 'inspect', name],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0
                        save()
                assert code == 0 and row['container_absent'], 'trial failure; preserve raw attempt'
                scenario = json.loads((stage / 'public/result.json').read_text())
                assert scenario['result'] == 'PASS_SCENARIO'
                print('PASS_NATIVE_TRIAL', number, scenario['measured_seconds'], flush=True)
            receipt['result'] = 'PASS_WRITER_TRIALS'
        finally:
            receipt['finished_utc'] = datetime.now(timezone.utc).isoformat()
            receipt['wall_seconds'] = time.monotonic() - began
            save()
            manifest(out)


if __name__ == '__main__':
    main()
