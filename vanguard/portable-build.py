#!/usr/bin/env python3
"""Build the locked Linux programs in the existing offline builders.

Fresh source archives come from exact git objects, including submodules. ARM
cache reuse verifies accepted preparation, source and compiler pins first.
All writes are owned; reusable inputs stay unchanged.
"""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import subprocess
import tarfile
import time
import uuid
import portable_licenses

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('tester', ROOT / 'vanguard/tester.py')
tester = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tester)
PIN = tester.PIN


def build_diagnostics(work):
    """Classify owned compiler evidence without exporting text or paths."""
    result = {'phase': 'UNKNOWN', 'reason': 'BUILD_FAILURE_UNCLASSIFIED',
              'peak_memory_bytes': None, 'memory_events': {}}
    def read(name, limit):
        path = work / name
        if not path.is_file() or path.is_symlink() or path.stat().st_nlink != 1:
            return ''
        with path.open('rb') as stream:
            stream.seek(max(0, path.stat().st_size - limit))
            return stream.read(limit).decode('utf-8', errors='replace')
    phase = read('build.phase', 128).strip()
    if phase in ('TOOLCHAIN', 'DEPENDENCIES', 'CONFIGURE', 'COMPILE', 'ABI_INSPECTION'):
        result['phase'] = phase
    peak = read('build.memory', 64).strip()
    if peak.isdigit():
        result['peak_memory_bytes'] = int(peak)
    for line in read('build.memory-events', 1024).splitlines():
        fields = line.split()
        if len(fields) == 2 and fields[0] in ('low', 'high', 'max', 'oom', 'oom_kill', 'oom_group_kill') and fields[1].isdigit():
            result['memory_events'][fields[0]] = int(fields[1])
    text = read('build.log', 1024 * 1024)
    patterns = [
        (r'fatal error: Killed signal terminated program', 'COMPILER_PROCESS_KILLED'),
        (r'internal compiler error:.*(?:Segmentation fault|segmentation fault)', 'COMPILER_INTERNAL_SEGMENTATION_FAILURE'),
        (r'internal compiler error:', 'COMPILER_INTERNAL_ERROR'),
        (r"error:.*(?:nothrow.*not a member|no member named 'nothrow')", 'STD_NOTHROW_DECLARATION_MISSING'),
        (r"error:.*(?:undeclared identifier 'posix_memalign'|posix_memalign.*not declared)", 'POSIX_MEMALIGN_DECLARATION_MISSING'),
        (r'error:.*No space left on device|fatal error:.*No space left on device', 'COMPILER_DISK_FULL'),
        (r'(?:fatal )?error:', 'COMPILER_ERROR_RECORDED'),
    ]
    for pattern, reason in patterns:
        if re.search(pattern, text):
            result['reason'] = reason
            break
    result['cgroup_oom_kill_observed'] = result['memory_events'].get('oom_kill', 0) > 0
    return result


def export_sources(cache, source, work, run):
    up = cache / 'monero-fcmp'
    source.mkdir()
    for relative, revision in {'': PIN['upstream']['commit'], **PIN['upstream']['submodules']}.items():
        repository = up / relative
        tester.require(tester.command(['git', '-C', str(repository), 'rev-parse', 'HEAD']) == revision,
                       'cached source revision mismatch')
        archive = work / ('source-' + (relative.replace('/', '-') or 'upstream') + '.tar')
        run('archive-' + (relative.replace('/', '-') or 'upstream'),
            ['git', '-C', str(repository), 'archive', '--format=tar', '-o', str(archive), revision])
        destination = source / relative
        destination.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive) as stream:
            stream.extractall(destination, filter='data')
        archive.unlink()
    tester.require(tester.sha(source / PIN['rust']['cargo_lock_path']) == PIN['rust']['cargo_lock_sha256'],
                   'Cargo.lock pin mismatch')


