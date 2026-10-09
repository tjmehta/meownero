#!/usr/bin/env python3
"""Run a disposable native Vanguard payment, recovery and subsequent spend."""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import shutil
import socket
import stat
import subprocess
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parent
UPSTREAM = 'e151643c5269c83bf24a83b2548e2493876026b2'
CARGO_LOCK = '6a8e9217b94169e26a8f595cb528d72c19dc2f5484e903c57328c594d62f8239'
PROGRAMS = ('monerod', 'monero-wallet-cli', 'monero-wallet-rpc')
COIN = 10**12


def child_environment():
    env = dict(os.environ)
    for name in ('LD_PRELOAD', 'LD_AUDIT'):
        env.pop(name, None)
    env['LD_LIBRARY_PATH'] = str(ROOT / 'lib')
    return env


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def safe(path):
    path = Path(os.path.abspath(path))
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'symlink path refused')
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


def preflight():
    sha(ROOT / 'release.json')
    manifest = json.loads(safe(ROOT / 'release.json').read_text())
    require(manifest['upstream_commit'] == UPSTREAM and manifest['cargo_lock_sha256'] == CARGO_LOCK,
            'wrong source pin')
    require(manifest['system'] == 'Linux' and platform.system() == 'Linux', 'wrong operating system')
    machine = {'amd64': 'x86_64', 'arm64': 'aarch64'}.get(platform.machine(), platform.machine())
    require(machine == manifest['architecture'], 'wrong architecture')
    libc, version = platform.libc_ver()
    require(libc == 'glibc' and tuple(map(int, version.split('.'))) >=
            tuple(map(int, manifest['minimum_glibc'].split('.'))), 'glibc ABI too old or unsupported')
    expected = set(manifest['files']) | {'release.json'}
    paths = list(ROOT.rglob('*'))
    require(not any(p.is_symlink() for p in paths), 'package symlink refused')
    actual = {str(p.relative_to(ROOT)) for p in paths if not p.is_dir()}
    require(expected == actual, 'package file set mismatch')
    for name, digest in manifest['files'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts, 'invalid package path')
        require(sha(ROOT / name) == digest, 'package hash mismatch: ' + name)
    for name in PROGRAMS:
        binary = ROOT / 'bin' / name
        with binary.open('rb') as stream:
            header = stream.read(20)
        require(header[:6] == b'\x7fELF\x02\x01' and int.from_bytes(header[18:20], 'little') ==
                {'x86_64': 62, 'aarch64': 183}[machine], 'wrong binary format or target')
        require(os.access(binary, os.X_OK), 'binary is not executable')
        result = subprocess.run([str(binary), '--version'], capture_output=True, timeout=20, env=child_environment())
        require(result.returncode == 0, 'program startup failed: ' + name)
    return manifest


@contextmanager
def lock():
    path = safe(Path(tempfile.gettempdir()) / ('meownero-vanguard-tester-' + str(os.getuid()) + '.lock'))
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


def run(out):
    out = safe(out)
    require(out.parent.is_dir() and not out.exists(), 'output must be new under an existing parent')
    with lock():
        manifest = preflight()
        available = int(next(row.split()[1] for row in Path('/proc/meminfo').read_text().splitlines()
                             if row.startswith('MemAvailable:'))) * 1024
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
                   'program_sha256': {name: sha(ROOT / 'bin' / name) for name in PROGRAMS},
                   'cleanup': [], 'payments': [], 'native_processes': []}
        began = time.monotonic()

        def deadline(signum, frame):
            raise TimeoutError('native journey deadline reached')

        previous_handler = signal.signal(signal.SIGALRM, deadline)
        previous_term = signal.signal(signal.SIGTERM, deadline)
        signal.setitimer(signal.ITIMER_REAL, 1200)

        def spawn(name, program, arguments):
            stream = (private / (name + '.log')).open('wb')
            logs.append(stream)
            # A cancellation between fork and registration must not orphan a child.
            mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGINT, signal.SIGALRM})
            try:
                process = subprocess.Popen([str(ROOT / 'bin' / program), *arguments],
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
                    mapped_executable = Path('/proc/' + str(process.pid) + '/exe')
                    actual_hash = hashlib.sha256(mapped_executable.read_bytes()).hexdigest()
                    require(actual_hash == receipt['program_sha256'][program], 'running executable hash mismatch')
                    loaded = {}
                    for line in Path('/proc/' + str(process.pid) + '/maps').read_text().splitlines():
                        parts = line.split(maxsplit=5)
                        if len(parts) != 6 or not parts[5].startswith('/'):
                            continue
                        path = Path(parts[5])
                        if path.name in manifest['bundled_libraries']:
                            require(path.parent == ROOT / 'lib', 'system library substituted for bundled library')
                            loaded[path.name] = sha(path)
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
            preflight()
            receipt['result'] = 'PASS_NATIVE_JOURNEY'
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous_handler)
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            previous_int = signal.signal(signal.SIGINT, signal.SIG_IGN)
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
        require(receipt['result'] == 'PASS_NATIVE_JOURNEY', 'journey or owned cleanup failed')
        print('PASS_NATIVE_JOURNEY. Share only result.json. Keep private/ unshared.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['preflight', 'run'])
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if args.action == 'preflight':
        with lock():
            preflight()
        print('PASS_PREFLIGHT')
    else:
        require(args.out is not None, '--out is required')
        run(args.out)


if __name__ == '__main__':
    main()
