#!/usr/bin/env python3
"""Run a disposable native Vanguard payment, recovery and subsequent spend."""
import argparse
import os
from contextlib import contextmanager
if os.name == 'posix':
    import fcntl
import hashlib
import json
from pathlib import Path
import platform
import re
import signal
import shutil
import socket
import stat
import subprocess
import tempfile
import time
import urllib.request
import sys

WINDOWS = platform.system() == 'Windows'
if WINDOWS:
    import portable_windows

ROOT = Path(__file__).resolve().parent
UPSTREAM = 'e151643c5269c83bf24a83b2548e2493876026b2'
CARGO_LOCK = '6a8e9217b94169e26a8f595cb528d72c19dc2f5484e903c57328c594d62f8239'
PROGRAMS = ('monerod', 'monero-wallet-cli', 'monero-wallet-rpc')
COIN = 10**12


class JourneyInterrupted(Exception):
    """Fatal cancellation or deadline, distinct from retryable RPC timeouts."""


def child_environment():
    env = dict(os.environ)
    for name in ('LD_PRELOAD', 'LD_AUDIT', 'DYLD_INSERT_LIBRARIES', 'DYLD_ROOT_PATH',
                 'DYLD_FALLBACK_LIBRARY_PATH'):
        env.pop(name, None)
    if WINDOWS:
        env['PATH'] = str(Path(env['SYSTEMROOT']) / 'System32')
    else:
        env['DYLD_LIBRARY_PATH' if platform.system() == 'Darwin' else 'LD_LIBRARY_PATH'] = str(ROOT / 'lib')
    return env


def executable(name):
    return ROOT / 'bin' / (name + ('.exe' if WINDOWS else ''))


def mac_physical_architecture():
    require(platform.system() == 'Darwin', 'physical Mac detection requires Darwin')

    def optional_oid(name):
        result = subprocess.run(['/usr/sbin/sysctl', '-n', name], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return result.stdout.strip()
        require(result.returncode == 1 and not result.stdout.strip() and
                result.stderr.strip() == "sysctl: unknown oid '" + name + "'", 'failed Mac architecture query: ' + name)
        return None

    arm = optional_oid('hw.optional.arm64')
    require(arm in (None, '0', '1'), 'could not identify physical Mac architecture')
    if arm == '1':
        # Preserve explicit Apple Silicon / translated Intel archive semantics.
        return 'aarch64'
    vendor = subprocess.check_output(['/usr/sbin/sysctl', '-n', 'machdep.cpu.vendor'], text=True, timeout=10).strip()
    kernel = subprocess.check_output(['/usr/bin/uname', '-m'], text=True, timeout=10).strip()
    translated = optional_oid('sysctl.proc_translated')
    require(vendor == 'GenuineIntel' and platform.machine() == 'x86_64' and kernel == 'x86_64' and
            translated in (None, '0'), 'physical Intel evidence missing, conflicting or translated')
    return 'x86_64'


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def safe(path):
    path = Path(os.path.abspath(path))
    require(not any(p.is_symlink() or (os.path.lexists(p) and getattr(p.lstat(), 'st_file_attributes', 0) & 0x400)
                    for p in (path, *path.parents)), 'symlink path refused')
    return path


def sha(path):
    path = safe(path)
    info = path.stat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'nonregular or hard-linked input refused')
    with path.open('rb') as stream:
        digest = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
        return digest.hexdigest()


