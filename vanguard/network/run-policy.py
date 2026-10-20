#!/usr/bin/env python3
"""One finite policy witness, only after a new platform-owner window grant."""
import argparse
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import time

import network as n
import policy

spec = importlib.util.spec_from_file_location('genesis_driver', Path(__file__).with_name('run-genesis.py'))
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)
g.NATIVE.update({'vanguard_network_policy', 'vanguard_network_admission'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--grant-comment', required=True,
        help='actual new platform grant UUID; old consumed grants are refused')
    args = parser.parse_args()
    n.require(re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', args.grant_comment), 'grant UUID required')
    n.require(args.grant_comment not in {'2d70177d-b7a7-4ef6-8079-242320bdcb1f',
                                       '15414082-2a53-4872-8d19-b87f302f0bae'}, 'prior grant is consumed')
    os.umask(0o077)
    out = n.fresh_directory(args.out)
    start = time.monotonic()
    deadline = start + 880
    receipt = {'schema': 'meownero-vanguard-policy-attempt/1', 'result': 'NOT_STARTED',
        'grant_comment': args.grant_comment, 'launch_ready': False, 'native_network_separation': 'NOT_RUN',
        'limits': {'wall_seconds': 900, 'execution_seconds': 880, 'cleanup_reserve_seconds': 20,
                   'cpus': 2, 'memory_bytes': 4294967296, 'swap_bytes': 0, 'pids': 256,
                   'compile_jobs': 1, 'network': 'none', 'published_ports': [], 'mined_blocks': 0}}
    lock = None
    cid = None

    def interrupted(signum, frame):
        raise RuntimeError('host supervision interrupted: ' + str(signum))

    for signum in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, interrupted)
    try:
        lock = os.open(g.LOCK, os.O_RDWR | os.O_NOFOLLOW)
        info = os.fstat(lock)
        n.require(stat.S_ISREG(info.st_mode) and (info.st_dev, info.st_ino) == g.LOCK_ID and
                  info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o600,
                  'original heavy-lock identity/owner/mode mismatch')
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        receipt['lock'] = {'device': info.st_dev, 'inode': info.st_ino}
        n.require(not subprocess.check_output(['git', '-C', str(n.ROOT), 'status', '--porcelain'],
                                             text=True).strip(), 'commit the exact candidate before native work')
        receipt['candidate_commit'] = subprocess.check_output(['git', '-C', str(n.ROOT), 'rev-parse', 'HEAD'],
                                                              text=True).strip()
        pin = n.read_json(n.HERE.parent / 'source-lock.json')
        value = n.profile()
        image = pin['builder']['image_id']
        receipt['admission'] = g.admission(image)
        g.require_admission(receipt['admission'])
        row = json.loads(subprocess.check_output(g.DOCKER + ['image', 'inspect', image], text=True, timeout=10))[0]
        n.require(row['Id'] == image and row['Architecture'] == 'amd64' and row['Os'] == 'linux', 'builder mismatch')
        originals = policy.checked_source(g.BASE / 'monero-fcmp')
        n.require(subprocess.check_output([str(g.RUST / 'bin/rustc'), '-V'], text=True, timeout=5).strip()
                  == pin['builder']['rustc'], 'Rust toolchain mismatch')
        receipt.update(profile_sha256=n.profile_hash(value), source_lock_sha256=value['source_lock_sha256'],
                       upstream_commit=value['upstream_commit'], builder_image=image, archives={})
        source = out / 'source'
        source.mkdir()
        for name, revision in [('', pin['upstream']['commit']), *pin['upstream']['submodules'].items()]:
            archive = out / ('source-' + (name.replace('/', '-') or 'root') + '.tar')
            g.run(['git', '-C', str(g.BASE / 'monero-fcmp' / name), 'archive', '--format=tar',
                   '-o', str(archive), revision], deadline=deadline, env={**os.environ, 'GIT_NO_LAZY_FETCH': '1'})
            receipt['archives'][name or '.'] = {'revision': revision, 'sha256': g.digest(archive)}
            destination = source / name
            destination.mkdir(parents=True, exist_ok=True)
            g.run(['tar', '-xf', str(archive), '-C', str(destination)], deadline=deadline)
        n.require(all((source / name).read_bytes() == raw for name, raw in originals.items()), 'export source mismatch')
        overlay = policy.prepare(g.BASE / 'monero-fcmp', out / 'overlay', value)
        n.require(overlay == n.read_json(n.HERE / 'evidence/selected-policy/policy-overlay.json'),
                  'overlay differs from frozen candidate')
        patch = out / 'overlay/selected-9-90.patch'
        g.run(['git', 'apply', '--check', str(patch)], cwd=source, deadline=deadline)
        g.run(['git', 'apply', str(patch)], cwd=source, deadline=deadline)
        for name, binding in overlay['files'].items():
            n.require(g.digest(source / name) == binding['changed_sha256'], 'applied policy hash differs')
        receipt['overlay'] = overlay
        target = source / 'tests/vanguard-policy'
        shutil.copytree(n.HERE / 'native/policy', target)
        cmake = source / 'tests/CMakeLists.txt'
        receipt['tests_cmake_original_sha256'] = g.digest(cmake)
        with cmake.open('a') as stream:
            stream.write('\nadd_subdirectory(vanguard-policy)\n')
        receipt['tests_cmake_changed_sha256'] = g.digest(cmake)
        receipt['witness_sources'] = {name: g.digest(target / name) for name in ('CMakeLists.txt', 'policy.cpp')}
        receipt['driver_sources'] = {name: g.digest(n.HERE / name) for name in
            ('run-policy.py', 'run-genesis.py', 'network.py', 'policy.py', 'policy-bindings.json', 'profile.json')}
        cargo = out / 'cargo-home'
        cargo.mkdir()
        for name in ('registry', 'git'):
            shutil.copytree(g.BASE / 'cargo-home' / name, cargo / name)
        receipt['cargo_cache_files'] = {str(p.relative_to(cargo)): g.digest(p) for p in sorted(cargo.rglob('*')) if p.is_file()}
        receipt['cargo_checkout_heads'] = {}
        for path in sorted((cargo / 'git/checkouts').glob('*/*')):
            if (path / '.git').exists():
                revision = subprocess.check_output(['git', '-C', str(path), 'rev-parse', 'HEAD'], text=True, timeout=5).strip()
                receipt['cargo_checkout_heads'][str(path.relative_to(cargo))] = revision
        for key in ('monero_oxide_rev', 'crypto_bigint_rev'):
            n.require(pin['rust'][key] in receipt['cargo_checkout_heads'].values(), 'missing Rust source pin')
        script = '''set -eu
trap 'cat /sys/fs/cgroup/memory.peak > /out/memory.peak; cat /sys/fs/cgroup/memory.events > /out/memory.events; cat /sys/fs/cgroup/cpu.stat > /out/cpu.stat' EXIT
rustc -V > /out/container-rustc.txt
cargo -V > /out/container-cargo.txt
cmake --version > /out/container-cmake.txt
g++ --version > /out/container-gxx.txt
cmake -S /src -B /src/build/network -D CMAKE_BUILD_TYPE=Release -D ARCH=default -D BUILD_TESTS=ON -D USE_DEVICE_TREZOR=OFF -D MANUAL_SUBMODULES=ON > /out/cmake.log 2>&1
cmake --build /src/build/network --target vanguard_network_policy --parallel 1 > /out/make.log 2>&1
sha256sum /src/build/network/tests/vanguard-policy/vanguard_network_policy > /out/binary.sha256
timeout 60 /src/build/network/tests/vanguard-policy/vanguard_network_policy /out/db-policy01 > /out/policy01.json 2> /out/policy01.stderr.log
timeout 60 /src/build/network/tests/vanguard-policy/vanguard_network_policy /out/db-policy02 > /out/policy02.json 2> /out/policy02.stderr.log
cmp /out/policy01.json /out/policy02.json
'''
        (out / 'build.sh').write_text(script)
        receipt['admission_before_create'] = g.admission(image)
        g.require_admission(receipt['admission_before_create'])
        current_lock = os.stat(g.LOCK, follow_symlinks=False)
        n.require((current_lock.st_dev, current_lock.st_ino) == g.LOCK_ID,
                  'original heavy-lock path was replaced before container creation')
        command = g.DOCKER + ['create', '--name', 'tjs2504-policy-' + out.name.lower(),
            '--cidfile', str(out / 'container.cid'), '--label', 'meownero.task=TJS-2504',
            '--pull=never', '--network=none', '--cap-drop=ALL', '--security-opt=no-new-privileges',
            '--cpus=2', '--memory=4g', '--memory-swap=4g', '--pids-limit=256', '--ulimit', 'core=0',
            '-u', f'{os.getuid()}:{os.getgid()}', '-v', f'{source}:/src', '-v', f'{cargo}:/cargo-home',
            '-v', f'{g.RUST}:/opt/rust:ro', '-v', f'{out}:/out', '-e', 'CARGO_HOME=/cargo-home',
            '-e', 'CARGO_NET_OFFLINE=true', '-e', 'CARGO_BUILD_JOBS=1',
            '-e', 'PATH=/opt/rust/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
            '-w', '/src', image, 'bash', '/out/build.sh']
        receipt['create_argv'] = command
        cid = g.run(command, deadline=deadline, capture_output=True, text=True).stdout.strip()
        n.require(re.fullmatch('[0-9a-f]{64}', cid), 'invalid exact container ID')
        receipt.update(container_id=cid, result='RUNNING')
        created = json.loads(subprocess.check_output(g.DOCKER + ['inspect', cid], text=True, timeout=5))[0]
        receipt['created_container'] = {key: created[key] for key in ('Id', 'Image', 'HostConfig', 'Mounts')}
        config = created['HostConfig']
        n.require(created['Image'] == image and config['NetworkMode'] == 'none' and
                  config['Memory'] == config['MemorySwap'] == 4294967296 and
                  config['NanoCpus'] == 2000000000 and config['PidsLimit'] == 256 and
                  not config['PortBindings'] and 'ALL' in config['CapDrop'] and
                  'no-new-privileges' in config['SecurityOpt'], 'created containment differs from request')
        n.write_json(out / 'receipt.json', receipt)
        with (out / 'docker.log').open('w') as log:
            g.run(g.DOCKER + ['start', '-a', cid], deadline=deadline, stdout=log, stderr=subprocess.STDOUT)
        first, second = [json.loads((out / name).read_text()) for name in ('policy01.json', 'policy02.json')]
        n.require(first == second and first['result'] == 'PASS_NATIVE_POLICY_HELPERS_AND_TEMPLATE_ONLY' and
                  (first['reward_vectors'], first['address_vectors'], first['constructions']) == (13608, 39, 24),
                  'native policy result/counters differ')
        receipt['native_policy'] = first
        receipt['result'] = 'PASS_NATIVE_POLICY_HELPERS_AND_TEMPLATE_ONLY'
    except (Exception, KeyboardInterrupt) as error:
        receipt.update(result='FAILED_BOUNDED_ATTEMPT', error=type(error).__name__ + ': ' + str(error))
    finally:
        for signum in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM):
            signal.signal(signum, signal.SIG_IGN)
        try:
            if not cid and (out / 'container.cid').exists():
                cid = (out / 'container.cid').read_text().strip()
            if cid and re.fullmatch('[0-9a-f]{64}', cid):
                inspect = subprocess.run(g.DOCKER + ['inspect', cid], capture_output=True, text=True, timeout=5)
                if inspect.returncode == 0:
                    receipt['container_state_before_cleanup'] = json.loads(inspect.stdout)[0]['State']
                    receipt['cleanup_exit'] = subprocess.run(g.DOCKER + ['rm', '-f', cid], capture_output=True, timeout=5).returncode
                probe = subprocess.run(g.DOCKER + ['inspect', cid], capture_output=True, text=True, timeout=5)
                receipt['container_absent'] = probe.returncode != 0 and 'no such' in probe.stderr.lower()
                if not receipt['container_absent']:
                    receipt['result'] = 'FAILED_CONTAINER_CLEANUP'
            if receipt['result'].startswith('PASS_'):
                events = dict(line.split() for line in (out / 'memory.events').read_text().splitlines())
                n.require(int(events['oom']) == int(events['oom_kill']) == 0, 'native OOM observed')
                n.require(not receipt['container_state_before_cleanup']['OOMKilled'] and
                          receipt['container_state_before_cleanup']['ExitCode'] == 0, 'native exit/OOM differs')
            if lock is not None:
                policy.checked_source(g.BASE / 'monero-fcmp')
                receipt['shared_source_recheck'] = 'PASS'
        except Exception as error:
            receipt.update(result='FAILED_FINAL_CHECKS', final_error=str(error))
        finally:
            receipt['wall_seconds'] = round(time.monotonic() - start, 3)
            if lock is not None:
                os.close(lock)
                receipt['lock_fd_closed'] = True
            n.write_json(out / 'receipt.json', receipt)
    print(json.dumps({key: receipt[key] for key in ('result', 'wall_seconds', 'launch_ready')}, indent=2))
    return 0 if receipt['result'].startswith('PASS_') else 1


if __name__ == '__main__':
    raise SystemExit(main())
