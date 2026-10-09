#!/usr/bin/env python3
"""Local Vanguard tester: inspect an accepted cache, run two short native gates."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import stat
import subprocess
import sys
import tarfile
import time
import uuid

ROOT = Path(__file__).resolve().parent.parent
PROFILE = json.loads((ROOT / 'vanguard/tester-profile.json').read_text())
PIN = json.loads((ROOT / 'vanguard/source-lock.json').read_text())
LOCK = Path('/tmp/meownero-swarm-20260912-heavy.lock').parent.resolve() / 'meownero-swarm-20260912-heavy.lock'
INPUTS = ('README.md', 'docs/vanguard-tester.md', 'research/current-evidence.md',
          'vanguard/source-lock.json', 'vanguard/tester-profile.json', 'vanguard/tester.py',
          'vanguard/tester-native.py', 'vanguard/test-tester-refusals.py',
          'vanguard/tester-public-schema.json', 'vanguard/test-tester-cleanup.py',
          'vanguard/daemon-p2p.py', 'vanguard/daemon-restore.py',
          'vanguard/verify-daemon-p2p.py', 'vanguard/verify-daemon-restore.py')
COMMON = ('events.jsonl', 'result.json', 'wire.jsonl', 'network-live.json', 'containment.json',
          'process-hashes.json', 'rpc-observations.jsonl')
FRAMES = ('duplicate-transaction', 'malformed-transaction', 'duplicate-block',
          'malformed-header', 'malformed-block')
PUBLIC = frozenset(['inputs.json', 'preflight.json', 'result.json', 'cleanup.json'] +
    [f'{gate}/{name}' for gate in ('p2p', 'restore') for name in
     ('receipt.json', 'build.memory', 'build.memory-events', 'build.cpu',
      'run1/run1.memory', 'run1/run1.memory-events', 'run1/run1.cpu')] +
    [f'{gate}/run1/public/{name}' for gate in ('p2p', 'restore') for name in COMMON] +
    ['p2p/run1/public/daemon1.log'] +
    [f'p2p/run1/public/frames/{name}.bin' for name in FRAMES])
DIRS = {str(p) for name in PUBLIC | {'EVIDENCE.sha256', 'export.json'}
        for p in Path(name).parents if str(p) != '.'}
GIB = 1024**3


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def sha(path):
    h = hashlib.sha256()
    with regular(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def safe_path(path):
    path = Path(os.path.abspath(path))
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'symlink path refused')
    return path


def regular(path):
    path = safe_path(path)
    require(stat.S_ISREG(path.stat().st_mode), f'regular file required: {path.name}')
    require(path.stat().st_nlink == 1, 'hard-linked file refused')
    return path


def fresh(path):
    path = safe_path(path)
    require(not path.exists(), 'existing output refused; use a new path and preserve failed attempts')
    require(path.parent.is_dir(), 'output parent must already exist')
    return path


def read(path):
    return json.loads(regular(path).read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def command(argv, timeout=30):
    result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    require(result.returncode == 0, f'prerequisite command failed: {argv[0]} {argv[1]}')
    return result.stdout.strip()


def docker(*args):
    return ['docker', '--context', PROFILE['docker_context'], *args]


@contextmanager
def heavy_lock():
    # Existing shared inode only. No install, lock replacement or global mutation.
    regular(LOCK)
    with LOCK.open('rb') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError('shared heavy lock busy; no workload started') from error
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def input_manifest():
    staged = ROOT / 'tester-inputs.json'
    if staged.exists():
        value = read(staged)
    else:
        require(not command(['git', '-C', str(ROOT), 'status', '--porcelain']), 'commit clean candidate first')
        value = {'candidate_commit': command(['git', '-C', str(ROOT), 'rev-parse', 'HEAD']),
                 'source_sha256': {name: sha(ROOT / name) for name in INPUTS}}
    require(set(value['source_sha256']) == set(INPUTS), 'package input set mismatch')
    require(len(value['candidate_commit']) == 40 and
            all(c in '0123456789abcdef' for c in value['candidate_commit']), 'candidate identity absent')
    require(value['source_sha256'] == {name: sha(ROOT / name) for name in INPUTS}, 'package source pins changed')
    return value


def cached_inputs(src):
    src = safe_path(src)
    require(sha(src / 'preparation/receipt.json') == PROFILE['preparation_sha256'], 'preparation pin mismatch')
    build = read(src / 'preparation/receipt.json')
    require(build['result'] == 'PASS_BUILD' and build['image'] == PROFILE['image'] and
            build['rustc'] == PIN['builder']['rustc'] and
            build['upstream_commit'] == PIN['upstream']['commit'] and
            build['submodules'] == PIN['upstream']['submodules'] and
            build['cargo_lock_sha256'] == PIN['rust']['cargo_lock_sha256'], 'source/toolchain provenance mismatch')
    up = src / 'monero-fcmp'
    require(command(['git', '-C', str(up), 'rev-parse', 'HEAD']) == PIN['upstream']['commit'], 'upstream pin mismatch')
    require(not command(['git', '-C', str(up), 'status', '--porcelain', '--untracked-files=no']), 'changed upstream source')
    for name, revision in PIN['upstream']['submodules'].items():
        require(command(['git', '-C', str(up / name), 'rev-parse', 'HEAD']) == revision, 'submodule pin mismatch')
        require(not command(['git', '-C', str(up / name), 'status', '--porcelain']), 'changed submodule source')
    require(sha(up / PIN['rust']['cargo_lock_path']) == PIN['rust']['cargo_lock_sha256'], 'Cargo.lock pin mismatch')
    for name, digest in PROFILE['toolchain_sha256'].items():
        require(sha(src / name) == digest, 'toolchain bytes mismatch')
    binaries = {}
    for name, expected in PROFILE['binary'].items():
        path = regular(up / 'build/vanguard/bin' / name)
        require(path.stat().st_size == expected['bytes'], 'binary size pin mismatch')
        with path.open('rb') as stream:
            header = stream.read(20)
        require(header[:5] == b'\x7fELF\x02' and int.from_bytes(header[18:20], 'little') == 183,
                'expected native Linux ARM64 ELF')
        binaries[name] = {'sha256': sha(path), 'bytes': path.stat().st_size}
        require(binaries[name] == expected == build['binary'][name], 'binary pin mismatch')
    return binaries


def supported_host():
    require((platform.system(), platform.machine(), platform.release(), platform.node().split('.')[0]) ==
            (PROFILE['system'], PROFILE['machine'], PROFILE['release'], PROFILE['host']),
            'unsupported profile; only verified build-mac Darwin 25.5.0 arm64 is supported')


def preflight(src, out=None):
    supported_host()
    inputs = input_manifest()
    if out is not None:
        fresh(out)
    binaries = cached_inputs(src)
    require(command(docker('context', 'inspect', 'colima', '--format', '{{.Endpoints.docker.Host}}')) ==
            PROFILE['docker_endpoint'], 'Docker context endpoint mismatch')
    require(command(docker('version', '--format', '{{.Client.Version}} {{.Server.Version}} {{.Server.Os}} {{.Server.Arch}}')) ==
            f"{PROFILE['docker_client']} {PROFILE['docker_server']} linux arm64", 'Docker version/profile mismatch')
    require(command(docker('image', 'inspect', PROFILE['image'], '--format', '{{.Id}} {{.Architecture}} {{.Os}}')) ==
            PROFILE['image'] + ' arm64 linux', 'pinned local image missing or incompatible; no pull attempted')
    require(not command(docker('ps', '-q')), 'Docker busy; wait for other containers, do not stop them')
    memory = command(['colima', 'ssh', '--', 'cat', '/proc/meminfo'])
    available = int(next(row.split()[1] for row in memory.splitlines() if row.startswith('MemAvailable:'))) * 1024
    cpu, total = map(int, command(docker('info', '--format', '{{.NCPU}} {{.MemTotal}}')).split())
    disk = shutil.disk_usage(out.parent if out else ROOT).free
    require(cpu >= 2 and total >= 5 * GIB and available >= 5 * GIB and disk >= 5 * GIB,
            'requires 2 VM CPUs, 5 GiB available VM memory and host disk; no settings changed')
    with heavy_lock():
        pass
    return {'result': 'PASS_PREFLIGHT', 'profile': PROFILE, 'inputs': inputs,
            'binary': binaries, 'available_vm_bytes': available, 'vm_cpus': cpu,
            'vm_memory_bytes': total, 'available_disk_bytes': disk,
            'toolchain_check': 'pinned preparation and installed rustc/cargo hashes; runtime versions checked during run',
            'lock': str(LOCK), 'checked_utc': datetime.now(timezone.utc).isoformat()}


def package(out):
    inputs = input_manifest()
    out = fresh(out)
    out.mkdir(mode=0o700)
    for name in INPUTS:
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    write(out / 'tester-inputs.json', inputs)
    print('PASS_PACKAGE', inputs['candidate_commit'])


def manifest(out, names, filename):
    (out / filename).write_text(''.join(f'{sha(out / name)}  {name}\n' for name in sorted(names)))


def owned_identity(cidfile, invocation):
    """A fresh cidfile plus an exact ID/image/invocation-label match proves ownership."""
    if not cidfile.exists():
        return None
    identity = regular(cidfile).read_text().strip()
    require(len(identity) == 64 and all(c in '0123456789abcdef' for c in identity),
            'invalid owned container ID')
    observed = json.loads(command(docker('inspect', identity, '--format',
        '{{json .Id}}'), timeout=15))
    label = command(docker('inspect', identity, '--format',
        '{{index .Config.Labels "meownero.tester.invocation"}}'), timeout=15)
    image = command(docker('inspect', identity, '--format', '{{.Image}}'), timeout=15)
    require(observed == identity and label == invocation and image == PROFILE['image'],
            'container ownership mismatch; no destructive cleanup allowed')
    return identity


def cleanup_container(identity, name, proc):
    """Attempt each bounded operation independently; never fall back to a name."""
    row = {'name': name, 'container_id': identity, 'stop_exit': None, 'inspect_exit': None,
           'remove_exit': None, 'absence_exit': None, 'container_absent': None,
           'private_state_retained': True, 'errors': []}
    final_state = None

    def attempt(operation, argv, timeout):
        try:
            observed = subprocess.run(argv, capture_output=True, timeout=timeout)
            row[operation + '_exit'] = observed.returncode
            if observed.returncode != 0:
                row['errors'].append({'operation': operation, 'error': 'nonzero_exit'})
            return observed
        except Exception as error:
            row['errors'].append({'operation': operation, 'error': type(error).__name__})

    if identity is not None:
        attempt('stop', docker('stop', '--time=20', identity), 35)
        observed = attempt('inspect', docker('inspect', identity, '--format', '{{json .State}}'), 15)
        if observed is not None and observed.returncode == 0:
            try:
                final_state = json.loads(observed.stdout)
            except (ValueError, UnicodeError):
                row['errors'].append({'operation': 'inspect', 'error': 'invalid_state'})
        attempt('remove', docker('rm', '-f', identity), 20)
        # Listing exact IDs distinguishes actual absence from an inspect transport failure.
        observed = attempt('absence', docker('ps', '-aq', '--no-trunc', '--filter', 'id=' + identity), 15)
        if observed is not None and observed.returncode == 0:
            row['container_absent'] = not observed.stdout.strip()
    if proc is not None:
        try:
            proc.wait(timeout=10)
        except Exception as error:
            row['errors'].append({'operation': 'client_wait', 'error': type(error).__name__})
            # Only our Docker attach client, never other workloads or broad processes.
            try:
                proc.kill()
                proc.wait(timeout=5)
            except Exception as error:
                row['errors'].append({'operation': 'client_reap', 'error': type(error).__name__})
    return row, final_state


def run(src, out):
    pre = preflight(src, out)
    out = fresh(out)
    src = safe_path(src)
    require(src not in out.parents and out not in src.parents, 'output overlaps read-only cache')
    with heavy_lock():
        # Recheck admission while holding the shared lock across both scenarios.
        require(not command(docker('ps', '-q')), 'Docker busy after lock acquisition')
        out.mkdir(mode=0o700)
        write(out / 'preflight.json', pre)
        write(out / 'inputs.json', pre['inputs'])
        result = {'result': 'FAIL', 'gates': {'p2p': 'NOT_RUN', 'restore': 'NOT_RUN'}, 'whole_deadline_seconds': 2500,
                  'private_state': 'retained in owned mode0700 output; never export recursively'}
        cleanup = []
        invocation = uuid.uuid4().hex
        began = time.monotonic()
        previous = {}

        def interrupted(signum, frame):
            raise RuntimeError('tester interrupted; cleaning only owned container')

        for sig in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM, signal.SIGALRM):
            previous[sig] = signal.signal(sig, interrupted)
        # Bound the whole workload, including source rechecks and subprocess setup.
        # Cleanup has its own bounded stop/inspect/remove calls after this timer fires.
        signal.setitimer(signal.ITIMER_REAL, 2500)
        try:
            for gate in ('p2p', 'restore'):
                require(time.monotonic() - began < 2380, 'whole runner deadline')
                stage = out / gate
                stage.mkdir()
                receipt = {'schema': f'meownero-vanguard-daemon-{gate}/1',
                    'candidate_commit': pre['inputs']['candidate_commit'],
                    'source_sha256': pre['inputs']['source_sha256'], 'upstream_commit': PIN['upstream']['commit'],
                    'builder_image': PROFILE['image'], 'rustc': PIN['builder']['rustc'],
                    'binary': pre['binary'], 'commands': [], 'attach_commands': [], 'metrics': {},
                    'build_mode': 'read-only cached binary inspection; no compilation'}
                result['gates'][gate] = 'FAIL_CACHE_INSPECTION'
                for label in ('build', 'run1'):
                    work = stage if label == 'build' else stage / label
                    work.mkdir(exist_ok=True)
                    if label == 'run1':
                        result['gates'][gate] = 'FAIL_NATIVE'
                    name = f'tjs1870-{invocation}-{gate}-{label}'
                    cidfile = work / 'container.cid'
                    body = ('uname -m; /cache/rust/bin/rustc -V; /cache/rust/bin/cargo -V; '
                            '/src/build/vanguard/bin/monerod --version; /src/build/vanguard/bin/monero-wallet-rpc --version'
                            if label == 'build' else f'timeout --signal=TERM --kill-after=30 1100 python3 -B /harness/tester-native.py {gate}')
                    script = (f"trap 'cat /sys/fs/cgroup/memory.peak > /out/{label}.memory; "
                              f"cat /sys/fs/cgroup/memory.events > /out/{label}.memory-events; "
                              f"cat /sys/fs/cgroup/cpu.stat > /out/{label}.cpu' EXIT\n"
                              'mkdir -m700 /out/private-home\n' + body)
                    argv = docker('create', '--name', name, '--cidfile', str(cidfile),
                        '--label', 'meownero.tester.invocation=' + invocation, '--pull=never', '--network=none',
                        '--cap-drop=ALL', '--security-opt=no-new-privileges', '--cpus=2', '--memory=4g',
                        '--memory-swap=4g', '--pids-limit=256', '--ulimit', 'core=0',
                        f'--tmpfs=/run/vanguard:rw,noexec,nosuid,nodev,size=1m,mode=0700,uid={os.getuid()},gid={os.getgid()}',
                        '-u', f'{os.getuid()}:{os.getgid()}',
                        '-v', f'{src}:/cache:ro', '-v', f'{src / "monero-fcmp"}:/src:ro',
                        '-v', f'{ROOT / "vanguard"}:/harness:ro', '-v', f'{work}:/out',
                        '-e', 'HOME=/out/private-home', '-w', '/out', PROFILE['image'], 'bash', '-euc', script)
                    receipt['commands'].append(argv)
                    proc = None
                    identity = None
                    code = 125
                    started = time.monotonic()
                    try:
                        collision = command(docker('ps', '-aq', '--no-trunc', '--filter', 'name=^/' + name + '$'))
                        require(not collision, 'container name collision refused; existing state preserved')
                        # Docker creates the cidfile in this fresh owned directory. A failed
                        # create/name conflict never authorizes cleanup of a container by name.
                        command(argv, timeout=30)
                        identity = owned_identity(cidfile, invocation)
                        require(identity is not None, 'owned container identity unavailable')
                        with (work / f'{label}.docker.log').open('wb') as log:
                            attach = docker('start', '-a', identity)
                            receipt['attach_commands'].append(attach)
                            proc = subprocess.Popen(attach, stdout=log, stderr=subprocess.STDOUT)
                            for _ in range(100):
                                observed = subprocess.run(docker('inspect', identity, '--format',
                                    '{{json .Id}}\n{{json .Image}}\n{{json .State}}\n{{json .HostConfig}}\n{{json .Mounts}}'),
                                    capture_output=True, timeout=10)
                                if observed.returncode == 0:
                                    (work / 'container-live.jsonl').write_bytes(observed.stdout)
                                    break
                                require(proc.poll() is None, 'container failed to start')
                                time.sleep(0.1)
                            else:
                                raise RuntimeError('live container identity unavailable')
                            try:
                                code = proc.wait(timeout=min(60 if label == 'build' else 1160,
                                                            2410 - (time.monotonic() - began)))
                            except subprocess.TimeoutExpired:
                                code = 124
                                raise RuntimeError('native gate deadline exceeded')
                    finally:
                        signal.setitimer(signal.ITIMER_REAL, 0)
                        ownership_errors = []
                        if identity is None and cidfile.exists():
                            try:
                                identity = owned_identity(cidfile, invocation)
                            except Exception as error:
                                ownership_errors.append({'operation': 'ownership', 'error': type(error).__name__})
                        row, final_state = cleanup_container(identity, name, proc)
                        row['errors'] = ownership_errors + row['errors']
                        cleanup.append(row)
                        if final_state is not None:
                            write(work / 'container-final.json', final_state)
                        receipt['metrics'][label] = {'exit': code, 'wall_seconds': time.monotonic() - started,
                            'container_id': identity, 'container_absent': row['container_absent'],
                            'cleanup_errors': row['errors'], 'container_final': final_state}
                        write(stage / 'receipt.json', receipt)
                        signal.setitimer(signal.ITIMER_REAL, max(0.001, 2500 - (time.monotonic() - began)))
                    require(code == 0 and row['container_absent'] is True and row['remove_exit'] == 0 and
                            not row['errors'], 'gate failed; keep output and inspect private logs')
                    counts = dict(line.split() for line in (work / f'{label}.memory-events').read_text().splitlines())
                    require(not int(counts['oom']) and not int(counts['oom_kill']), 'container OOM')
                    if label == 'build':
                        text = (work / 'build.docker.log').read_text()
                        require('aarch64' in text and PIN['builder']['rustc'] in text, 'cached native runtime version mismatch')
                require(read(stage / 'run1/public/result.json')['result'] == 'PASS', 'scenario did not pass')
                result['gates'][gate] = 'PASS_NATIVE'
            require(time.monotonic() - began < 2500, 'whole runner deadline exceeded')
            require(cached_inputs(src) == pre['binary'] and input_manifest() == pre['inputs'],
                    'cache or package inputs changed during workload')
            result['read_only_inputs_unchanged'] = True
            result['result'] = 'PASS_NATIVE_JOURNEY'
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            result['wall_seconds'] = time.monotonic() - began
            write(out / 'result.json', result)
            write(out / 'cleanup.json', cleanup)
            names = PUBLIC - {'p2p/run1/public/daemon1.log'}
            present = {name for name in names if (out / name).is_file()}
            # Raw parser log is retained privately; exporter emits parser markers only.
            if (out / 'p2p/run1/public/daemon1.log').is_file():
                present.add('p2p/run1/public/daemon1.log')
            manifest(out, present, 'EVIDENCE.sha256')
            manifest(out, {'inputs.json'}, 'INPUTS.sha256')
            for sig, handler in previous.items():
                signal.signal(sig, handler)
        print(result['result'], 'private output:', out)


def manifest_entries(out):
    entries = {}
    for line in regular(out / 'EVIDENCE.sha256').read_text().splitlines():
        digest, name = line.split('  ', 1)
        require(name in PUBLIC and name not in entries, 'unsafe/non-allowlisted manifest entry')
        require(len(digest) == 64 and all(c in '0123456789abcdef' for c in digest), 'bad digest')
        require(sha(out / name) == digest, 'evidence changed: ' + name)
        entries[name] = digest
    require(set(entries) == PUBLIC, 'incomplete journey; failed output must remain private')
    return entries


def private_fields(value):
    if isinstance(value, dict):
        for key, item in value.items():
            require(key.lower() not in {'seed', 'mnemonic', 'private_key', 'spend_key', 'view_key',
                'password', 'token', 'credential', 'authorization', 'secret', 'tx_key', 'tx_metadata'}, 'secret-bearing evidence refused')
            private_fields(item)
    elif isinstance(value, list):
        for item in value:
            private_fields(item)


def public_fields(value, name):
    """Validate frozen field/type shapes, including JSON encoded inside native RPC."""
    schema = read(ROOT / 'vanguard/tester-public-schema.json')
    key = name + '#' + str(value.get('method')) if name.endswith('/rpc-observations.jsonl') else name
    require(key in schema['roots'], 'unknown public evidence schema')

    def check(item, node_id):
        node = schema['nodes'][node_id]
        kind = ('object' if isinstance(item, dict) else 'array' if isinstance(item, list) else
                'boolean' if isinstance(item, bool) else 'number' if isinstance(item, (int, float)) else
                'null' if item is None else 'string')
        require(kind in node['types'], 'non-public evidence type refused')
        if kind == 'object':
            require(set(item) <= set(node['fields']), 'unknown public evidence field refused')
            for field, child in item.items():
                check(child, node['fields'][field])
        elif kind == 'array':
            require(not item or node['items'] is not None, 'unknown public evidence array payload refused')
            for child in item:
                check(child, node['items'])
        elif kind == 'string' and 'json' in node:
            check(json.loads(item), node['json'])
    check(value, schema['roots'][key])


def public_bytes(path, name):
    raw = regular(path).read_bytes()
    require(len(raw) <= 32 * 1024**2, 'oversized export member')
    require(name.endswith('.bin') or b'\0' not in raw, 'binary/database evidence refused')
    if name.endswith('.bin'):
        import struct
        require(len(raw) >= 33 and int.from_bytes(raw[:8], 'little') == 0x0101010101012101 and
                int.from_bytes(raw[8:16], 'little') == len(raw) - 33, 'non-Levin bytes refused')
    elif name.endswith('.json'):
        value = json.loads(raw)
        private_fields(value)
        public_fields(value, name)
    elif name.endswith('.jsonl'):
        for line in raw.splitlines():
            value = json.loads(line)
            private_fields(value)
            public_fields(value, name)
    elif name.endswith('.log'):
        # No free-form log payload crosses this boundary. Preserve parser counts and raw digest.
        text = raw.decode('utf-8')
        markers = ('Failed to parse transaction from blob', 'Failed to parse block from blob')
        raw = ''.join((marker + '\n') * text.count(marker) for marker in markers).encode()
    else:
        require(b'\0' not in raw, 'binary evidence refused')
        if name.endswith('.memory'):
            require(raw.decode().strip().isdigit(), 'non-memory payload refused')
        else:
            require(all(len(row.split()) == 2 and row.split()[1].isdigit() for row in raw.decode().splitlines()),
                    'non-counter payload refused')
    return raw


def export(source, out, archive):
    source = safe_path(source)
    out, archive = fresh(out), fresh(archive)
    require(source != out and source not in out.parents and out not in source.parents and
            archive != out and out not in archive.parents and source not in archive.parents,
            'export paths overlap')
    original = manifest_entries(source)
    # Validate every selected member before creating output. Ignore unlisted private files.
    values = {name: public_bytes(source / name, name) for name in sorted(PUBLIC)}
    out.mkdir(mode=0o700)
    for name, raw in values.items():
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    write(out / 'export.json', {'result': 'PASS_ALLOWLISTED_EXPORT', 'raw_sha256': original,
        'parser_log_projection': 'p2p/run1/public/daemon1.log contains only recognized parser markers',
        'excluded': 'all unlisted paths, including wallet/chain/ring databases and raw logs'})
    manifest(out, PUBLIC | {'export.json'}, 'EVIDENCE.sha256')
    validate_public(out)
    with archive.open('xb') as raw, gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0) as zipped:
        with tarfile.open(fileobj=zipped, mode='w') as tar:
            for name in sorted(PUBLIC | {'export.json', 'EVIDENCE.sha256'}):
                path = out / name
                info = tarfile.TarInfo(name)
                info.size, info.mode, info.mtime = path.stat().st_size, 0o644, 0
                with path.open('rb') as stream:
                    tar.addfile(info, stream)
    print('PASS_ALLOWLISTED_EXPORT', sha(archive), archive.stat().st_size)


def validate_public(out):
    out = safe_path(out)
    found = set()
    for path in out.rglob('*'):
        name = str(path.relative_to(out))
        require(not path.is_symlink(), 'symlink export refused')
        if path.is_dir():
            require(name in DIRS, 'unlisted export directory')
        else:
            regular(path)
            require(name in PUBLIC | {'export.json', 'EVIDENCE.sha256'}, 'unlisted export file')
            found.add(name)
    require(found == PUBLIC | {'export.json', 'EVIDENCE.sha256'}, 'export member set mismatch')
    entries = {}
    for line in (out / 'EVIDENCE.sha256').read_text().splitlines():
        digest, name = line.split('  ', 1)
        require(name in PUBLIC | {'export.json'} and name not in entries, 'unsafe export manifest')
        require(sha(out / name) == digest, 'export manifest mismatch')
        entries[name] = digest
    require(set(entries) == PUBLIC | {'export.json'}, 'export manifest set mismatch')
    for name in PUBLIC:
        require(public_bytes(out / name, name) == (out / name).read_bytes(), 'noncanonical public payload')
    public_bytes(out / 'export.json', 'export.json')


def verify_rpc(work, gate):
    rows = [json.loads(line) for line in (work / 'rpc-observations.jsonl').read_text().splitlines()]
    result = read(work / 'result.json')
    payments = [result['txid']] if gate == 'p2p' else [result['stable_txid'], result['restored_spend_txid']]
    for txid in payments:
        constructions = [r for r in rows if r['method'] == 'transfer' and
                         r['response'].get('result', {}).get('tx_hash') == txid]
        require(len(constructions) == 1, 'payment construction missing or duplicated')
        construction = constructions[0]
        params, sent = construction['request']['params'], construction['response']['result']
        expected = 10**12 if gate == 'p2p' else 5 * 10**12 if txid == result['stable_txid'] else 2 * 10**12
        require(len(params['destinations']) == 1 and params['destinations'][0]['amount'] == expected and
                sent['fee'] > 0, 'native payment amount or fee mismatch')
        native = [tx for row in rows if row['path'] == 'get_transactions'
                  for tx in row['response'].get('txs', []) if tx['tx_hash'] == txid]
        require(native, 'native transaction observation absent')
        for tx in native:
            decoded = json.loads(tx['as_json'])
            require(decoded['rct_signatures']['type'] == 7 and decoded['vout'] and
                    all(list(v['target']) == ['carrot_v1'] for v in decoded['vout']), 'intended native crypto absent')
        if gate == 'restore':
            port = 19190 if txid == result['stable_txid'] else 19090
            addresses = {r['response']['result']['address'] for r in rows
                         if r['method'] == 'get_address' and r['port'] == port}
            require(params['destinations'][0]['address'] in addresses, 'payment destination not receiver address')
    if gate == 'restore':
        restores = [r for r in rows if r['method'] == 'restore_deterministic_wallet' and r['port'] == 19093]
        require(len(restores) == 1 and restores[0]['response']['result']['address'] in
                {r['response']['result']['address'] for r in rows if r['method'] == 'get_address' and r['port'] == 19190},
                'native restored address mismatch')
        credits = [tx for r in rows if r['method'] == 'incoming_transfers' and r['port'] == 19190
                   for tx in r['response']['result'].get('transfers', []) if tx['tx_hash'] == result['stable_txid']]
        require(credits and all(tx['amount'] == 5 * 10**12 for tx in credits) and
                any(tx['spent'] for tx in credits), 'native receive/later spend binding absent')


def verify(out):
    validate_public(out)
    inputs = read(out / 'inputs.json')
    require(set(inputs['source_sha256']) == set(INPUTS), 'input set mismatch')
    commit = inputs['candidate_commit']
    subprocess.run(['git', '-C', str(ROOT), 'merge-base', '--is-ancestor', commit, 'HEAD'], check=True)
    for name, digest in inputs['source_sha256'].items():
        blob = subprocess.check_output(['git', '-C', str(ROOT), 'show', f'{commit}:{name}'])
        require(hashlib.sha256(blob).hexdigest() == digest == sha(ROOT / name), 'exact candidate source mismatch')
    require(read(out / 'result.json')['result'] == 'PASS_NATIVE_JOURNEY', 'journey failed')
    require(read(out / 'result.json')['read_only_inputs_unchanged'], 'input preservation check absent')
    require(read(out / 'preflight.json')['profile'] == PROFILE, 'unsupported receipt profile')
    cleanup = read(out / 'cleanup.json')
    identities = [row['container_id'] for row in cleanup]
    require(len(cleanup) == 4 and len(set(identities)) == 4 and
            all(len(identity) == 64 and all(c in '0123456789abcdef' for c in identity) for identity in identities) and
            all(row['container_absent'] is True and row['remove_exit'] == 0 and
                row['absence_exit'] == 0 and not row['errors'] for row in cleanup),
            'owned cleanup incomplete')
    # Legacy reconcilers are called unchanged. The ARM adapter changes only the explicit
    # executable baseline in its private module instance, after checking the fixed profile.
    # Their historical x86 CLI behavior and source bytes remain untouched.
    import tempfile
    with tempfile.TemporaryDirectory(prefix='tester-verify-', dir=out.parent) as temp:
        for gate in ('p2p', 'restore'):
            stage = Path(temp) / gate
            shutil.copytree(out / gate, stage)
            receipt = read(stage / 'receipt.json')
            require(receipt['binary'] == PROFILE['binary'] and receipt['source_sha256'] == inputs['source_sha256'] and
                    receipt['candidate_commit'] == commit and receipt['builder_image'] == PROFILE['image'], 'gate pin mismatch')
            require(set(receipt['metrics']) == {'build', 'run1'} and len(receipt['commands']) == 2 and
                    len(receipt['attach_commands']) == 2, 'native lifecycle receipt incomplete')
            for number, label in enumerate(('build', 'run1')):
                identity = receipt['metrics'][label]['container_id']
                owned = [row for row in cleanup if row['container_id'] == identity]
                create = receipt['commands'][number]
                require(len(owned) == 1 and create[:4] == docker('create') and
                        '--cidfile' in create and '--label' in create and '--name' in create and
                        create[create.index('--name') + 1] == owned[0]['name'] and
                        receipt['attach_commands'][number] == docker('start', '-a', identity),
                        'owned container lifecycle binding mismatch')
            for label, metric in receipt['metrics'].items():
                require(metric['exit'] == 0 and metric['container_absent'] and metric['container_final'] and
                        not metric['cleanup_errors'] and metric['container_id'] in identities and
                        not metric['container_final']['OOMKilled'] and metric['container_final']['ExitCode'] == 0,
                        'native exit/OOM/cleanup mismatch')
                peak = int((stage / ('' if label == 'build' else label) / f'{label}.memory').read_text())
                require(0 < peak <= 4 * GIB, 'memory peak/cap mismatch')
            processes = read(stage / 'run1/public/process-hashes.json')
            require(len(processes) == (3 if gate == 'p2p' else 7) and
                    all(row['sha256'] == PROFILE['binary'][row['binary']]['sha256'] for row in processes),
                    'running native process hash mismatch')
            verify_rpc(stage / 'run1/public', gate)
            names = {str(p.relative_to(stage)) for p in stage.rglob('*') if p.is_file()}
            manifest(stage, names, 'MANIFEST.sha256')
            spec = importlib.util.spec_from_file_location('tester_legacy_' + gate, ROOT / f'vanguard/verify-daemon-{gate}.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if gate == 'restore':
                module.EXPECTED_BINARIES = PROFILE['binary']
            module.verify(stage)
    print('PASS_TESTER_JOURNEY_RECONCILIATION UNVERIFIED_LIVE_TIPS')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    for action in ('preflight', 'run'):
        p = sub.add_parser(action)
        p.add_argument('--src', type=Path, default=Path(PROFILE['cache']))
        p.add_argument('--out', type=Path, required=action == 'run')
    p = sub.add_parser('package'); p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('export'); p.add_argument('source', type=Path)
    p.add_argument('--out', type=Path, required=True); p.add_argument('--archive', type=Path, required=True)
    p = sub.add_parser('verify'); p.add_argument('source', type=Path)
    args = parser.parse_args()
    try:
        if args.action == 'preflight': print(json.dumps(preflight(args.src, args.out), indent=2))
        elif args.action == 'run': run(args.src, args.out)
        elif args.action == 'package': package(args.out)
        elif args.action == 'export': export(args.source, args.out, args.archive)
        else: verify(args.source)
    except Exception as error:
        print('FAIL_TESTER', str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