def preflight(translated_macos_x64=False):
    sha(ROOT / 'release.json')
    manifest = json.loads(safe(ROOT / 'release.json').read_text())
    require(manifest['upstream_commit'] == UPSTREAM and manifest['cargo_lock_sha256'] == CARGO_LOCK,
            'wrong source pin')
    require(manifest['system'] in ('Linux', 'Darwin', 'Windows') and platform.system() == manifest['system'],
            'wrong operating system')
    machine = {'amd64': 'x86_64', 'arm64': 'aarch64'}.get(platform.machine(), platform.machine())
    if WINDOWS:
        require(sys.version_info >= (3, 13), 'Windows requires Python 3.13 or later for private directory permissions')
        version = sys.getwindowsversion()
        require(version.major >= 10 and version.build >= 16299, 'Windows 10 version 1709 or later required')
        machine = portable_windows.native_architecture()
    elif manifest['system'] == 'Darwin':
        machine = mac_physical_architecture()
    translated = translated_macos_x64 and manifest['system'] == 'Darwin' and machine == 'aarch64' and manifest['architecture'] == 'x86_64'
    require(not translated_macos_x64 or translated, 'wrong architecture: translation requires an x86_64 Mac archive on Apple Silicon')
    if translated:
        subprocess.run(['/usr/sbin/pkgutil', '--pkg-info', 'com.apple.pkg.RosettaUpdateAuto'], check=True, capture_output=True, timeout=10)
        machine = 'x86_64'
    require(machine == manifest['architecture'] or
            (WINDOWS and machine == 'x86_64' and manifest['architecture'] == 'i686'), 'wrong architecture')
    if WINDOWS:
        require(manifest['architecture'] == 'i686' or sys.maxsize > 2**32,
                '64-bit Windows programs require 64-bit CPython for native module verification')
    if manifest['system'] == 'Linux':
        libc, version = platform.libc_ver()
        require(libc == 'glibc' and tuple(map(int, version.split('.'))) >=
                tuple(map(int, manifest['minimum_glibc'].split('.'))), 'glibc ABI too old or unsupported')
    elif manifest['system'] == 'Darwin':
        require(tuple(map(int, platform.mac_ver()[0].split('.'))) >=
                tuple(map(int, manifest['minimum_macos'].split('.'))), 'macOS ABI too old')
    expected = set(manifest['files']) | {'release.json'}
    paths = list(ROOT.rglob('*'))
    require(not any(p.is_symlink() or getattr(p.lstat(), 'st_file_attributes', 0) & 0x400 for p in paths), 'package symlink refused')
    actual = {p.relative_to(ROOT).as_posix() for p in paths if not p.is_dir()}
    require(expected == actual, 'package file set mismatch')
    for name, digest in manifest['files'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts, 'invalid package path')
        require(sha(ROOT / name) == digest, 'package hash mismatch: ' + name)
    for name in PROGRAMS:
        binary = executable(name)
        with binary.open('rb') as stream:
            header = stream.read(20)
        if manifest['system'] == 'Linux':
            valid = header[:6] == b'\x7fELF\x02\x01' and int.from_bytes(header[18:20], 'little') == \
                {'x86_64': 62, 'aarch64': 183}[machine]
        elif manifest['system'] == 'Darwin':
            valid = header[:4] == b'\xcf\xfa\xed\xfe' and int.from_bytes(header[4:8], 'little') == \
                {'x86_64': 0x1000007, 'aarch64': 0x100000c}[machine] and int.from_bytes(header[12:16], 'little') == 2
        else:
            with binary.open('rb') as stream:
                stream.seek(60)
                offset = int.from_bytes(stream.read(4), 'little')
                stream.seek(offset)
                pe = stream.read(26)
            valid = header[:2] == b'MZ' and pe[:4] == b'PE\0\0' and int.from_bytes(pe[4:6], 'little') == \
                {'i686': 0x14c, 'x86_64': 0x8664, 'aarch64': 0xaa64}[manifest['architecture']] and \
                int.from_bytes(pe[24:26], 'little') == (0x10b if manifest['architecture'] == 'i686' else 0x20b)
        require(valid, 'wrong binary format or target')
        require(os.access(binary, os.X_OK), 'binary is not executable')
        if WINDOWS:
            job = portable_windows.Job(seconds=20)
            try:
                with tempfile.TemporaryFile() as stream:
                    process = job.spawn(binary, ['--version'], stream, child_environment(), ROOT)
                    require(process.wait(timeout=20) == 0, 'program startup failed: ' + name)
            finally:
                job.close()
        else:
            result = subprocess.run([str(binary), '--version'], capture_output=True, timeout=20, env=child_environment())
            require(result.returncode == 0, 'program startup failed: ' + name)
    return manifest


