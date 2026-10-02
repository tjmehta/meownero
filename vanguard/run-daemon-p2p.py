#!/usr/bin/env python3
"""Build and receipt two native FCMP++ monerod peers over private AF_UNIX P2P."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parent.parent
PIN = json.loads((ROOT / 'vanguard/source-lock.json').read_text())
SOURCES = ['vanguard/daemon-p2p.py', 'vanguard/run-daemon-p2p.py',
           'vanguard/verify-daemon-p2p.py', 'vanguard/source-lock.json']
RESTORE_SOURCES = SOURCES + ['vanguard/daemon-restore.py', 'vanguard/verify-daemon-restore.py']
LOAD_SOURCES = SOURCES + ['vanguard/daemon-load.py', 'vanguard/verify-daemon-load.py']
IMAGE = PIN['builder']['image_id']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def output(args):
    return subprocess.check_output(args, text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--src', type=Path, default=ROOT / 'build/vanguard-src')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--runs', type=int, choices=(1, 2), default=2)
    parser.add_argument('--scenario', choices=('p2p', 'restore', 'load'), default='p2p')
    args = parser.parse_args()
    src, out = args.src.resolve(), args.out.resolve()
    up = src / 'monero-fcmp'
    if out.exists():
        raise SystemExit('refusing existing evidence directory')
    if int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines()
                if line.startswith('MemAvailable:'))) < 5 * 1024**2:
        raise SystemExit('requires 5 GiB available memory')
    if shutil.disk_usage(ROOT).free < 5 * 1024**3:
        raise SystemExit('requires 5 GiB available disk')
    if output(['git', '-C', str(up), 'rev-parse', 'HEAD']) != PIN['upstream']['commit']:
        raise SystemExit('upstream commit mismatch')
    if sha(up / PIN['rust']['cargo_lock_path']) != PIN['rust']['cargo_lock_sha256']:
        raise SystemExit('Cargo.lock mismatch')
    tracked_changes = output(['git', '-C', str(up), 'diff', '--name-only', 'HEAD'])
    if tracked_changes not in ('', 'tests/CMakeLists.txt'):
        raise SystemExit('unexpected tracked upstream change')
    rust = Path(os.environ.get('RUST_TOOLCHAIN_DIR',
                str(Path.home() / '.rustup/toolchains/stable-x86_64-unknown-linux-gnu')))
    if output([str(rust / 'bin/rustc'), '-V']) != PIN['builder']['rustc']:
        raise SystemExit('Rust toolchain mismatch')
    with open('/tmp/meownero-swarm-20260912-heavy.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        out.mkdir(parents=True)
        restore = args.scenario == 'restore'
        load = args.scenario == 'load'
        sources = LOAD_SOURCES if load else RESTORE_SOURCES if restore else SOURCES
        receipt = {'schema': 'meownero-vanguard-daemon-load/1' if load else
                   'meownero-vanguard-daemon-restore/1' if restore else 'meownero-vanguard-daemon-p2p/1',
            'candidate_commit': output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD']),
            'source_sha256': {source: sha(ROOT / source) for source in sources},
            'upstream_commit': PIN['upstream']['commit'], 'builder_image': IMAGE,
            'rustc': PIN['builder']['rustc'], 'binary': {}, 'commands': [], 'metrics': {}}
        shutil.copy2(ROOT / 'vanguard/source-lock.json', out / 'source-lock.json')

        def container(stage, script, work, readonly=False):
            name = f'vanguard-daemon-p2p-{os.getpid()}-{stage}'
            command = ['docker', 'run', '--rm', '--name', name, '--pull=never',
                '--network=none', '--cap-drop=ALL', '--security-opt=no-new-privileges',
                '--cpus=2', '--memory=4g', '--memory-swap=4g', '--pids-limit=256',
                '--ulimit', 'core=0', '-u', f'{os.getuid()}:{os.getgid()}',
                '-v', f'{up}:/src' + (':ro' if readonly else ''),
                '-v', f'{src / "cargo-home"}:/cargo-home' + (':ro' if readonly else ''),
                '-v', f'{rust}:/opt/rust:ro', '-v', f'{ROOT / "vanguard"}:/harness:ro',
                '-v', f'{work}:/out', '-e', 'CARGO_HOME=/cargo-home',
                '-e', 'CARGO_NET_OFFLINE=true',
                '-e', 'PATH=/opt/rust/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
                '-w', '/out', IMAGE, 'bash', '-euc',
                f'trap \'cat /sys/fs/cgroup/memory.peak > /out/{stage}.memory; '
                f'cat /sys/fs/cgroup/memory.events > /out/{stage}.memory-events; '
                f'cat /sys/fs/cgroup/cpu.stat > /out/{stage}.cpu\' EXIT\n' + script]
            receipt['commands'].append(command)
            began = time.monotonic()
            try:
                with (work / f'{stage}.docker.log').open('w') as log:
                    code = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                          timeout=1800 if stage == 'build' else 1200).returncode
            except subprocess.TimeoutExpired:
                code = 124
                subprocess.run(['docker', 'rm', '-f', name], stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
            receipt['metrics'][stage] = {'exit': code, 'wall_seconds': time.monotonic() - began}
            (out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
            if code:
                raise SystemExit(f'{stage} failed; inspect {work}')

        container('build', 'cd /src/build/vanguard\ntimeout 1700 make -j1 daemon wallet_rpc_server > /out/make.log 2>&1',
                  out)
        for binary in ('monerod', 'monero-wallet-rpc'):
            path = up / 'build/vanguard/bin' / binary
            receipt['binary'][binary] = {'sha256': sha(path), 'bytes': path.stat().st_size}
        for number in range(1, args.runs + 1):
            stage = f'run{number}'
            work = out / stage
            work.mkdir()
            script = 'daemon-load.py' if load else 'daemon-restore.py' if restore else 'daemon-p2p.py'
            container(stage, f'timeout 1100 python3 -B /harness/{script}', work, readonly=True)
        (out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
        (out / 'MANIFEST.sha256').write_text(''.join(
            f'{sha(path)}  {path.relative_to(out)}\n' for path in sorted(out.rglob('*'))
            if path.is_file() and 'private' not in path.parts and path.name != 'MANIFEST.sha256'))
        verifier = 'verify-daemon-load.py' if load else 'verify-daemon-restore.py' if restore else 'verify-daemon-p2p.py'
        command = ['python3', '-B', str(ROOT / 'vanguard' / verifier), str(out)]
        if load:
            command += ['--src', str(src)]
        subprocess.run(command, check=True)


if __name__ == '__main__':
    main()
