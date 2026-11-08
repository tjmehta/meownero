#!/usr/bin/env python3
"""One bounded offline TESTNET admission attempt; no peer, wallet or RPC.

Reuses only the explicitly granted TJS-2504 export/build/Cargo copy. Docker
containment follows run-genesis.py and the platform reply 15414082. No retries.
"""
import argparse
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import tarfile
import time

import network

spec = importlib.util.spec_from_file_location('genesis_driver', Path(__file__).with_name('run-genesis.py'))
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)
REUSE = Path('<agent-scratch>'
             'a8902417-a0b5-43af-942b-72d7f4096bc6/scratch/native-attempt01')
CASES = ('positive', 'positive-reward', 'wrong-height', 'wrong-unlock', 'empty-outputs',
         'wrong-version', 'identity', 'small-order', 'malformed', 'historical-torsion')


def validate_reuse(pin, receipt):
    """Compare every archived source member and copied Cargo input before reuse."""
    # This internal hash-bound telemetry contains a full Cargo input manifest;
    # the public profile reader's 64 KiB limit is intentionally inappropriate.
    network.require(g.digest(REUSE / 'receipt.json') == g.digest(
        network.HERE / 'evidence/native-genesis-attempt01/receipt.json'), 'prior receipt changed')
    with (REUSE / 'receipt.json').open() as stream:
        old = json.load(stream)
    network.require(old['result'] == 'PASS_NATIVE_RECIPE_HELPERS_ONLY', 'prior helper failed')
    network.require(old['source_lock_sha256'] == g.digest(network.HERE.parent / 'source-lock.json') and
                    old['upstream_commit'] == pin['upstream']['commit'] and
                    old['builder_image'] == pin['builder']['image_id'], 'prior source/builder pins differ')
    source = REUSE / 'source'
    verified = {}
    expected_paths = set()
    for name, binding in old['archives'].items():
        archive = REUSE / ('source-' + (name.replace('/', '-') if name != '.' else 'root') + '.tar')
        network.require(g.digest(archive) == binding['sha256'], 'source archive changed: ' + name)
        base = source if name == '.' else source / name
        count = 0
        with tarfile.open(archive) as members:
            for member in members:
                relative = Path(member.name)
                network.require(not relative.is_absolute() and '..' not in relative.parts, 'unsafe archive member')
                path = base / relative
                if member.isfile() or member.issym():
                    expected_paths.add(str(path.relative_to(source)))
                if member.isfile():
                    raw = members.extractfile(member).read()
                    if name == '.' and member.name == 'tests/CMakeLists.txt':
                        raw += b'\nadd_subdirectory(vanguard-network)\n'
                    network.require(not path.is_symlink() and path.read_bytes() == raw,
                                    'export differs from committed object: ' + str(relative))
                    count += 1
                elif member.issym():
                    network.require(path.is_symlink() and os.readlink(path) == member.linkname,
                                    'export symlink differs: ' + str(relative))
        verified[name] = {'revision': binding['revision'], 'archive_sha256': binding['sha256'],
                          'regular_files_verified': count}
    extra_paths = {'tests/vanguard-network/' + name for name in ('CMakeLists.txt', 'README.md', 'genesis.cpp')}
    actual_paths = {str(p.relative_to(source)) for p in source.rglob('*')
                    if (p.is_file() or p.is_symlink()) and not str(p.relative_to(source)).startswith('build/')}
    network.require(actual_paths == expected_paths | extra_paths, 'unexpected or missing exported source paths')
    for name, digest in old['helper_sources'].items():
        network.require(g.digest(source / 'tests/vanguard-network' / name) == digest,
                        'prior helper source changed: ' + name)
    network.require(g.digest(source / 'tests/CMakeLists.txt') == old['tests_cmake_changed_sha256'],
                    'prior target registration changed')
    cargo = REUSE / 'cargo-home'
    for name, digest in old['cargo_cache_files'].items():
        network.require(g.digest(cargo / name) == digest, 'copied Cargo input changed: ' + name)
    for name, revision in old['cargo_checkout_heads'].items():
        actual = subprocess.check_output(['git', '-C', str(cargo / name), 'rev-parse', 'HEAD'],
                                         text=True, timeout=5).strip()
        network.require(actual == revision, 'copied Cargo Git revision differs')
    network.require(g.digest(source / pin['rust']['cargo_lock_path']) == pin['rust']['cargo_lock_sha256'],
                    'owned Cargo.lock changed')
    expected = (REUSE / 'binary.sha256').read_text().split()[0]
    network.require(g.digest(source / 'build/network/tests/vanguard-network/vanguard_network_genesis') == expected,
                    'prior helper binary changed')
    receipt['reuse'] = {'root': str(REUSE), 'prior_receipt_sha256': g.digest(REUSE / 'receipt.json'),
        'archives': verified, 'cargo_files_verified': len(old['cargo_cache_files']),
        'cargo_checkout_heads': old['cargo_checkout_heads'], 'prior_helper_sha256': expected,
        'build_mode': 'INCREMENTAL_TASK_OWNED_BUILD_NOT_CLEAN',
        'prebuild_objects': {str(p.relative_to(source)): g.digest(p)
                            for p in sorted((source / 'build/network').rglob('*'))
                            if p.is_file() and p.suffix in ('.o', '.a')}}
    return source, cargo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    out = network.fresh_directory(args.out)
    began = time.monotonic()
    deadline = began + 880
    receipt = {'schema': 'meownero-vanguard-testnet-admission-attempt/1', 'result': 'NOT_STARTED',
        'launch_ready': False, 'testnet_admission': 'NOT_RUN', 'native_two_peer': 'NOT_RUN',
        'slot_comment': '15414082-2a53-4872-8d19-b87f302f0bae',
        'candidate_commit': subprocess.check_output(['git', '-C', str(network.ROOT), 'rev-parse', 'HEAD'],
                                                   text=True).strip(),
        'driver_sha256': g.digest(Path(__file__)),
        'limits': {'wall_seconds': 900, 'execution_seconds': 880, 'cleanup_reserve_seconds': 20,
                   'cpus': 2, 'memory_bytes': 4 * 1024**3, 'swap_bytes': 0, 'pids': 256,
                   'compile_jobs': 1, 'network': 'none', 'published_ports': []}}
    lock = None
    container = None

    def interrupted(signum, frame):
        raise RuntimeError('host supervision interrupted by signal ' + str(signum))

    for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(signum, interrupted)
    try:
        lock = os.open(g.LOCK, os.O_RDWR | os.O_NOFOLLOW)
        info = os.fstat(lock)
        network.require(stat.S_ISREG(info.st_mode) and (info.st_dev, info.st_ino) == g.LOCK_ID and
                        info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o600,
                        'heavy-lock identity/owner/mode differs from grant')
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        receipt['lock'] = {'device': info.st_dev, 'inode': info.st_ino, 'nonblocking': True}
        pin = network.read_json(network.HERE.parent / 'source-lock.json')
        image = pin['builder']['image_id']
        g.NATIVE.add('vanguard_network_admission')
        receipt['admission'] = dict(g.admission(image), load_average=list(os.getloadavg()), logical_cpus=os.cpu_count())
        g.require_admission(receipt['admission'])
        image_row = json.loads(subprocess.check_output(g.DOCKER + ['image', 'inspect', image],
                                                       text=True, timeout=10))[0]
        network.require(image_row['Id'] == image and image_row['Architecture'] == 'amd64' and
                        image_row['Os'] == 'linux', 'builder image mismatch')
        network.checked_source(g.BASE / 'monero-fcmp')
        rustc = subprocess.check_output([str(g.RUST / 'bin/rustc'), '-V'], text=True, timeout=5).strip()
        network.require(rustc == pin['builder']['rustc'], 'Rust toolchain mismatch')
        receipt.update(source_lock_sha256=g.digest(network.HERE.parent / 'source-lock.json'),
                       profile_sha256=network.profile_hash(network.profile()), upstream_commit=pin['upstream']['commit'],
                       builder_image=image, rustc=rustc)
        source, cargo = validate_reuse(pin, receipt)
        overlay = network.admission_overlay(g.BASE / 'monero-fcmp', out / 'overlay', network.profile())
        frozen = network.read_json(network.HERE / 'evidence/native-genesis-attempt01/admission-overlay/admission-overlay.json')
        network.require(overlay == frozen, 'prepared overlay differs from committed boundary')
        patch = out / 'overlay/testnet-admission-prerequisite.patch'
        g.run(['git', 'apply', '--check', str(patch)], cwd=source, deadline=deadline)
        g.run(['git', 'apply', str(patch)], cwd=source, deadline=deadline)
        receipt['overlay'] = overlay
        for name, binding in overlay['files'].items():
            network.require(g.digest(source / name) == binding['changed_sha256'], 'applied overlay hash mismatch')
        target = source / 'tests/vanguard-network'
        for name in ('CMakeLists.txt', 'admission.cpp'):
            (target / name).write_bytes((network.HERE / 'native' / name).read_bytes())
        receipt['witness_sources'] = {name: g.digest(target / name) for name in ('CMakeLists.txt', 'admission.cpp')}
        for name in ('run-admission.py', 'run-genesis.py', 'network.py', 'profile.json'):
            (out / ('executed-' + name)).write_bytes((network.HERE / name).read_bytes())
        script = '''set -eu
trap 'cat /sys/fs/cgroup/memory.peak > /out/memory.peak; cat /sys/fs/cgroup/memory.events > /out/memory.events; cat /sys/fs/cgroup/cpu.stat > /out/cpu.stat' EXIT
rustc -V > /out/container-rustc.txt
cargo -V > /out/container-cargo.txt
cmake --version > /out/container-cmake.txt
g++ --version > /out/container-gxx.txt
cmake -S /src -B /src/build/network -D CMAKE_BUILD_TYPE=Release -D ARCH=default -D BUILD_TESTS=ON -D USE_DEVICE_TREZOR=OFF -D MANUAL_SUBMODULES=ON > /out/cmake.log 2>&1
cmake --build /src/build/network --target vanguard_network_admission --parallel 1 > /out/make.log 2>&1
sha256sum /src/build/network/tests/vanguard-network/vanguard_network_admission > /out/binary.sha256
'''
        for case in CASES:
            script += (f'status=0\ntimeout 45 /src/build/network/tests/vanguard-network/vanguard_network_admission '
                       f'/out/db-{case} {case} > /out/{case}.stdout.log 2> /out/{case}.stderr.log || status=$?\n'
                       f'echo "$status" > /out/{case}.exit\n')
        (out / 'build.sh').write_text(script)
        receipt['admission_before_create'] = dict(g.admission(image), load_average=list(os.getloadavg()))
        g.require_admission(receipt['admission_before_create'])
        command = g.DOCKER + ['create', '--name', 'tjs2504-admission-' + out.name.lower(),
            '--cidfile', str(out / 'container.cid'), '--label', 'meownero.task=TJS-2504',
            '--pull=never', '--network=none', '--cap-drop=ALL', '--security-opt=no-new-privileges',
            '--cpus=2', '--memory=4g', '--memory-swap=4g', '--pids-limit=256', '--ulimit', 'core=0',
            '-u', f'{os.getuid()}:{os.getgid()}', '-v', f'{source}:/src', '-v', f'{cargo}:/cargo-home',
            '-v', f'{g.RUST}:/opt/rust:ro', '-v', f'{out}:/out', '-e', 'CARGO_HOME=/cargo-home',
            '-e', 'CARGO_NET_OFFLINE=true', '-e', 'CARGO_BUILD_JOBS=1',
            '-e', 'PATH=/opt/rust/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
            '-w', '/src', image, 'bash', '/out/build.sh']
        receipt['create_argv'] = command
        container = g.run(command, deadline=deadline, capture_output=True, text=True).stdout.strip()
        network.require(re.fullmatch('[0-9a-f]{64}', container), 'invalid owned container ID')
        receipt['container_id'] = container
        row = json.loads(subprocess.check_output(g.DOCKER + ['inspect', container], text=True, timeout=5))[0]
        receipt['containment'] = {k: row[k] for k in ('HostConfig', 'Mounts', 'Config')}
        receipt['result'] = 'RUNNING'
        network.write_json(out / 'receipt.json', receipt)
        with (out / 'docker.log').open('w') as log:
            g.run(g.DOCKER + ['start', '-a', container], deadline=deadline, stdout=log, stderr=subprocess.STDOUT)
        results = {}
        for case in CASES:
            status = int((out / (case + '.exit')).read_text())
            rows = (out / (case + '.stdout.log')).read_text().splitlines()
            results[case] = {'exit': status, 'result': next((json.loads(line) for line in reversed(rows)
                                                          if line.startswith('{')), None)}
        receipt['cases'] = results
        if results['positive']['exit'] == 0:
            positive = results['positive']['result']
            network.require(positive and positive['result'] == 'PASS_NATIVE_TESTNET_GENESIS_ONLY', 'positive receipt missing')
            recipe = network.read_json(network.HERE / 'evidence/native-genesis-attempt01/recipe1.json')
            network.require(positive['fresh']['genesis_block_hex'] == recipe['genesis_block_hex'], 'stored genesis blob differs')
            receipt['testnet_admission'] = 'PASS_NATIVE_TESTNET_GENESIS_ONLY'
        network.require(all(row['exit'] == 0 and row['result'] for row in results.values()), 'native witness cases failed')
        receipt['result'] = 'PASS_NATIVE_TESTNET_GENESIS_AND_CONTROLS_ONLY'
    except (Exception, KeyboardInterrupt) as error:
        receipt['result'] = 'FAILED_BOUNDED_ATTEMPT'
        receipt['error'] = type(error).__name__ + ': ' + str(error)
    finally:
        for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            signal.signal(signum, signal.SIG_IGN)
        if not container and (out / 'container.cid').exists():
            container = (out / 'container.cid').read_text().strip()
        try:
            if container and re.fullmatch('[0-9a-f]{64}', container):
                rows = subprocess.run(g.DOCKER + ['inspect', container], capture_output=True, text=True, timeout=4)
                if rows.returncode == 0:
                    row = json.loads(rows.stdout)[0]
                    receipt['container_state_before_cleanup'] = row['State']
                    if row['State']['Running']:
                        subprocess.run(g.DOCKER + ['kill', container], capture_output=True, timeout=4)
                    removed = subprocess.run(g.DOCKER + ['rm', '-f', container], capture_output=True, timeout=4)
                    receipt['cleanup_exit'] = removed.returncode
                probe = subprocess.run(g.DOCKER + ['inspect', container], capture_output=True, text=True, timeout=4)
                receipt['cleanup_probe'] = {'exit': probe.returncode, 'stderr': probe.stderr}
                receipt['container_absent'] = probe.returncode != 0 and 'no such' in probe.stderr.lower()
                network.require(receipt['container_absent'], 'owned container removal unconfirmed')
        except Exception as error:
            receipt['cleanup_error'] = str(error)
            receipt['result'] = 'FAILED_CLEANUP'
        try:
            network.checked_source(g.BASE / 'monero-fcmp')
            receipt['shared_source_recheck'] = 'PASS_PINNED_SOURCE_PATHS'
        except Exception as error:
            receipt['shared_source_recheck'] = str(error)
            receipt['result'] = 'FAILED_SOURCE_RECHECK'
        receipt['wall_seconds'] = round(time.monotonic() - began, 3)
        network.write_json(out / 'receipt.json', receipt)
        if lock is not None:
            os.close(lock)
    print(json.dumps({k: receipt[k] for k in ('result', 'testnet_admission', 'wall_seconds')}))
    return 0 if receipt['result'] == 'PASS_NATIVE_TESTNET_GENESIS_AND_CONTROLS_ONLY' else 1


if __name__ == '__main__':
    sys.exit(main())