@contextmanager
def lock():
    if WINDOWS:
        with portable_windows.lock(safe):
            yield
        return
    temp_root = Path(tempfile.gettempdir())
    if platform.system() == 'Darwin':
        # macOS reports /var/... while its canonical system temp root is
        # /private/var/.... Keep the lock leaf and user outputs strict.
        temp_root = temp_root.resolve(strict=True)
    path = safe(temp_root / ('meownero-vanguard-tester-' + str(os.getuid()) + '.lock'))
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(descriptor)
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == os.getuid(),
                'unsafe tester lock')
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError('tester busy; no processes started') from error
        yield
    finally:
        os.close(descriptor)


def rpc(port, method, params=None):
    # Disable inherited proxies even for loopback. Seeds never enter a log.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request = urllib.request.Request('http://127.0.0.1:' + str(port) + '/json_rpc',
        json.dumps({'jsonrpc': '2.0', 'id': '0', 'method': method, 'params': params or {}}).encode(),
        {'Content-Type': 'application/json'})
    with opener.open(request, timeout=90) as response:
        value = json.load(response)
    require('error' not in value, 'RPC failed: ' + method)
    return value['result']


def available_memory():
    if WINDOWS:
        return portable_windows.available_memory()
    if platform.system() == 'Linux':
        return int(next(row.split()[1] for row in Path('/proc/meminfo').read_text().splitlines()
                        if row.startswith('MemAvailable:'))) * 1024
    stats = subprocess.check_output(['/usr/bin/vm_stat'], text=True, timeout=10)
    page_size = int(re.search(r'page size of (\d+) bytes', stats)[1])
    pages = re.findall(r'^Pages (?:free|inactive|speculative):\s+(\d+)\.', stats, re.MULTILINE)
    require(len(pages) == 3, 'could not inspect available native memory')
    return sum(map(int, pages)) * page_size


