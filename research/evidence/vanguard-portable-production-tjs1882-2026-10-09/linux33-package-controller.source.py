#!/usr/bin/env python3
"""Build the locked older Linux baseline on an owned native GitHub runner."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import time

ROOT = Path(__file__).resolve().parent.parent


def sha(path):
    assert path.is_file() and not path.is_symlink()
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def load(name):
    spec = importlib.util.spec_from_file_location('linux_ci_' + name.replace('-', '_'), ROOT / 'vanguard' / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def resources(parent, reserve=10, minimum_available=5 * 1024**3):
    available = int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines()
                         if line.startswith('MemAvailable:'))) * 1024
    free = shutil.disk_usage(parent).free
    docker_free = shutil.disk_usage('/var/lib/docker').free
    assert minimum_available in (5 * 1024**3, 6 * 1024**3)
    assert available >= minimum_available, 'available memory gate'
    assert min(free, docker_free) >= reserve * 1024**3, 'disk reserve gate'
    return {'available_memory_bytes': available, 'free_disk_bytes': free, 'docker_free_disk_bytes': docker_free}



def fetch(inputs, out):
    """Only exact public source/compiler downloads; later compilation is offline."""
    assert not (out / 'cache').exists()
    cache = out / 'cache'
    cache.mkdir(mode=0o700)
    pin = json.loads((ROOT / 'vanguard/source-lock.json').read_text())
    env = os.environ.copy()
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT='0',
               GIT_OPTIONAL_LOCKS='0', CARGO_HOME=str(cache / 'cargo-home'), CARGO_NET_GIT_FETCH_WITH_CLI='true')

    def run(argv, timeout=180, cwd=None):
        subprocess.run([str(v) for v in argv], env=env, cwd=cwd, check=True, timeout=timeout)

    def download(url, path, digest):
        assert url.startswith('https://') and not path.exists()
        run(['curl', '--fail', '--location', '--proto', '=https', '--proto-redir', '=https',
             '--tlsv1.2', '--max-time', '180', '--retry', '1', '--output', path, url], timeout=370)
        assert sha(path) == digest, 'public download checksum mismatch'

    up = cache / 'monero-fcmp'
    revisions = {'': pin['upstream']['commit'], **pin['upstream']['submodules']}
    for relative, revision in revisions.items():
        destination = up / relative
        destination.mkdir(parents=True, exist_ok=bool(relative), mode=0o700)
        url = pin['upstream']['url'] if not relative else inputs['submodule_urls'][relative]
        if relative:
            configured = subprocess.check_output(['git', '-C', str(up), 'config', '-f', '.gitmodules',
                'submodule.' + relative + '.url'], text=True, env=env, timeout=10).strip()
            assert configured == url, 'submodule URL differs from locked source'
        git = ['git', '-c', 'credential.helper=', '-c', 'core.hooksPath=/dev/null', '-c', 'protocol.file.allow=never']
        run(git + ['init', destination])
        run(git + ['-C', destination, 'remote', 'add', 'origin', url])
        run(git + ['-C', destination, 'fetch', '--depth=1', 'origin', revision])
        run(git + ['-C', destination, 'checkout', '--detach', revision])
        assert subprocess.check_output(git + ['-C', destination, 'rev-parse', 'HEAD'], text=True, env=env).strip() == revision
    assert sha(up / pin['rust']['cargo_lock_path']) == pin['rust']['cargo_lock_sha256']
    rust_archive = out / 'rust-1.93.0-x86_64-unknown-linux-gnu.tar.xz'
    download(inputs['rust']['url'], rust_archive, inputs['rust']['sha256'])
    extract = out / 'rust-distribution'
    extract.mkdir(mode=0o700)
    with tarfile.open(rust_archive) as stream:
        components = {'rustc', 'cargo', 'rust-std-x86_64-unknown-linux-gnu'}
        members = [m for m in stream.getmembers() if len(Path(m.name).parts) < 3 or
                   Path(m.name).parts[1] in components]
        stream.extractall(extract, members=members, filter='data')
    distribution = extract / 'rust-1.93.0-x86_64-unknown-linux-gnu'
    rust = out / 'rust'
    run(['/bin/sh', distribution / 'install.sh', '--prefix=' + str(rust), '--disable-ldconfig',
         '--components=rustc,cargo,rust-std-x86_64-unknown-linux-gnu'])
    assert sha(rust / 'bin/rustc') == inputs['rust']['rustc_sha256']
    assert sha(rust / 'bin/cargo') == inputs['rust']['cargo_sha256']
    assert subprocess.check_output([str(rust / 'bin/rustc'), '-V'], text=True).strip() == pin['builder']['rustc']
    env['PATH'] = str(rust / 'bin') + os.pathsep + env['PATH']
    run([rust / 'bin/cargo', 'fetch', '--locked', '--manifest-path', up / pin['rust']['cargo_lock_path'].replace('Cargo.lock', 'Cargo.toml')], 600)
    depends = cache / 'depends-sources'
    depends.mkdir(mode=0o700)
    for name, row in inputs['depends'].items():
        recipe = up / 'contrib/depends/packages' / (name + '.mk')
        assert sha(recipe) == row['recipe_sha256']
        text = recipe.read_text()
        assert re.search(r'^\$\(package\)_sha256_hash=(.+)$', text, re.M)[1] == row['sha256']
        download(row['url'], depends / row['file'], row['sha256'])
    write(out / 'fetch-receipt.json', {'schema': 'meownero-native-linux-public-input-fetch/1',
        'result': 'PASS_PUBLIC_LOCKED_INPUTS_NATIVE_COMPILATION_UNTESTED', 'upstream_commit': pin['upstream']['commit'],
        'submodules': pin['upstream']['submodules'], 'cargo_lock_sha256': pin['rust']['cargo_lock_sha256'],
        'rust_archive_sha256': sha(rust_archive), 'rustc_sha256': sha(rust / 'bin/rustc'),
        'cargo_sha256': sha(rust / 'bin/cargo'), 'depends_sha256': {n: sha(depends / r['file']) for n, r in inputs['depends'].items()}})


def public_worker_receipt(value):
    """Keep fixed build provenance and scalars; omit execution text and paths."""
    keys = ('schema', 'target', 'builder_image', 'source_lock', 'patches', 'result',
            'started_utc', 'finished_utc', 'compiler_execution_substrate', 'distribution',
            'older_builder_preparation_sha256', 'depends_static_dependencies',
            'rustc_sha256', 'cargo_sha256', 'base_manifest', 'base_image',
            'registry_access', 'cleanup', 'binaries')
    result = {key: value[key] for key in keys if key in value}
    result['commands'] = []
    if 'native_compile_resources' in value:
        policy = value['native_compile_resources']
        assert policy['scope'] == 'FRESH_NATIVE_UBUNTU22_ONLY'
        safe = {'scope': policy['scope']}
        for key in ('container_memory_bytes', 'container_memory_swap_bytes', 'host_minimum_available_bytes', 'measured_available_bytes'):
            assert type(policy[key]) is int and policy[key] >= 0
            safe[key] = policy[key]
        result['native_compile_resources'] = safe
    for row in value.get('commands', []):
        label = row.get('label')
        allowed = ('archive-upstream', 'archive-external-gtest', 'archive-external-mx25519',
                   'archive-external-randomx', 'archive-external-rapidjson', 'archive-external-supercop',
                   'build', 'inspect', 'cleanup', 'base', 'prepare', 'commit')
        safe = {'label': label if label in allowed else 'OTHER_PHASE'}
        for key in ('exit', 'wall_seconds'):
            if key in row:
                assert type(row[key]) in (int, float) or row[key] is None
                safe[key] = row[key]
        result['commands'].append(safe)
    if 'failure_type' in value:
        kinds = ('RuntimeError', 'AssertionError', 'TimeoutExpired', 'KeyboardInterrupt',
                 'SystemExit', 'OSError', 'PermissionError', 'FileNotFoundError')
        result['failure_type'] = value['failure_type'] if value['failure_type'] in kinds else 'OTHER_EXCEPTION'
    if 'build_diagnostic' in value:
        diagnostic = value['build_diagnostic']
        phases = ('UNKNOWN', 'TOOLCHAIN', 'DEPENDENCIES', 'CONFIGURE', 'COMPILE', 'ABI_INSPECTION')
        reasons = ('BUILD_FAILURE_UNCLASSIFIED', 'COMPILER_PROCESS_KILLED', 'COMPILER_INTERNAL_SEGMENTATION_FAILURE',
                   'COMPILER_INTERNAL_ERROR', 'STD_NOTHROW_DECLARATION_MISSING', 'POSIX_MEMALIGN_DECLARATION_MISSING',
                   'COMPILER_DISK_FULL', 'COMPILER_ERROR_RECORDED')
        safe = {'phase': diagnostic['phase'] if diagnostic.get('phase') in phases else 'UNKNOWN',
                'reason': diagnostic['reason'] if diagnostic.get('reason') in reasons else 'BUILD_FAILURE_UNCLASSIFIED'}
        for key in ('peak_memory_bytes', 'cgroup_oom_kill_observed', 'owned_container_oom_killed',
                    'owned_container_exit', 'owned_container_running_at_inspection'):
            if key in diagnostic:
                assert type(diagnostic[key]) in (int, bool) or diagnostic[key] is None
                safe[key] = diagnostic[key]
        safe['memory_events'] = {key: count for key, count in diagnostic.get('memory_events', {}).items()
                                if key in ('low', 'high', 'max', 'oom', 'oom_kill', 'oom_group_kill') and type(count) is int}
        result['build_diagnostic'] = safe
    return result




def package_failure(error, inputs):
    """Record a bound source location, never exception text, argv or paths."""
    kinds = {'AssertionError', 'RuntimeError', 'CalledProcessError', 'OSError',
             'ValueError', 'KeyError', 'KeyboardInterrupt', 'SystemExit'}
    value = {'schema': 'meownero-native-linux-package-failure/1', 'phase': 'PACKAGE',
             'failure_type': type(error).__name__ if type(error).__name__ in kinds else 'OTHER_ERROR',
             'source_module': 'UNKNOWN', 'source_line': None, 'source_sha256': None}
    modules = {str(ROOT / 'vanguard' / name): name
               for name in ('package-portable.py', 'portable_licenses.py')}
    frame = error.__traceback__
    while frame is not None:
        name = modules.get(frame.tb_frame.f_code.co_filename)
        if name is not None:
            value.update(source_module=name, source_line=frame.tb_lineno,
                         source_sha256=inputs['source_files']['vanguard/' + name])
            context = frame.tb_frame.f_locals.get('package_context') if name == 'portable_licenses.py' else None
            if isinstance(context, dict):
                components = {'boost', 'openssl', 'sodium', 'unbound', 'zeromq'}
                component = context.get('component')
                public = {'component': component if isinstance(component, str) and component in components else 'UNKNOWN',
                          'libraries': [], 'link_commands': []}
                names = r'lib(?:boost_(?:filesystem|program_options|serialization|thread|chrono|atomic|container|date_time|charconv|locale)|ssl|crypto|sodium|unbound|zmq)\.(?:a|so(?:\.\d+)*)'
                rows = context.get('libraries', ())
                if isinstance(rows, (list, tuple, set)):
                    for row in list(rows)[:64]:
                        if isinstance(row, (list, tuple)) and len(row) == 2:
                            basename, origin = row
                            if isinstance(basename, str) and isinstance(origin, str) and origin in {'pinned_depends', 'system', 'bundled', 'non_pinned_depends', 'unmapped_contrib', 'unmapped_relative'}:
                                public['libraries'].append({'basename': basename if re.fullmatch(names, basename) else 'OTHER_LIBRARY',
                                                            'origin': origin})
                public['libraries'] = sorted(public['libraries'], key=lambda row: (row['basename'], row['origin']))
                rows = context.get('link_commands', ())
                if isinstance(rows, (list, tuple)):
                    for row in rows[:64]:
                        if not isinstance(row, dict):
                            continue
                        target, digest = row.get('target'), row.get('sha256')
                        if isinstance(target, str) and target in {'daemon', 'simplewallet', 'wallet_rpc_server'} and isinstance(digest, str) and re.fullmatch(r'[0-9a-f]{64}', digest):
                            public['link_commands'].append({'target': target, 'sha256': digest,
                                                            'kind': 'response_file' if 'response_file' in row else 'link_command'})
                value['depends_inventory'] = public
        frame = frame.tb_next
    return value


def worker(phase, inputs, out):
    if phase == 'fetch':
        fetch(inputs, out)
        return
    cache = out / 'cache'
    argv = {
        'prepare': ['--out', str(out / 'builder'), '--target', 'linux-x86_64'],
        'build': ['--cache', str(cache), '--rust', str(out / 'rust'), '--out', str(out / 'build'),
                  '--target', 'linux-x86_64', '--older-builder-receipt', str(out / 'builder/preparation.json'),
                  '--depends-sources', str(cache / 'depends-sources'), '--native-ubuntu22-memory-policy'],
        'package': ['--build', str(out / 'build'), '--out', str(out / 'package')],
    }
    scripts = {'prepare': 'portable-prepare-old-linux.py', 'build': 'portable-build.py', 'package': 'package-portable.py'}
    if phase == 'runtime':
        archive = out / 'package/meownero-vanguard-x86_64.tar.gz'
        image = json.loads((out / 'builder/preparation.json').read_text())['builder_image']
        sys.argv = ['run-portable-check.py', '--archive', str(archive), '--sha256', sha(archive),
                    '--target', 'linux-x86_64', '--runtime-image', image, '--out', str(out / 'runtime')]
        load('run-portable-check.py').main()
    else:
        sys.argv = [scripts[phase], *argv[phase]]
        try:
            load(scripts[phase]).main()
        except BaseException as error:
            if phase == 'package':
                try:
                    write(out / 'public/package-diagnostic.json', package_failure(error, inputs))
                except BaseException:
                    error.add_note('PACKAGE_DIAGNOSTIC_EXPORT_FAILED')
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--inputs-sha256', required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--validate-only', action='store_true')
    parser.add_argument('--phase', choices=['fetch', 'prepare', 'build', 'package', 'runtime'])
    args = parser.parse_args()
    os.umask(0o077)
    assert sha(args.inputs) == args.inputs_sha256
    inputs = json.loads(args.inputs.read_text())
    assert inputs['schema'] == 'meownero-private-native-linux-build-inputs/1'
    policy = {'scope': 'FRESH_NATIVE_UBUNTU22_ONLY', 'target': 'linux-x86_64', 'container_memory_bytes': 4 * 1024**3, 'container_memory_swap_bytes': 4 * 1024**3, 'host_minimum_available_bytes': 6 * 1024**3}
    assert inputs['compile_resource_policy'] == policy, 'architecture-bound compile resource policy mismatch'
    for name, digest in inputs['source_files'].items():
        assert sha(ROOT / name) == digest, 'CI source input mismatch: ' + name
    out = args.out.absolute()
    if args.phase:
        assert out.is_dir() and not out.is_symlink()
        worker(args.phase, inputs, out)
        return
    assert out.parent.is_dir() and not out.exists() and not any(p.is_symlink() for p in (out, *out.parents))
    out.mkdir(mode=0o700)
    public = out / 'public'
    public.mkdir(mode=0o700)
    proof = {'schema': 'meownero-native-ubuntu22-ci-build-and-journey/1', 'result': 'FAIL',
             'inputs_sha256': args.inputs_sha256, 'github_sha': os.environ.get('GITHUB_SHA'),
             'github_run_id': os.environ.get('GITHUB_RUN_ID'), 'phases': [],
             'debian12_execution': 'UNTESTED', 'independent_release_acceptance': 'PENDING_ORIGINAL_REVIEWER'}
    began, lock_identity = time.monotonic(), None
    lock = Path('/tmp/meownero-swarm-20260912-heavy.lock')
    try:
        if args.validate_only:
            proof['result'] = 'PASS_ALLOWLIST_ONLY_RUNNER_BUILD_NATIVE_JOURNEY_UNTESTED'
            return
        assert os.environ.get('GITHUB_ACTIONS') == 'true' and os.environ.get('RUNNER_OS') == 'Linux'
        assert os.environ.get('RUNNER_ARCH') == 'X64' and platform.system() == 'Linux' and platform.machine() == 'x86_64'
        assert sys.version_info >= (3, 13)
        glibc = subprocess.check_output(['getconf', 'GNU_LIBC_VERSION'], text=True, timeout=10).strip()
        assert glibc == 'glibc 2.35', 'actual native Ubuntu22 libc required'
        release = dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
        assert release['ID'].strip('"') == 'ubuntu' and release['VERSION_ID'].strip('"') == '22.04'
        assert subprocess.check_output(['docker', 'info', '--format', '{{.OSType}} {{.Architecture}}'], text=True, timeout=15).strip() == 'linux x86_64'
        assert not subprocess.check_output(['docker', 'ps', '-q'], text=True, timeout=15).strip(), 'preserve other workloads'
        proof['native_runner'] = {'system': platform.system(), 'architecture': platform.machine(),
            'os': 'Ubuntu22.04', 'glibc': glibc, 'resources': resources(out.parent, minimum_available=policy['host_minimum_available_bytes'])}
        with lock.open('xb') as stream:
            os.chmod(lock, 0o600)
            lock_identity = lock.stat().st_ino
        supervisor = load('run-portable-ci.py')
        for name, seconds in [('fetch', 900), ('prepare', 1200), ('build', 3600), ('package', 180), ('runtime', 1500)]:
            row = {'phase': name, 'resources': resources(out.parent, 5 if name == 'runtime' else 10, policy['host_minimum_available_bytes'])}
            proof['phases'].append(row)
            write(public / 'ci-receipt.json', proof)
            private = out / ('supervise-' + name)
            private.mkdir(mode=0o700)
            supervision_public = private / 'public'
            supervision_public.mkdir(mode=0o700)
            remaining = 6900 - (time.monotonic() - began) - 180
            assert remaining > 0, 'finite115minute controller budget exhausted'
            try:
                supervisor.mac_check([sys.executable, '-B', __file__, '--inputs', args.inputs,
                    '--inputs-sha256', args.inputs_sha256, '--out', out, '--phase', name], private,
                    supervision_public, timeout=min(seconds, remaining), cleanup_seconds=180,
                    supervision_schema='meownero-native-linux-ci-owned-supervision/1', failure_label='native Linux ' + name)
                row['result'] = 'PASS'
            finally:
                cleanup_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGINT})
                cleanup_handlers = {s: signal.getsignal(s) for s in (signal.SIGTERM, signal.SIGINT)}
                try:
                    path = supervision_public / 'supervision.json'
                    if path.is_file():
                        receipt = json.loads(path.read_text())
                        write(public / (name + '-supervision.json'), receipt)
                        assert receipt['wrapper_reaped'] and all(p['removed'] for p in receipt['cleanup'])
                finally:
                    try:
                        for number, handler in cleanup_handlers.items():
                            signal.signal(number, handler)
                    finally:
                        signal.pthread_sigmask(signal.SIG_SETMASK, cleanup_mask)
            if name == 'build':
                build = json.loads((out / 'build/build-receipt.json').read_text())
                assert build['compiler_execution_substrate'] == 'NATIVE' and build['patches'] == []
                assert build['cleanup']['removed']
            if name == 'package':
                release = json.loads((out / 'package/meownero-vanguard-x86_64/release.json').read_text())
                assert tuple(map(int, release['minimum_glibc'].split('.'))) <= (2, 35), 'actual ABI does not support Ubuntu22 baseline'
        runtime = out / 'runtime'
        journey = json.loads((runtime / 'journey/result.json').read_text())
        controls = json.loads((runtime / 'controls/controls.json').read_text())
        check = json.loads((runtime / 'check-receipt.json').read_text())
        archive = out / 'package/meownero-vanguard-x86_64.tar.gz'
        assert check['result'] == 'PASS_NATIVE_ARCHIVE_JOURNEY' and check['cleanup']['removed']
        assert journey['result'] == 'PASS_NATIVE_JOURNEY' and journey['execution_substrate'] == 'NATIVE'
        assert journey['architecture'] == 'x86_64' and journey['upstream_commit'] == inputs['upstream_commit']
        assert journey['release_manifest_sha256'] == sha(out / 'package/meownero-vanguard-x86_64/release.json')
        assert journey['program_sha256'] == {n: release['files']['bin/' + n] for n in ('monerod', 'monero-wallet-cli', 'monero-wallet-rpc')}
        assert journey['cleanup'] and all(p['removed'] for p in journey['cleanup'])
        assert journey['receive_atomic'] == 5000000000000 and journey['subsequent_spend_atomic'] == 2000000000000
        assert journey['restore_matches'] and journey['cli_open_restored_wallet']
        assert len(journey['payments']) == 2 and all(p['rct_type'] == 7 and p['carrot_outputs'] for p in journey['payments'])
        assert controls['result'] == 'PASS_REFUSALS' and len(controls['cases']) == 10
        assert controls['release_manifest_sha256'] == journey['release_manifest_sha256']
        assert sha(archive) == check['archive_sha256']
        artifacts = out / 'artifacts'
        artifacts.mkdir(mode=0o700)
        shutil.copyfile(archive, artifacts / archive.name)
        (artifacts / 'SHA256SUMS').write_text(sha(archive) + '  ' + archive.name + '\n')
        proof.update(result='PASS_NATIVE_UBUNTU22_BUILD_ARCHIVE_JOURNEY_TEN_CONTROLS_PENDING_REVIEW',
                     archive_sha256=sha(archive), archive_bytes=archive.stat().st_size,
                     release_manifest_sha256=journey['release_manifest_sha256'], minimum_glibc=release['minimum_glibc'])
    except BaseException as error:
        proof['failure_type'] = type(error).__name__
        raise
    finally:
        # Public structured receipts only; no logs, Cargo caches or wallet state.
        cleanup_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGINT})
        cleanup_handlers = {s: signal.getsignal(s) for s in (signal.SIGTERM, signal.SIGINT)}
        try:
            for relative, name in [('fetch-receipt.json', 'fetch.json'), ('builder/preparation.json', 'builder.json'),
                ('build/build-receipt.json', 'build.json'), ('package/meownero-vanguard-x86_64/release.json', 'release.json'),
                ('package/meownero-vanguard-x86_64/license-coverage.json', 'license-coverage.json'),
                ('runtime/journey/result.json', 'journey.json'), ('runtime/controls/controls.json', 'controls.json'),
                ('runtime/check-receipt.json', 'check.json')]:
                path = out / relative
                if path.is_file() and not path.is_symlink():
                    write(public / name, public_worker_receipt(json.loads(path.read_text())) if name in ('build.json', 'builder.json') else json.loads(path.read_text()))
            try:
                if lock_identity is not None:
                    # Container wrappers must have removed their exact recorded children.
                    for relative, directory in [('builder/preparation.json', 'builder'),
                        ('build/build-receipt.json', 'build'), ('runtime/check-receipt.json', 'runtime')]:
                        path = out / relative
                        cidfiles = list((out / directory).glob('*.container.id')) + list((out / directory).glob('container.id'))
                        if cidfiles:
                            receipt = json.loads(path.read_text())
                            assert receipt['cleanup']['removed'], 'preserve lock: owned container cleanup unproven'
                            remaining = subprocess.check_output(['docker', 'ps', '-aq', '--no-trunc'], text=True, timeout=15).splitlines()
                            assert all(p.read_text().strip() not in remaining for p in cidfiles), 'recorded owned container remains'
                    assert lock.stat().st_ino == lock_identity and lock.stat().st_uid == os.getuid() and not lock.is_symlink()
                    lock.unlink()
                    proof['owned_ephemeral_lock_removed'] = True
            except BaseException as error:
                proof['result'] = 'FAIL'
                proof['cleanup_failure_type'] = type(error).__name__
                raise
            finally:
                proof['wall_seconds'] = round(time.monotonic() - began, 3)
                write(public / 'ci-receipt.json', proof)
                print(proof['result'])
        finally:
            try:
                for number, handler in cleanup_handlers.items():
                    signal.signal(number, handler)
            finally:
                signal.pthread_sigmask(signal.SIG_SETMASK, cleanup_mask)


if __name__ == '__main__':
    def cancelled(number, frame):
        raise RuntimeError('native Linux CI cancelled; stop owned phase and clean exact containers')
    signal.signal(signal.SIGTERM, cancelled)
    signal.signal(signal.SIGINT, cancelled)
    main()