def native_compile_resources(target, preparation):
    """Fixed fresh Ubuntu22 native policy; other build routes keep their caps."""
    architecture = 'aarch64' if target == 'linux-aarch64' else 'x86_64'
    tester.require(target in ('linux-x86_64', 'linux-aarch64') and platform.system() == 'Linux' and
                   platform.machine() == architecture, 'native Ubuntu22 resource policy target mismatch')
    tester.require(preparation and preparation['target'] == target and preparation['distribution'] == 'Ubuntu 22.04'
                   and preparation.get('compiler_execution_substrate', 'NATIVE') == 'NATIVE', 'fresh native Ubuntu22 preparation required')
    release = dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
    tester.require(release['ID'].strip('"') == 'ubuntu' and release['VERSION_ID'].strip('"') == '22.04', 'Ubuntu22 host required')
    available = int(next(row.split()[1] for row in Path('/proc/meminfo').read_text().splitlines()
                         if row.startswith('MemAvailable:'))) * 1024
    tester.require(available >= 6 * 1024**3, 'requires 6 GiB available memory for native Ubuntu22 compile')
    return {'scope': 'FRESH_NATIVE_UBUNTU22_ONLY', 'container_memory_bytes': 4 * 1024**3,
            'container_memory_swap_bytes': 4 * 1024**3, 'host_minimum_available_bytes': 6 * 1024**3,
            'measured_available_bytes': available}


