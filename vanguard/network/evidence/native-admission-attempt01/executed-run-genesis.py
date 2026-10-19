#!/usr/bin/env python3
"""One offline, clean-source genesis-helper attempt under the local slot grant.

No daemon, database, wallet, networking, shared-source write or dependency fetch.
See native/README.md for the narrower claim this executable can establish.
Docker options: https://docs.docker.com/reference/cli/docker/container/run/
Object export: https://git-scm.com/docs/git-archive
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import sys
import time

import network

BASE = Path('<repo>/build/vanguard-src')
RUST = Path('~/.rustup/toolchains/stable-x86_64-unknown-linux-gnu')
LOCK = Path('/tmp/meownero-swarm-20260912-heavy.lock')
LOCK_ID = (66306, 657237)  # Platform's host inode, not an API-container /tmp.
DOCKER = ['docker', '--host', 'unix:///var/run/docker.sock']
NATIVE = {'cmake', 'make', 'gmake', 'ninja', 'cargo', 'rustc', 'cc1', 'cc1plus',
          'gcc', 'g++', 'clang', 'clang++', 'ld', 'ld.lld', 'monerod',
          'monero-wallet-rpc', 'monero-wallet-cli', 'vanguard_network_genesis'}


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def run(argv, *, deadline, **kwargs):
    remaining = deadline - time.monotonic()
    network.require(remaining > 0, 'attempt deadline exhausted')
    return subprocess.run(argv, timeout=remaining, check=True, **kwargs)


def admission(image):
    available = int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines()
                         if line.startswith('MemAvailable:'))) * 1024
    processes = []
    for proc in Path('/proc').iterdir():
        if proc.name.isdigit():
            try:
                comm = (proc / 'comm').read_text().strip()
                if comm in NATIVE:
                    processes.append({'pid': int(proc.name), 'comm': comm})
            except (FileNotFoundError, ProcessLookupError):
                pass
    ids = subprocess.check_output(DOCKER + ['ps', '-q'], text=True, timeout=10).split()
    collisions = []
    if ids:
        rows = json.loads(subprocess.check_output(DOCKER + ['inspect', *ids], text=True, timeout=10))
        for row in rows:
            command = ' '.join([row.get('Path', ''), *row.get('Args', [])]).lower()
            if row['Image'] == image or any(word in command for word in
                                            ('monerod', 'monero-wallet', 'vanguard', 'cmake', 'cargo', 'rustc')):
                collisions.append({'id': row['Id'], 'name': row['Name']})
    return {'available_memory_bytes': available, 'free_disk_bytes': shutil.disk_usage(BASE).free,
            'native_processes': processes, 'native_containers': collisions}


def require_admission(observed):
    network.require(observed['available_memory_bytes'] >= 5 * 1024**3, 'requires 5 GiB available memory')
    network.require(observed['free_disk_bytes'] >= 5 * 1024**3, 'requires 5 GiB free disk')
    network.require(not observed['native_processes'] and not observed['native_containers'],
                    'native workload collision; no workloads were stopped')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    out = network.fresh_directory(args.out)
    receipt = {'schema': 'meownero-vanguard-genesis-attempt/1', 'result': 'NOT_STARTED',
               'launch_ready': False, 'native_recipe': 'NOT_RUN', 'testnet_admission': 'NOT_RUN',
               'slot_comment': '2d70177d-b7a7-4ef6-8079-242320bdcb1f',
               'candidate_commit': subprocess.check_output(
                   ['git', '-C', str(network.ROOT), 'rev-parse', 'HEAD'], text=True).strip(),
               'driver_sha256': digest(Path(__file__)), 'limits': {'wall_seconds': 900,
                   'execution_seconds': 880, 'cleanup_reserve_seconds': 20,
                   'cpus': 2, 'memory_bytes': 4 * 1024**3, 'swap_bytes': 0, 'pids': 256,
                   'compile_jobs': 1, 'network': 'none', 'published_ports': []}}
    lock = None
    container_id = None
    began = time.monotonic()
    deadline = began + 880

    def interrupted(signum, frame):
        raise RuntimeError('host supervision interrupted by signal ' + str(signum))

    for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(signum, interrupted)
    try:
        # Do not create, truncate, unlink, replace, or silently use another inode.
        lock = os.open(LOCK, os.O_RDWR | os.O_NOFOLLOW)
        info = os.fstat(lock)
        network.require(stat.S_ISREG(info.st_mode) and (info.st_dev, info.st_ino) == LOCK_ID and
                        info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o600,
                        'host heavy-lock identity/owner/mode differs from slot grant')
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        receipt['lock'] = {'device': info.st_dev, 'inode': info.st_ino, 'nonblocking': True}
        pin = network.read_json(network.HERE.parent / 'source-lock.json')
        image = pin['builder']['image_id']
        receipt['admission'] = admission(image)
        require_admission(receipt['admission'])
        image_row = json.loads(subprocess.check_output(DOCKER + ['image', 'inspect', image],
                                                       text=True, timeout=10))[0]
        network.require(image_row['Id'] == image and image_row['Architecture'] == 'amd64' and
                        image_row['Os'] == 'linux', 'builder image mismatch')
        value = network.profile()
        network.checked_source(BASE / 'monero-fcmp')
        receipt.update(profile_sha256=network.profile_hash(value), upstream_commit=pin['upstream']['commit'],
                       source_lock_sha256=digest(network.HERE.parent / 'source-lock.json'), builder_image=image)
        rustc = subprocess.check_output([str(RUST / 'bin/rustc'), '-V'], text=True, timeout=10).strip()
        network.require(rustc == pin['builder']['rustc'], 'Rust toolchain mismatch')
        receipt['rustc'] = rustc
        receipt['archives'] = {}
        source = out / 'source'
        source.mkdir()
        # git archive reads committed objects, excluding the dirty cached test CMake
        # and all generated build objects. Each submodule is exported separately.
        for name, revision in [('', pin['upstream']['commit']), *pin['upstream']['submodules'].items()]:
            archive = out / ('source-' + (name.replace('/', '-') or 'root') + '.tar')
            repo = BASE / 'monero-fcmp' / name
            env = dict(os.environ, GIT_NO_LAZY_FETCH='1')
            run(['git', '-C', str(repo), 'archive', '--format=tar', '-o', str(archive), revision],
                deadline=deadline, env=env)
            receipt['archives'][name or '.'] = {'revision': revision, 'sha256': digest(archive)}
            destination = source / name
            destination.mkdir(parents=True, exist_ok=True)
            run(['tar', '-xf', str(archive), '-C', str(destination)], deadline=deadline)
        receipt['clean_source'] = {name: digest(source / name)
                                   for name in network.read_json(network.HERE / 'source-bindings.json')['files']}
        # archive can honor export-subst. Require the consensus/source-bound files
        # to remain byte-identical to the checked originals before adding our target.
        network.require(receipt['clean_source'] == network.read_json(
            network.HERE / 'source-bindings.json')['files'], 'export altered bound native source')
        target = source / 'tests/vanguard-network'
        shutil.copytree(network.HERE / 'native', target)
        cmake = source / 'tests/CMakeLists.txt'
        receipt['tests_cmake_original_sha256'] = digest(cmake)
        with cmake.open('a') as stream:
            stream.write('\nadd_subdirectory(vanguard-network)\n')
        receipt['tests_cmake_changed_sha256'] = digest(cmake)
        receipt['helper_sources'] = {name: digest(target / name) for name in ('CMakeLists.txt', 'genesis.cpp')}
        cargo = out / 'cargo-home'
        cargo.mkdir()
        # No shared cache writes, hardlinks, credentials/config, or cached targets.
        for name in ('registry', 'git'):
            shutil.copytree(BASE / 'cargo-home' / name, cargo / name)
        receipt['cargo_cache_files'] = {str(path.relative_to(cargo)): digest(path)
                                       for path in sorted(cargo.rglob('*')) if path.is_file()}
        receipt['cargo_checkout_heads'] = {}
        for path in sorted((cargo / 'git/checkouts').glob('*/*')):
            if (path / '.git').exists():
                revision = subprocess.check_output(['git', '-C', str(path), 'rev-parse', 'HEAD'],
                                                   text=True, timeout=10).strip()
                receipt['cargo_checkout_heads'][str(path.relative_to(cargo))] = revision
        for key in ('monero_oxide_rev', 'crypto_bigint_rev'):
            network.require(pin['rust'][key] in receipt['cargo_checkout_heads'].values(),
                            'pinned Rust Git checkout missing: ' + key)
        receipt['admission_before_create'] = admission(image)
        require_admission(receipt['admission_before_create'])
        script = '''set -eu
trap 'cat /sys/fs/cgroup/memory.peak > /out/memory.peak; cat /sys/fs/cgroup/memory.events > /out/memory.events; cat /sys/fs/cgroup/cpu.stat > /out/cpu.stat' EXIT
rustc -V > /out/container-rustc.txt
cargo -V > /out/container-cargo.txt
cmake --version > /out/container-cmake.txt
g++ --version > /out/container-gxx.txt
cmake -S /src -B /src/build/network -D CMAKE_BUILD_TYPE=Release -D ARCH=default -D BUILD_TESTS=ON -D USE_DEVICE_TREZOR=OFF -D MANUAL_SUBMODULES=ON > /out/cmake.log 2>&1
cmake --build /src/build/network --target vanguard_network_genesis --parallel 1 > /out/make.log 2>&1
/src/build/network/tests/vanguard-network/vanguard_network_genesis > /out/recipe1.json 2> /out/recipe1.stderr.log
/src/build/network/tests/vanguard-network/vanguard_network_genesis > /out/recipe2.json 2> /out/recipe2.stderr.log
cmp /out/recipe1.json /out/recipe2.json
sha256sum /src/build/network/tests/vanguard-network/vanguard_network_genesis > /out/binary.sha256
'''
        (out / 'build.sh').write_text(script)
        name = 'tjs2504-genesis-' + out.name.lower()
        command = DOCKER + ['create', '--name', name, '--cidfile', str(out / 'container.cid'),
            '--label', 'meownero.task=TJS-2504',
            '--pull=never', '--network=none', '--cap-drop=ALL', '--security-opt=no-new-privileges',
            '--cpus=2', '--memory=4g', '--memory-swap=4g', '--pids-limit=256', '--ulimit', 'core=0',
            '-u', f'{os.getuid()}:{os.getgid()}', '-v', f'{source}:/src', '-v', f'{cargo}:/cargo-home',
            '-v', f'{RUST}:/opt/rust:ro', '-v', f'{out}:/out', '-e', 'CARGO_HOME=/cargo-home',
            '-e', 'CARGO_NET_OFFLINE=true', '-e', 'CARGO_BUILD_JOBS=1',
            '-e', 'PATH=/opt/rust/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
            '-w', '/src', image, 'bash', '/out/build.sh']
        receipt['create_argv'] = command
        container_id = run(command, deadline=deadline, capture_output=True, text=True).stdout.strip()
        network.require(re.fullmatch('[0-9a-f]{64}', container_id),
                        'invalid owned container ID')
        receipt['container_id'] = container_id
        receipt['result'] = 'RUNNING'
        network.write_json(out / 'receipt.json', receipt)
        with (out / 'docker.log').open('w') as log:
            completed = run(DOCKER + ['start', '-a', container_id], deadline=deadline,
                            stdout=log, stderr=subprocess.STDOUT)
        receipt['native_recipe'] = json.loads((out / 'recipe1.json').read_text())['result']
        network.require((out / 'recipe1.json').read_bytes() == (out / 'recipe2.json').read_bytes(),
                        'native recipe outputs differ')
        receipt['result'] = 'PASS_NATIVE_RECIPE_HELPERS_ONLY'
    except (Exception, KeyboardInterrupt) as error:
        receipt['result'] = 'FAILED_BOUNDED_ATTEMPT'
        receipt['error'] = type(error).__name__ + ': ' + str(error)
    finally:
        for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            signal.signal(signum, signal.SIG_IGN)
        # cidfile also identifies our exact container if create was interrupted
        # after the daemon created it but before the CLI returned its stdout.
        if not container_id and (out / 'container.cid').exists():
            container_id = (out / 'container.cid').read_text().strip()
        # Stop/remove only the ID actually returned for this attempt, while still
        # holding the same host lock. Never find-and-kill by image or task prefix.
        if container_id and re.fullmatch('[0-9a-f]{64}', container_id):
            rows = subprocess.run(DOCKER + ['inspect', container_id], capture_output=True, text=True, timeout=5)
            if rows.returncode == 0:
                row = json.loads(rows.stdout)[0]
                receipt['container_state_before_cleanup'] = row['State']
                if row['State']['Running']:
                    subprocess.run(DOCKER + ['kill', container_id], capture_output=True, timeout=5)
                removed = subprocess.run(DOCKER + ['rm', '-f', container_id], capture_output=True, timeout=5)
                receipt['cleanup_exit'] = removed.returncode
            probe = subprocess.run(DOCKER + ['inspect', container_id], capture_output=True, text=True, timeout=5)
            receipt['cleanup_probe_exit'] = probe.returncode
            receipt['cleanup_probe_stderr'] = probe.stderr
            receipt['container_absent'] = probe.returncode != 0 and 'no such' in probe.stderr.lower()
        # Recheck read-only source pins after the workload, not just before it.
        try:
            network.checked_source(BASE / 'monero-fcmp')
            receipt['shared_source_recheck'] = 'PASS_PINNED_SOURCE_PATHS'
        except Exception as error:
            receipt['shared_source_recheck'] = str(error)
        receipt['wall_seconds'] = round(time.monotonic() - began, 3)
        network.write_json(out / 'receipt.json', receipt)
        if lock is not None:
            os.close(lock)
    print(json.dumps(receipt, indent=2))
    return 0 if receipt['result'] == 'PASS_NATIVE_RECIPE_HELPERS_ONLY' else 1


if __name__ == '__main__':
    sys.exit(main())
