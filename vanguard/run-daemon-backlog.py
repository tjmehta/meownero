#!/usr/bin/env python3
"""Two finite native backlog trials, using a private pinned source/cache."""
import argparse
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('runner', ROOT / 'vanguard/run-daemon-p2p.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
PIN, IMAGE, sha, output = runner.PIN, runner.IMAGE, runner.sha, runner.output
SOURCES = ['vanguard/source-lock.json', 'vanguard/daemon-p2p.py',
           'vanguard/daemon-load.py', 'vanguard/run-daemon-p2p.py',
           'vanguard/verify-daemon-load.py', 'vanguard/daemon-backlog.py',
           'vanguard/run-daemon-backlog.py', 'vanguard/verify-daemon-backlog.py',
           'vanguard/test-daemon-backlog-refusals.py']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--src', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    src, out = args.src.resolve(), args.out.resolve()
    up = src / 'monero-fcmp'
    if out.exists():
        raise SystemExit('refusing existing evidence directory')
    if output(['git', '-C', str(ROOT), 'status', '--porcelain']):
        raise SystemExit('commit the clean candidate before execution')
    if int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines()
                if line.startswith('MemAvailable:'))) < 5 * 1024**2 or \
            shutil.disk_usage(out.parent).free < 5 * 1024**3:
        raise SystemExit('requires 5 GiB available memory and disk')
    if output(['git', '-C', str(up), 'rev-parse', 'HEAD']) != PIN['upstream']['commit'] or \
            sha(up / PIN['rust']['cargo_lock_path']) != PIN['rust']['cargo_lock_sha256']:
        raise SystemExit('source/lock pin mismatch')
    if output(['git', '-C', str(up), 'diff', '--name-only', 'HEAD']) not in ('', 'tests/CMakeLists.txt'):
        raise SystemExit('unexpected upstream modifications')
    for path, commit in PIN['upstream']['submodules'].items():
        if output(['git', '-C', str(up / path), 'rev-parse', 'HEAD']) != commit or \
                output(['git', '-C', str(up / path), 'status', '--porcelain']):
            raise SystemExit('submodule pin/cleanliness mismatch: ' + path)
    rust = Path(os.environ.get('RUST_TOOLCHAIN_DIR',
                str(Path.home() / '.rustup/toolchains/stable-x86_64-unknown-linux-gnu')))
    if output([str(rust / 'bin/rustc'), '-V']) != PIN['builder']['rustc']:
        raise SystemExit('Rust toolchain mismatch')
    with open('/tmp/meownero-swarm-20260912-heavy.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        out.mkdir(parents=True)
        receipt = {'schema': 'meownero-vanguard-daemon-backlog/1',
                   'candidate_commit': output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD']),
                   'source_sha256': {name: sha(ROOT / name) for name in SOURCES},
                   'upstream_commit': PIN['upstream']['commit'], 'builder_image': IMAGE,
                   'rustc': PIN['builder']['rustc'], 'submodules': PIN['upstream']['submodules'],
                   'cargo_lock_sha256': sha(up / PIN['rust']['cargo_lock_path']),
                   'binary': {}, 'commands': [], 'metrics': {}}
        shutil.copy2(ROOT / 'vanguard/source-lock.json', out / 'source-lock.json')

        def save():
            (out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')

        def container(stage, script, work):
            name = f'vanguard-backlog-{os.getpid()}-{stage}'
            readonly = ':ro' if stage != 'build' else ''
            command = ['docker', 'run', '--rm', '--name', name, '--pull=never',
                '--network=none', '--cap-drop=ALL', '--security-opt=no-new-privileges',
                '--cpus=2', '--memory=4g', '--memory-swap=4g', '--pids-limit=256',
                '--ulimit', 'core=0', '-u', f'{os.getuid()}:{os.getgid()}',
                '-v', f'{up}:/src{readonly}', '-v', f'{src / "cargo-home"}:/cargo-home{readonly}',
                '-v', f'{rust}:/opt/rust:ro', '-v', f'{ROOT / "vanguard"}:/harness:ro',
                '-v', f'{work}:/out', '-e', 'CARGO_HOME=/cargo-home', '-e', 'CARGO_NET_OFFLINE=true',
                '-e', 'PATH=/opt/rust/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
                '-w', '/out', IMAGE, 'bash', '-euc',
                f'trap \'cat /sys/fs/cgroup/memory.peak > /out/{stage}.memory; '
                f'cat /sys/fs/cgroup/memory.events > /out/{stage}.memory-events; '
                f'cat /sys/fs/cgroup/cpu.stat > /out/{stage}.cpu\' EXIT\n' + script]
            receipt['commands'].append(command)
            began = time.monotonic()
            save()
            try:
                with (work / f'{stage}.docker.log').open('w') as log:
                    code = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                          timeout=1800 if stage == 'build' else 1060).returncode
            finally:
                # The exact name is task-owned. Also handles interruption/timeouts.
                subprocess.run(['docker', 'rm', '-f', name], stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
            receipt['metrics'][stage] = {'exit': code, 'wall_seconds': time.monotonic() - began}
            (work / f'{stage}.exit').write_text(str(code) + '\n')
            save()
            if code:
                raise SystemExit(f'{stage} failed; inspect {work}')

        bins = up / 'build/vanguard/bin'
        receipt['build_mode'] = 'cached' if all((bins / b).is_file() for b in
                                               ('monerod', 'monero-wallet-rpc')) else 'rebuilt'
        script = ('sha256sum /src/build/vanguard/bin/monerod /src/build/vanguard/bin/monero-wallet-rpc'
                  if receipt['build_mode'] == 'cached' else
                  'cd /src/build/vanguard\ntimeout 1700 make -j1 daemon wallet_rpc_server > /out/make.log 2>&1')
        container('build', script, out)
        for name in ('monerod', 'monero-wallet-rpc'):
            path = bins / name
            receipt['binary'][name] = {'sha256': sha(path), 'bytes': path.stat().st_size}
        # Known executable bytes are checked before any scenario executes.
        spec = importlib.util.spec_from_file_location('load_verifier', ROOT / 'vanguard/verify-daemon-load.py')
        check = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(check)
        for name, (digest, size) in check.BINARIES.items():
            if receipt['binary'][name] != {'sha256': digest, 'bytes': size}:
                raise SystemExit('pinned executable mismatch: ' + name)
        for number in (1, 2):
            stage = f'run{number}'
            work = out / stage
            work.mkdir()
            container(stage, 'timeout --signal=TERM 1040 python3 -B /harness/daemon-backlog.py', work)
            shutil.rmtree(work / 'private')
        save()
        (out / 'MANIFEST.sha256').write_text(''.join(
            f'{sha(path)}  {path.relative_to(out)}\n' for path in sorted(out.rglob('*'))
            if path.is_file() and 'private' not in path.parts and path.name != 'MANIFEST.sha256'))
        subprocess.run(['python3', '-B', str(ROOT / 'vanguard/verify-daemon-backlog.py'),
                        str(out), '--src', str(src)], check=True)


if __name__ == '__main__':
    main()