def run(out, translated_macos_x64=False, deadline_seconds=1200):
    out = safe(out)
    require(out.parent.is_dir() and not out.exists(), 'output must be new under an existing parent')
    with lock():
        manifest = preflight(translated_macos_x64)
        available = available_memory()
        require(available >= 5 * 1024**3 and shutil.disk_usage(out.parent).free >= 5 * 1024**3,
                'requires five GiB available memory and disk')
        out.mkdir(mode=0o700)
        private = out / 'private'
        private.mkdir(mode=0o700)
        ringdb = private / 'ringdb'
        ringdb.mkdir(mode=0o700)
        processes, logs = [], []
        receipt = {'schema': 'meownero-portable-journey/1', 'result': 'FAIL_NATIVE_JOURNEY',
                   'upstream_commit': UPSTREAM, 'architecture': manifest['architecture'],
                   'release_manifest_sha256': sha(ROOT / 'release.json'),
                   'program_sha256': {name: sha(executable(name)) for name in PROGRAMS},
                   'cleanup': [], 'payments': [], 'native_processes': []}
        receipt['execution_substrate'] = 'ROSETTA_TRANSLATED_MACOS_X86_64' if translated_macos_x64 else \
            ('NATIVE_WINDOWS_WOW64' if WINDOWS and manifest['architecture'] == 'i686' and portable_windows.native_architecture() == 'x86_64' else 'NATIVE')
        began = time.monotonic()

        def deadline(signum, frame):
            raise JourneyInterrupted('native journey interrupted or deadline reached')

        job = portable_windows.Job(seconds=deadline_seconds) if WINDOWS else None
        previous_handler = signal.signal(signal.SIGALRM, deadline) if not WINDOWS else None
        previous_term = signal.signal(signal.SIGTERM, deadline)
        if not WINDOWS:
            signal.setitimer(signal.ITIMER_REAL, deadline_seconds)
        previous_break = signal.signal(signal.SIGBREAK, deadline) if WINDOWS else None

        def spawn(name, program, arguments):
            stream = (private / (name + '.log')).open('wb')
            logs.append(stream)
            if WINDOWS:
                process = job.spawn(executable(program), arguments, stream, child_environment(), private)
                processes.append((name, process))
                return process
            # A cancellation between fork and registration must not orphan a child.
            mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGINT, signal.SIGALRM})
            try:
                process = subprocess.Popen([str(executable(program)), *arguments],
                    stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT,
                    start_new_session=True, env=child_environment(), cwd=private,
                    preexec_fn=lambda: signal.pthread_sigmask(signal.SIG_SETMASK, mask))
                processes.append((name, process))
            finally:
                signal.pthread_sigmask(signal.SIG_SETMASK, mask)
            return process

        def start(name, program, arguments, port):
            with socket.socket() as reserved:
                reserved.bind(('127.0.0.1', port))
            process = spawn(name, program, arguments)
            end = time.monotonic() + 45
            while time.monotonic() < end:
                require(process.poll() is None, 'owned process exited: ' + name)
                try:
                    rpc(port, 'get_info' if program == 'monerod' else 'get_version')
                    if manifest['system'] == 'Linux':
                        mapped_executable = Path('/proc/' + str(process.pid) + '/exe')
                        actual_hash = hashlib.sha256(mapped_executable.read_bytes()).hexdigest()
                        paths = [Path(parts[5]) for line in Path('/proc/' + str(process.pid) + '/maps').read_text().splitlines()
                                 if len(parts := line.split(maxsplit=5)) == 6 and parts[5].startswith('/')]
                    elif manifest['system'] == 'Darwin':
                        mapped = subprocess.check_output(['/usr/sbin/lsof', '-a', '-p', str(process.pid),
                                                          '-d', 'txt', '-Fn'], text=True, timeout=10)
                        paths = [Path(line[1:]) for line in mapped.splitlines() if line.startswith('n/')]
                        require(ROOT / 'bin' / program in paths, 'native kernel executable mapping mismatch')
                        actual_hash = sha(ROOT / 'bin' / program)
                    else:
                        mapped_executable, paths = portable_windows.mapped_paths(process)
                        require(mapped_executable == executable(program), 'native kernel executable mapping mismatch')
                        actual_hash = sha(mapped_executable)
                    require(actual_hash == receipt['program_sha256'][program], 'running executable hash mismatch')
                    loaded = {}
                    for path in paths:
                        basename = path.name.lower() if WINDOWS else path.name
                        if basename in manifest['bundled_libraries']:
                            require(path.parent == ROOT / ('bin' if WINDOWS else 'lib'), 'system library substituted for bundled library')
                            loaded[basename] = sha(path)
                    receipt['native_processes'].append({'name': name, 'pid': process.pid,
                        'binary_sha256': actual_hash, 'bundled_library_sha256': loaded})
                    return
                except (OSError, RuntimeError):
                    time.sleep(0.2)
            raise TimeoutError('startup timeout: ' + name)

        try:
            # Reserve every port together, then let owned children bind them.
            reservations = [socket.socket() for _ in range(5)]
            try:
                for item in reservations:
                    item.bind(('127.0.0.1', 0))
                ports = [item.getsockname()[1] for item in reservations]
            finally:
                for item in reservations:
                    item.close()
            node, p2p, sender, receiver, restored = ports
            chain = private / 'chain'
            chain.mkdir(mode=0o700)
            start('daemon', 'monerod', ['--regtest', '--keep-fakechain', '--fixed-difficulty', '1',
                '--offline', '--non-interactive', '--no-igd', '--disable-dns-checkpoints',
                '--check-updates', 'disabled', '--no-zmq', '--rpc-ssl', 'disabled',
                '--max-concurrency', '1', '--data-dir', str(chain), '--p2p-bind-ip', '127.0.0.1',
                '--p2p-bind-port', str(p2p), '--rpc-bind-ip', '127.0.0.1', '--rpc-bind-port', str(node),
                '--log-file', str(private / 'daemon-native.log')], node)
            for name, port in [('sender', sender), ('receiver', receiver), ('restored', restored)]:
                directory = private / name
                directory.mkdir(mode=0o700)
                start(name, 'monero-wallet-rpc', ['--rpc-bind-ip', '127.0.0.1', '--rpc-bind-port', str(port),
                    '--disable-rpc-login', '--wallet-dir', str(directory), '--daemon-address',
                    'http://127.0.0.1:' + str(node), '--trusted-daemon', '--allow-mismatched-daemon-version',
                    '--shared-ringdb-dir', str(ringdb), '--max-concurrency', '1',
                    '--log-file', str(private / (name + '-native.log'))], port)
            for name, port in [('sender', sender), ('receiver', receiver)]:
                rpc(port, 'create_wallet', {'filename': name, 'password': '', 'language': 'English'})
            sender_address = rpc(sender, 'get_address')['address']
            receiver_address = rpc(receiver, 'get_address')['address']

            def mine(count):
                require(len(rpc(node, 'generateblocks', {'wallet_address': sender_address,
                    'amount_of_blocks': count})['blocks']) == count, 'funding block count mismatch')

            def balance(port):
                rpc(port, 'refresh')
                return rpc(port, 'get_balance')['balance']

            def payment(port, destination, amount):
                txid = rpc(port, 'transfer', {'destinations': [{'amount': amount, 'address': destination}]})['tx_hash']
                require(len(txid) == 64 and all(c in '0123456789abcdef' for c in txid), 'invalid transaction hash')
                # Fetch the actual daemon transaction, including an unmined pool transaction.
                request = urllib.request.Request('http://127.0.0.1:' + str(node) + '/get_transactions',
                    json.dumps({'txs_hashes': [txid], 'decode_as_json': True}).encode(),
                    {'Content-Type': 'application/json'})
                with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=90) as response:
                    tx = json.loads(json.load(response)['txs'][0]['as_json'])
                require(tx['rct_signatures']['type'] == 7 and tx['vout'] and
                        all('carrot_v1' in item['target'] for item in tx['vout']), 'wrong crypto lineage')
                receipt['payments'].append({'tx_hash': txid, 'amount_atomic': amount, 'rct_type': 7,
                                            'carrot_outputs': True})
                mine(12)
                return txid

            mine(70)
            balance(sender)
            first_tx = payment(sender, receiver_address, 5 * COIN)
            require(balance(receiver) == 5 * COIN, 'receive balance mismatch')
            def outputs(port):
                return [{key: row[key] for key in ('tx_hash', 'amount', 'key_image', 'pubkey', 'spent')}
                        for row in rpc(port, 'incoming_transfers', {'transfer_type': 'all'})['transfers']]
            original_outputs = outputs(receiver)
            require(len(original_outputs) == 1 and original_outputs[0]['tx_hash'] == first_tx and
                    original_outputs[0]['amount'] == 5 * COIN and original_outputs[0]['key_image'],
                    'native receive output mismatch')
            seed = rpc(receiver, 'query_key', {'key_type': 'mnemonic'})['key']
            require(len(seed.split()) == 25, 'unexpected recovery seed format')
            recovered = rpc(restored, 'restore_deterministic_wallet', {'seed': seed, 'restore_height': 0,
                'filename': 'restored', 'password': '', 'autosave_current': True})
            del seed
            require(recovered['address'] == receiver_address and balance(restored) == 5 * COIN,
                    'restored address or balance mismatch')
            require(outputs(restored) == original_outputs, 'restored outputs or key images mismatch')
            later_tx = payment(restored, sender_address, 2 * COIN)
            require(balance(restored) < 3 * COIN, 'restored spend balance mismatch')
            balance(sender)
            require(any(row['tx_hash'] == later_tx and row['amount'] == 2 * COIN for row in outputs(sender)),
                    'later payment not received by sender')
            require(any(row['key_image'] == original_outputs[0]['key_image'] and row['spent']
                        for row in outputs(restored)), 'recovered input was not spent')
            receipt['receive_atomic'] = 5 * COIN
            receipt['restore_matches'] = True
            receipt['subsequent_spend_atomic'] = 2 * COIN
            restored_process = next(process for name, process in processes if name == 'restored')
            restored_process.terminate()
            restored_process.wait(timeout=10)
            cli = spawn('cli', 'monero-wallet-cli', ['--wallet-file',
                str(private / 'restored/restored'), '--password', '', '--daemon-address',
                'http://127.0.0.1:' + str(node), '--trusted-daemon', '--allow-mismatched-daemon-version',
                '--shared-ringdb-dir', str(ringdb),
                '--log-file', str(private / 'cli-native.log'), 'balance'])
            cli.wait(timeout=60)
            require(cli.returncode == 0 and b'alance:' in (private / 'cli.log').read_bytes(),
                    'native CLI could not open restored wallet')
            receipt['cli_open_restored_wallet'] = True
            preflight(translated_macos_x64)
            require(not WINDOWS or not job.expired, 'owned Windows journey deadline reached')
            receipt['result'] = 'PASS_TRANSLATED_JOURNEY' if translated_macos_x64 else 'PASS_NATIVE_JOURNEY'
        finally:
            if not WINDOWS:
                signal.setitimer(signal.ITIMER_REAL, 0)
                signal.signal(signal.SIGALRM, previous_handler)
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            previous_int = signal.signal(signal.SIGINT, signal.SIG_IGN)
            if WINDOWS:
                signal.signal(signal.SIGBREAK, signal.SIG_IGN)
            if WINDOWS:
                try:
                    job.close()
                    receipt['owned_job_cleanup'] = True
                    receipt['owned_job'] = job.cleanup
                except (OSError, RuntimeError, subprocess.TimeoutExpired):
                    receipt['owned_job_cleanup'] = False
                    receipt['result'] = 'FAIL_NATIVE_JOURNEY'
            for name, process in reversed(processes):
                try:
                    if process.poll() is None:
                        process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
                    receipt['cleanup'].append({'name': name, 'pid': process.pid, 'exit': process.returncode,
                                               'removed': True})
                except (OSError, subprocess.TimeoutExpired):
                    receipt['cleanup'].append({'name': name, 'pid': process.pid, 'removed': False})
                    receipt['result'] = 'FAIL_NATIVE_JOURNEY'
            for stream in logs:
                stream.close()
            receipt['wall_seconds'] = round(time.monotonic() - began, 3)
            (out / 'result.json').write_text(json.dumps(receipt, indent=2) + '\n')
            signal.signal(signal.SIGTERM, previous_term)
            signal.signal(signal.SIGINT, previous_int)
            if WINDOWS:
                signal.signal(signal.SIGBREAK, previous_break)
        require(receipt['result'] == ('PASS_TRANSLATED_JOURNEY' if translated_macos_x64 else 'PASS_NATIVE_JOURNEY'), 'journey or owned cleanup failed')
        print(receipt['result'] + '. Share only result.json. Keep private/ unshared.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['preflight', 'run'])
    parser.add_argument('--out', type=Path)
    parser.add_argument('--translated-macos-x86_64', action='store_true')
    parser.add_argument('--deadline-seconds', type=int, default=1200)
    args = parser.parse_args()
    require(1 <= args.deadline_seconds <= 1200, 'deadline must be within 1..1200 seconds')
    if args.action == 'preflight':
        with lock():
            preflight(args.translated_macos_x86_64)
        print('PASS_PREFLIGHT')
    else:
        require(args.out is not None, '--out is required')
        run(args.out, args.translated_macos_x86_64, args.deadline_seconds)


if __name__ == '__main__':
    main()