def main():
    os.environ['GIT_OPTIONAL_LOCKS'] = '0'
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--rust', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--target', choices=['linux-x86_64', 'linux-aarch64'], default='linux-x86_64')
    parser.add_argument('--reuse-arm-cache', action='store_true')
    parser.add_argument('--inspect-built', type=Path)
    parser.add_argument('--older-builder-receipt', type=Path, help='Exact task-owned Ubuntu 22.04 builder preparation receipt')
    parser.add_argument('--depends-sources', type=Path, help='Read-only cache of checksum-pinned depends source archives')
    parser.add_argument('--native-ubuntu22-memory-policy', action='store_true')
    args = parser.parse_args()
    work = tester.fresh(args.out)
    cache, rust = args.cache.resolve(), args.rust.resolve()
    arm = args.target == 'linux-aarch64'
    image = tester.PROFILE['image'] if arm else PIN['builder']['image_id']
    preparation = None
    if args.older_builder_receipt:
        tester.require(not args.reuse_arm_cache and not args.inspect_built, 'older baseline requires fresh source build')
        preparation = tester.read(args.older_builder_receipt)
        tester.require(preparation['result'] == 'PREPARED_OLDER_BUILDER' and preparation['cleanup']['removed'] and preparation['distribution'] == 'Ubuntu 22.04', 'unverified older builder')
        tester.require(preparation['target'] == args.target, 'older builder target mismatch')
        image = preparation['builder_image']
    docker = ['docker', '--context', 'colima'] if platform.system() == 'Darwin' else ['docker']
    architecture = 'arm64' if arm else 'amd64'
    native = {'x86_64': 'amd64', 'aarch64': 'arm64', 'arm64': 'arm64'}.get(platform.machine())
    translated = bool(preparation and preparation.get('compiler_execution_substrate') ==
                      'PREEXISTING_QEMU_AMD64_ON_COLIMA_ARM64')
    tester.require(not translated or (platform.system() == 'Darwin' and native == 'arm64' and
                   architecture == 'amd64'), 'translated compiler requires the existing ARM64 Mac host')
    tester.require(native == architecture or translated, 'native compiler architecture required')
    compile_resources = None
    if args.native_ubuntu22_memory_policy:
        tester.require(not args.reuse_arm_cache and not args.inspect_built and not translated, 'fresh native resource policy only')
        compile_resources = native_compile_resources(args.target, preparation)  # Before acquiring the lock.
    with tester.heavy_lock():
        tester.require(shutil.disk_usage(work.parent).free >= 10 * 1024**3,
                       'requires 10 GiB free disk before build')
        docker_free = int(tester.command(['colima', 'ssh', '--', 'df', '-B1', '/var/lib/docker']).splitlines()[-1].split()[3]) if platform.system() == 'Darwin' else shutil.disk_usage('/var/lib/docker').free
        tester.require(docker_free >= 10 * 1024**3, 'requires 10 GiB Docker disk reserve')
        memory = tester.command(['colima', 'ssh', '--', 'cat', '/proc/meminfo']) if platform.system() == 'Darwin' else Path('/proc/meminfo').read_text()
        available = int(next(row.split()[1] for row in memory.splitlines()
                             if row.startswith('MemAvailable:'))) * 1024
        tester.require(available >= (6 if compile_resources else 5) * 1024**3,
                       'requires 6 GiB available memory' if compile_resources else 'requires 5 GiB available memory')
        tester.require(tester.command(docker + ['image', 'inspect', image,
                       '--format', '{{.Architecture}} {{.Os}}']) == architecture + ' linux', 'wrong builder target')
        if platform.system() == 'Darwin':
            tester.require(not tester.command(docker + ['ps', '-q']), 'Docker busy; preserve non-owned work')
        if translated:
            emulation = tester.command(['colima', 'ssh', '--', 'cat', '/proc/sys/fs/binfmt_misc/qemu-x86_64'])
            tester.require(emulation.startswith('enabled\n') and 'flags: POCF' in emulation,
                           'already-enabled x64 container translation required')
        recovery = None
        if args.inspect_built:
            prior = tester.read(args.inspect_built / 'build-receipt.json')
            tester.require(prior['source_lock'] == PIN and prior['builder_image'] == image and
                           prior['patches'] == [] and prior['cleanup']['removed'], 'unowned or incompatible recovery')
            recovery = tester.sha(args.inspect_built / 'build-receipt.json')
            shutil.copytree(args.inspect_built, work)
            work.chmod(0o700)
        elif args.reuse_arm_cache:
            tester.require(arm, 'only the accepted ARM cache is reusable')
            tester.cached_inputs(cache)
            shutil.copytree(cache, work)
            work.chmod(0o700)
        else:
            work.mkdir(mode=0o700)
        receipt = {'schema': 'meownero-portable-build/1', 'target': args.target, 'builder_image': image,
                   'source_lock': PIN, 'patches': [], 'commands': [], 'result': 'INCOMPLETE',
                   'started_utc': datetime.now(timezone.utc).isoformat()}
        receipt['compiler_execution_substrate'] = preparation.get('compiler_execution_substrate', 'NATIVE') if preparation else 'NATIVE'
        if preparation:
            receipt['older_builder_preparation_sha256'] = tester.sha(args.older_builder_receipt)
            receipt['distribution'] = preparation['distribution']
        if recovery:
            receipt['recovered_attempt_receipt_sha256'] = recovery

        def save():
            tester.write(work / 'build-receipt.json', receipt)

        def run(label, argv, timeout=60):
            began = time.monotonic()
            row = {'label': label, 'argv': argv}
            receipt['commands'].append(row)
            save()
            try:
                with (work / (label + '.log')).open('wb') as stream:
                    result = subprocess.run(argv, stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
                row['exit'] = result.returncode
                tester.require(result.returncode == 0, label + ' failed; diagnostics preserved')
            finally:
                cleanup_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGINT})
                cleanup_handlers = {s: signal.getsignal(s) for s in (signal.SIGTERM, signal.SIGINT)}
                try:
                    row['wall_seconds'] = time.monotonic() - began
                    save()
                finally:
                    try:
                        for number, handler in cleanup_handlers.items():
                            signal.signal(number, handler)
                    finally:
                        signal.pthread_sigmask(signal.SIG_SETMASK, cleanup_mask)
            print(label, row['exit'], flush=True)

        source = work / 'monero-fcmp'
        if args.inspect_built:
            tester.require(tester.sha(source / PIN['rust']['cargo_lock_path']) == PIN['rust']['cargo_lock_sha256'],
                           'recovery source lock mismatch')
            tester.require(tester.command(['git', '-C', str(source), 'rev-parse', 'HEAD']) == PIN['upstream']['commit']
                           and not tester.command(['git', '-C', str(source), 'status', '--porcelain', '--untracked-files=no']),
                           'recovery tracked source changed')
        elif args.reuse_arm_cache:
            receipt['cache_preparation_sha256'] = tester.sha(cache / 'preparation/receipt.json')
        else:
            export_sources(cache, source, work, run)
            shutil.copytree(cache / 'cargo-home', work / 'cargo-home', symlinks=False)
            if preparation:
                tester.require(args.depends_sources and args.depends_sources.is_dir(), 'older baseline needs pinned depends sources')
                shutil.copytree(args.depends_sources, source / 'contrib/depends/sources')
                receipt['dependency_licenses'] = portable_licenses.retain_depends(work)
                receipt['depends_static_dependencies'] = True
        receipt['rustc_sha256'] = tester.sha(rust / 'bin/rustc')
        receipt['cargo_sha256'] = tester.sha(rust / 'bin/cargo')
        name = 'tjs1882-' + uuid.uuid4().hex + '-linux-build'
        invocation = uuid.uuid4().hex
        cidfile = work / (invocation + '.container.id')
        script = '''set -e
printf '%s\\n' TOOLCHAIN > /out/build.phase
test "$(rustc -V)" = 'rustc 1.93.0 (254b59607 2026-01-19)'
trap 'cat /sys/fs/cgroup/memory.peak > /out/build.memory; cat /sys/fs/cgroup/memory.events > /out/build.memory-events' EXIT
dpkg-query -W -f='${binary:Package}=${Version}\\n' | sort > /out/dependencies.txt
mkdir -p /out/licenses
for copyright in /usr/share/doc/*/copyright; do
    cp -L "$copyright" "/out/licenses/COPYRIGHT-$(basename "$(dirname "$copyright")")"
done
for license in /usr/share/common-licenses/*; do
    cp -L "$license" "/out/licenses/COPYING-common-$(basename "$license")"
done
gcc --version > /out/compiler.txt
cmake --version >> /out/compiler.txt
rustc -Vv >> /out/compiler.txt
mkdir -p build/vanguard
cd build/vanguard
printf '%s\\n' CONFIGURE > /out/build.phase
cmake -DCMAKE_BUILD_TYPE=Release -DARCH=default -DBUILD_TESTS=OFF -DUSE_DEVICE_TREZOR=OFF -DBUILD_GUI_DEPS=OFF -DMANUAL_SUBMODULES=ON -DSTATIC=OFF -DUSE_READLINE=OFF ../..
printf '%s\\n' COMPILE > /out/build.phase
timeout 3500 make -j1 daemon simplewallet wallet_rpc_server
printf '%s\\n' ABI_INSPECTION > /out/build.phase
mkdir -p /out/runtime-libs
for binary in bin/monerod bin/monero-wallet-cli bin/monero-wallet-rpc; do
    "$binary" --version
    readelf -h "$binary"
    readelf -d "$binary" | grep NEEDED || true
    ldd "$binary" >> /out/runtime-links.txt
    for library in $(ldd "$binary" | awk '$3 ~ /^\\// {print $3}'); do
        case "$(basename "$library")" in libc.so.*|libm.so.*|libdl.so.*|libpthread.so.*|librt.so.*) continue;; esac
        cp -L "$library" /out/runtime-libs/
    done
done
'''
        if args.inspect_built:
            first = script.index('mkdir -p build/vanguard')
            last = script.index('mkdir -p /out/runtime-libs')
            script = script[:first] + 'cd build/vanguard\n' + script[last:]
        if preparation:
            depends_host = 'aarch64-unknown-linux-gnu' if arm else 'x86_64-unknown-linux-gnu'
            first = script.index('mkdir -p build/vanguard')
            script = script[:first] + '''cd contrib/depends
printf '%s\\n' DEPENDENCIES > /out/build.phase
make -j2 HOST=DEPENDS_HOST NO_WALLET=1 NO_READLINE=1 linux_CC=gcc linux_CXX=g++ linux_AR=ar linux_RANLIB=ranlib linux_NM=nm linux_STRIP=strip
cd ../..
sed -i 's/SET(STATIC ON)/SET(STATIC OFF)/' contrib/depends/DEPENDS_HOST/share/toolchain.cmake
sha256sum contrib/depends/DEPENDS_HOST/share/toolchain.cmake > /out/generated-toolchain.sha256
'''.replace('DEPENDS_HOST', depends_host) + script[first:]
            script = script.replace('cmake -DCMAKE_BUILD_TYPE=Release ',
                ('cmake -DCMAKE_TOOLCHAIN_FILE=/src/contrib/depends/DEPENDS_HOST/share/toolchain.cmake -DOPENSSL_USE_STATIC_LIBS=ON -DOPENSSL_CRYPTO_LIBRARY=/src/contrib/depends/DEPENDS_HOST/lib/libcrypto.a -DOPENSSL_SSL_LIBRARY=/src/contrib/depends/DEPENDS_HOST/lib/libssl.a -Dsodium_USE_STATIC_LIBS=ON -DCMAKE_BUILD_TYPE=Release ').replace('DEPENDS_HOST', depends_host))
            receipt['generated_toolchain_adaptation'] = 'Static pinned Boost/OpenSSL3.5.8/ZeroMQ/Unbound/Sodium closure; dynamic system libc/C++ ABI for the older distro floor.'
        reuse_paths = args.reuse_arm_cache or args.inspect_built
        mount = '/work/monero-fcmp' if reuse_paths else '/src'
        if reuse_paths:
            script = script.replace('/opt/rust', '/work/rust')
        if compile_resources:
            compile_resources = native_compile_resources(args.target, preparation)  # Fresh immediately before compile.
            receipt['native_compile_resources'] = compile_resources
            save()
        container_memory = '4g' if compile_resources else '3g'
        argv = docker + ['run', '--platform=linux/' + architecture, '--pull=never', '--name', name, '--cidfile', str(cidfile),
                '--label', 'meownero.invocation=' + invocation, '--network=none', '--cpus=2',
                '--memory=' + container_memory, '--memory-swap=' + container_memory, '--pids-limit=256', '--cap-drop=ALL',
                '--security-opt=no-new-privileges', '--ulimit', 'core=0', '-u', f'{os.getuid()}:{os.getgid()}',
                '-v', f'{source}:{mount}', '-v', f'{work / "cargo-home"}:/cargo-home',
                '-v', f'{rust}:/opt/rust:ro', '-v', f'{work}:/out', '-e', 'CARGO_HOME=/cargo-home',
                '-e', 'CARGO_NET_OFFLINE=true', '-e', 'CARGO_BUILD_JOBS=1', '-e', 'HOME=/tmp',
                '-e', 'PATH=/opt/rust/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
                '-w', mount, image, 'bash', '-ec', script]
        if reuse_paths:
            argv[argv.index(f'{rust}:/opt/rust:ro')] = f'{rust}:/work/rust:ro'
            argv[argv.index('PATH=/opt/rust/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin')] = 'PATH=/work/rust/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'
        try:
            run('inspect' if args.inspect_built else 'build', argv, 120 if args.inspect_built else 3600)
            receipt['binaries'] = {name: {'sha256': tester.sha(source / 'build/vanguard/bin' / name),
                'bytes': (source / 'build/vanguard/bin' / name).stat().st_size}
                for name in ('monerod', 'monero-wallet-cli', 'monero-wallet-rpc')}
            receipt['result'] = 'BUILT_VERSION_EXECUTED_JOURNEY_UNTESTED'
        except BaseException as error:
            receipt['result'] = 'FAILED_ATTEMPT'
            receipt['failure'] = str(error)
            receipt['failure_type'] = type(error).__name__
            receipt['build_diagnostic'] = build_diagnostics(work)
            raise
        finally:
            cleanup_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGINT})
            cleanup_handlers = {s: signal.getsignal(s) for s in (signal.SIGTERM, signal.SIGINT)}
            try:
                try:
                    if cidfile.exists():
                        cid = cidfile.read_text().strip()
                        receipt['cleanup'] = {'id': cid, 'removed': False, 'ownership': 'unknown'}
                        save()
                        proof = json.loads(tester.command(docker + ['inspect', cid]))[0]
                        tester.require(proof['Id'] == cid and proof['Name'] == '/' + name and
                            proof['Image'] == image and
                            proof['Config']['Labels'].get('meownero.invocation') == invocation,
                            'container ownership proof failed; preserve container')
                        receipt['cleanup']['ownership'] = 'proven'
                        if receipt['result'] == 'FAILED_ATTEMPT':
                            receipt['build_diagnostic'] = build_diagnostics(work)
                            state = proof['State']
                            receipt['build_diagnostic']['owned_container_oom_killed'] = bool(state['OOMKilled'])
                            receipt['build_diagnostic']['owned_container_exit'] = int(state['ExitCode'])
                            receipt['build_diagnostic']['owned_container_running_at_inspection'] = bool(state['Running'])
                        run('cleanup', docker + ['rm', '-f', cid], 30)
                        tester.require(cid not in tester.command(docker + ['ps', '-aq', '--no-trunc']).splitlines(),
                                       'owned container remains')
                        receipt['cleanup']['removed'] = True
                finally:
                    receipt['finished_utc'] = datetime.now(timezone.utc).isoformat()
                    save()
            finally:
                try:
                    for number, handler in cleanup_handlers.items():
                        signal.signal(number, handler)
                finally:
                    signal.pthread_sigmask(signal.SIG_SETMASK, cleanup_mask)


if __name__ == '__main__':
    def cancelled(signum, frame):
        raise RuntimeError('build cancelled; preserve diagnostics and clean proven owned container')
    signal.signal(signal.SIGTERM, cancelled)
    main()
