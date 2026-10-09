#!/usr/bin/env python3
"""Run one bounded native cross-host witness on build-mac; provider cleanup is separate."""
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
STAGE = ROOT
BUILD = Path('~/Developer/tjs1816-5a24c6b6/build01')
IMAGE = 'sha256:345b4ccbee39f1231271234eddcc38e9e7c492114744ca21796b517913ee544b'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert platform.system() == 'Darwin' and platform.machine() == 'arm64'
    assert subprocess.check_output(['hostname'], text=True).strip().split('.')[0] == 'build-mac'
    config = json.load(sys.stdin)  # Protected SSH stdin; never record credentials.
    assert config['candidate_commit'] and config['environment']['MEOWNERO_REMOTE_CONTROL_URL'].startswith('https://')
    out = STAGE / 'trial01'
    assert not out.exists(), 'fresh trial required'
    build = json.loads((BUILD / 'preparation/receipt.json').read_text())
    assert build['result'] == 'PASS_BUILD' and build['image'] == IMAGE
    pin = json.loads((ROOT / 'source-lock.json').read_text())
    up = BUILD / 'monero-fcmp'
    assert subprocess.check_output(['git', '-C', str(up), 'rev-parse', 'HEAD'], text=True).strip() == pin['upstream']['commit']
    assert not subprocess.check_output(['git', '-C', str(up), 'status', '--porcelain', '--untracked-files=no'], text=True).strip()
    for path, rev in pin['upstream']['submodules'].items():
        assert subprocess.check_output(['git', '-C', str(up / path), 'rev-parse', 'HEAD'], text=True).strip() == rev
    assert sha(up / pin['rust']['cargo_lock_path']) == pin['rust']['cargo_lock_sha256']
    for name, key in [('monerod', 'MEOWNERO_LOCAL_DAEMON_SHA256'), ('monero-wallet-rpc', 'MEOWNERO_LOCAL_WALLET_SHA256')]:
        assert sha(up / 'build/vanguard/bin' / name) == config['environment'][key] == build['binary'][name]['sha256']
    sources = {name: sha(ROOT / name) for name in ('source-lock.json', 'daemon-p2p.py', 'daemon-cross-host.py', 'run-cross-host-build-mac.py')}
    assert sources == config['source_sha256'], 'candidate source differs'
    with open('/tmp/meownero-swarm-20260912-heavy.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        mem = subprocess.check_output(['colima', 'ssh', '--', 'cat', '/proc/meminfo'], text=True)
        assert int(next(line.split()[1] for line in mem.splitlines() if line.startswith('MemAvailable:'))) >= 5 * 1024**2
        assert shutil.disk_usage(STAGE).free >= 5 * 1024**3
        out.mkdir(mode=0o700)
        name = 'tjs1856-cross-host01'
        script = "trap 'cat /sys/fs/cgroup/memory.peak > /out/final.memory; cat /sys/fs/cgroup/memory.events > /out/final.memory-events; cat /sys/fs/cgroup/cpu.stat > /out/final.cpu' EXIT; timeout --signal=TERM 1580 python3 -B /harness/daemon-cross-host.py"
        args = ['docker', '--context', 'colima', 'run', '--rm', '--name', name, '--pull=never',
                '--network=bridge', '--cap-drop=ALL', '--security-opt=no-new-privileges', '--cpus=2',
                '--memory=4g', '--memory-swap=4g', '--pids-limit=256', '--ulimit', 'core=0',
                '-u', '501:20', '-v', str(up) + ':/src:ro', '-v', str(ROOT) + ':/harness:ro',
                '-v', str(out) + ':/out', '-w', '/out']
        for key in sorted(config['environment']):
            assert key.startswith('MEOWNERO_')
            args += ['-e', key]
        args += [IMAGE, 'bash', '-euc', script]
        receipt = {'scope': 'native ARM local daemon/wallets over real Railway transport',
                   'candidate_commit': config['candidate_commit'], 'source_sha256': sources,
                   'source_pins': pin, 'build_receipt_sha256': sha(BUILD / 'preparation/receipt.json'),
                   'provider_preflight': config['provider_preflight'], 'argv': args,
                   'started_utc': datetime.now(timezone.utc).isoformat(), 'result': 'INCOMPLETE'}
        began = time.monotonic()
        env = {**os.environ, **config['environment']}
        proc = None
        def interrupted(signum, frame):
            raise RuntimeError('owned native host runner interrupted')
        for sig in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, interrupted)
        try:
            with (out / 'docker.stdout.log').open('wb') as stdout, (out / 'docker.stderr.log').open('wb') as stderr:
                proc = subprocess.Popen(args, env=env, stdout=stdout, stderr=stderr)
                for _ in range(100):
                    inspected = subprocess.run(['docker', '--context', 'colima', 'inspect', name,
                        '--format', '{{json .Id}}\n{{json .Image}}\n{{json .Platform}}\n{{json .State}}\n{{json .HostConfig}}\n{{json .Mounts}}'], capture_output=True)
                    if inspected.returncode == 0:
                        (out / 'container-live.jsonl').write_bytes(inspected.stdout)
                        break
                    assert proc.poll() is None
                    time.sleep(0.1)
                else:
                    raise RuntimeError('live native container identity unavailable')
                receipt['exit'] = proc.wait(timeout=1620)
                receipt['result'] = 'NATIVE_DRIVER_COMPLETED' if receipt['exit'] == 0 else 'FAIL_NATIVE_DRIVER'
        finally:
            subprocess.run(['docker', '--context', 'colima', 'stop', '--time=30', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(['docker', '--context', 'colima', 'rm', '-f', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if proc and proc.poll() is None:
                proc.wait(timeout=40)
            receipt['container_absent'] = subprocess.run(['docker', '--context', 'colima', 'inspect', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0
            receipt['wall_seconds'] = time.monotonic() - began
            receipt['finished_utc'] = datetime.now(timezone.utc).isoformat()
            (out / 'host-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
        print(receipt['result'], 'owned container removed:', receipt['container_absent'], flush=True)


if __name__ == '__main__':
    main()
