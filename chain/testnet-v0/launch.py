#!/usr/bin/env python3
"""Version 1: fresh, isolated selected-9-90 two-peer launch and bounded witness."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import urllib.request

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
IMAGE = 'sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e'
BINARY_SHA = 'b79cb49dbea95c0eeff7dca8c945d65f4fab3d49fb626fcbe7a9343569d4a2c1'
EXPECTED = {
    'recipe_version': 1,
    'profile': 'selected-9-90',
    'network_mode': 'isolated-mainnet',
    'genesis_hash': '20ce111b9a74c7ce79fbaafd053afb71b2f2335e208fa7e993fb46c8c91964d8',
    'genesis_reward_atomic': 0,
    'reward_atomic': 9000000000000,
    'target_seconds': 90,
    'fork': {'genesis_version': 1, 'version': 16, 'height': 1},
    'address_prefix': 120,
    'pool_profile': 'selected-9-90-prefix120',
    'pool_enabled': False,
}
# Existing public test-reorg.py fixture. No wallet, seed or private key is used.
ADDRESS = 'M9Lds8CcBgCJbqSiUvYfS3BfhEdxZmv8pDt25oW1LzxrZv9Uq6ARagiFViMGUE3gJk5VPWingCXVf1p2tyAy6SUeSLMMvfc'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def validate_profile(profile):
    require(isinstance(profile, dict), 'profile must be a JSON object')
    for key, value in EXPECTED.items():
        require(profile.get(key) == value, f'wrong {key} profile: expected {value!r}, got {profile.get(key)!r}')
    require(profile.keys() == EXPECTED.keys(), 'unexpected profile fields; daemon overrides are not supported')


def preflight(binary, profile_path):
    validate_profile(json.loads(profile_path.read_text()))
    require(digest(binary) == BINARY_SHA, f'binary SHA-256 mismatch: expected {BINARY_SHA}')
    manifest = json.loads((HERE / 'baseline.json').read_text())
    require(manifest['monerod_sha256'] == BINARY_SHA and manifest['builder_image'] == IMAGE,
            'baseline binary or builder mismatch')
    patches = sorted(str(p.relative_to(ROOT)) for p in (ROOT / 'chain/patches').glob('*.patch'))
    require(patches == manifest['patch_order'] and len(patches) == 15, 'fifteen-patch manifest mismatch')
    for name, expected in manifest['inputs_sha256'].items():
        require(digest(ROOT / name) == expected, f'input SHA-256 mismatch: {name}')
    return manifest


def rpc(node, method, params=None, endpoint=False):
    body = params or {}
    route = method if endpoint else 'json_rpc'
    if not endpoint:
        body = {'jsonrpc': '2.0', 'id': '0', 'method': method, 'params': body}
    request = urllib.request.Request(f'http://127.0.0.1:{28081 + node * 100}/{route}',
                                     json.dumps(body).encode(), {'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=15) as response:
        result = json.load(response)
    require(not result.get('error'), f'{method}: {result}')
    result = result if endpoint else result['result']
    require(result.get('status', 'OK') == 'OK', f'{method}: {result}')
    return result


def inside():
    work = Path('/work')
    procs = {}
    result = {'result': 'FAIL', 'scope': 'two local P2P peers; native miner and DAA; empty blocks'}
    started = time.monotonic()

    def event(label, **fields):
        print(json.dumps({'event': label, 'elapsed_s': time.monotonic() - started, **fields}), flush=True)

    def wait(check, label, seconds=90):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            require(all(p.poll() is None for p in procs.values()), 'daemon exited early')
            try:
                if check():
                    return
            except (OSError, ValueError):
                pass
            time.sleep(0.2)
        raise TimeoutError(label)

    def header(node, height):
        return rpc(node, 'get_block_header_by_height', {'height': height})['block_header']

    def state(node):
        tip = rpc(node, 'get_last_block_header')['block_header']
        sums = rpc(node, 'get_coinbase_tx_sum', {'height': 0, 'count': tip['height'] + 1})
        return {'height': tip['height'], 'hash': tip['hash'],
                'cumulative_work': tip['wide_cumulative_difficulty'],
                'emission_atomic': sums['emission_amount'], 'fees_atomic': sums['fee_amount']}

    def interrupted(signum, frame):
        raise RuntimeError(f'interrupted by signal {signum}')

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    try:
        require(sorted(p.name for p in Path('/sys/class/net').iterdir()) == ['lo'],
                'inside mode requires an isolated network namespace with only loopback')
        validate_profile(json.loads((work / 'profile.json').read_text()))
        require(digest(Path('/binary/monerod')) == BINARY_SHA, 'mounted binary SHA-256 mismatch')
        (work / 'data').mkdir()  # Exclusive creation: never adopt stale node state.
        commands = {}
        for n in (0, 1):
            data = work / 'data' / f'peer{n}'
            data.mkdir()
            # Empty explicit config prevents inherited user configuration.
            config = work / f'peer{n}.conf'
            config.write_text('')
            cmd = ['/binary/monerod', '--config-file', str(config), '--data-dir', str(data),
                   '--non-interactive', '--no-igd', '--disable-dns-checkpoints', '--check-updates', 'disabled',
                   '--max-concurrency', '1', '--allow-local-ip', '--hide-my-port',
                   '--add-exclusive-node', f'127.0.0.1:{28080 + (1-n)*100}',
                   '--p2p-bind-ip', '127.0.0.1', '--p2p-bind-port', str(28080+n*100),
                   '--rpc-bind-ip', '127.0.0.1', '--rpc-bind-port', str(28081+n*100),
                   '--rpc-ssl', 'disabled', '--no-zmq', '--log-level', '1',
                   '--log-file', str(work / f'peer{n}.log')]
            commands[f'peer{n}'] = cmd
            save(work / 'daemon-commands.json', commands)
            with (work / f'peer{n}.stdout.log').open('w') as log:
                procs[n] = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
        wait(lambda: all(rpc(n, 'get_info')['synchronized'] for n in (0, 1)), 'core startup timeout')
        initial = {}
        for n in (0, 1):
            info = rpc(n, 'get_info')
            genesis = header(n, 0)
            fork = rpc(n, 'hard_fork_info', {'version': 16})
            template = rpc(n, 'get_block_template', {'wallet_address': ADDRESS})
            initial[str(n)] = {'info': info, 'genesis': genesis, 'fork': fork, 'template': template}
            require(info['height'] == 1 and info['nettype'] == 'mainnet', 'wrong fresh network mode')
            require(info['target'] == EXPECTED['target_seconds'], 'wrong live target profile')
            require(genesis['hash'] == EXPECTED['genesis_hash'], 'wrong live genesis profile')
            require(genesis['reward'] == 0 and genesis['major_version'] == 1, 'wrong live genesis reward/version')
            require(fork['version'] == 16 and fork['earliest_height'] == 1, 'wrong live fork profile')
            require(template['expected_reward'] == EXPECTED['reward_atomic'], 'wrong live reward profile')
            require(template['height'] == 1 and bytes.fromhex(template['blocktemplate_blob'])[0] == 16,
                    'wrong height-one template fork')
        save(work / 'profile-readback.json', initial)
        event('profile_verified')
        wait(lambda: all(rpc(n, 'get_connections').get('connections') for n in (0, 1)), 'P2P handshake timeout')
        before = [rpc(n, 'get_connections') for n in (0, 1)]
        save(work / 'peers-before.json', before)
        mining = {'miner_address': ADDRESS, 'threads_count': 1, 'do_background_mining': False, 'ignore_battery': True}
        save(work / 'mining-command.json', {'node': 0, 'endpoint': '/start_mining', 'params': mining})
        rpc(0, 'start_mining', mining, endpoint=True)
        event('native_mining_started')
        wait(lambda: rpc(0, 'get_info')['height'] >= 4, 'native mining timeout', seconds=240)
        rpc(0, 'stop_mining', endpoint=True)
        wanted = state(0)
        wait(lambda: state(1) == wanted, 'P2P convergence timeout')
        states = [state(n) for n in (0, 1)]
        require(states[0] == states[1] and states[0]['height'] >= 3, 'tip/work/emission mismatch')
        require(wanted['emission_atomic'] == wanted['height'] * EXPECTED['reward_atomic'], 'wrong total emission')
        require(wanted['fees_atomic'] == 0, 'unexpected fees in empty-block witness')
        headers = [[header(n, h) for h in range(wanted['height'] + 1)] for n in (0, 1)]
        for peer_headers in headers:
            require(all(h['major_version'] == 16 and h['reward'] == EXPECTED['reward_atomic']
                        for h in peer_headers[1:]), 'wrong mined reward/fork profile')
        save(work / 'headers.json', headers)
        save(work / 'rpc-final.json', [
            {'info': rpc(n, 'get_info'), 'tip': rpc(n, 'get_last_block_header'),
             'sum': rpc(n, 'get_coinbase_tx_sum', {'height': 0, 'count': wanted['height'] + 1})}
            for n in (0, 1)])
        save(work / 'peers-after.json', [rpc(n, 'get_connections') for n in (0, 1)])
        result.update(result='PASS', peers=states, profile=EXPECTED,
                      delivery='native mining on peer0; peer1 receives through TCP P2P only')
        event('converged', peers=states)
    except Exception as error:
        result.update(result='FAIL', error=str(error))
        event('failure', error=str(error))
    finally:
        for p in procs.values():
            if p.poll() is None:
                p.terminate()
        exits = {}
        for n, p in procs.items():
            try:
                p.wait(timeout=30)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()
            exits[str(n)] = p.returncode
        resources = {p.name: p.read_text() for p in (Path('/sys/fs/cgroup') / name for name in
                     ('memory.peak', 'memory.events', 'memory.max', 'memory.swap.max', 'cpu.max')) if p.exists()}
        resources['daemon_exit_codes'] = exits
        resources['elapsed_seconds'] = time.monotonic() - started
        save(work / 'resources.json', resources)
        if len(exits) != 2 or any(exits.values()):
            result.update(result='FAIL', shutdown_error=exits)
        save(work / 'result.json', result)
    return 0 if result['result'] == 'PASS' else 1


def launch(args):
    binary = args.binary.resolve()
    profile = args.profile.resolve()
    work = args.work.absolute()
    require(not work.exists() and not work.is_symlink(), f'stale data/output directory refused: {work}; choose a new path')
    manifest = preflight(binary, profile)
    if args.check_only:
        print('PASS: profile, binary and baseline inputs verified; no process started')
        return 0
    work.mkdir(parents=True)  # exist_ok=False also rejects racing launches.
    save(work / 'launcher-command.json', [sys.executable, *sys.argv])
    save(work / 'baseline.json', manifest)
    shutil.copyfile(profile, work / 'profile.json')
    inputs = list(manifest['inputs_sha256']) + [str(p.relative_to(ROOT)) for p in HERE.iterdir() if p.is_file()]
    (work / 'INPUTS.sha256').write_text(''.join(f'{digest(ROOT / p)}  {p}\n' for p in sorted(set(inputs))))
    (work / 'BINARY.sha256').write_text(f'{digest(binary)}  {binary}\n')
    # This is the existing shared resource lock, not a scratch directory.
    with open('/tmp/meownero-swarm-20260912-heavy.lock', 'a') as lock:
        process = None
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('shared heavy lock busy; retry with a fresh path after its owner finishes')
        available = int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines()
                             if line.startswith('MemAvailable:'))) * 1024
        free = shutil.disk_usage(work).free
        save(work / 'preflight-resources.json', {'available_ram_bytes': available, 'free_disk_bytes': free,
                                               'minimum_bytes': 5 * 1024**3})
        require(min(available, free) >= 5 * 1024**3, 'need at least 5 GiB available RAM and disk')
        name = f'meow-tjs229-{os.getpid()}'
        command = ['docker', 'run', '--rm', '--pull=never', '--name', name, '--network', 'none',
                   '--memory=4g', '--memory-swap=4g', '--cpus=2', '--pids-limit=256',
                   '--user', f'{os.getuid()}:{os.getgid()}', '--cap-drop=ALL', '--security-opt=no-new-privileges',
                   '--read-only', '--tmpfs', '/tmp:rw,nosuid,nodev,size=64m',
                   '-e', 'PYTHONDONTWRITEBYTECODE=1', '-e', 'HOME=/tmp',
                   '-v', f'{binary}:/binary/monerod:ro', '-v', f'{HERE}:/recipe:ro',
                   '-v', f'{work}:/work', IMAGE,
                   'timeout', '--signal=TERM', '--kill-after=75', '420', 'python3', '-u', '/recipe/launch.py', '--inside']
        save(work / 'container-command.json', command)
        try:
            with (work / 'run.log').open('w') as log:
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                for line in process.stdout:
                    print(line, end='', flush=True)
                    log.write(line)
                    log.flush()
                code = process.wait()
            (work / 'container.exit').write_text(str(code) + '\n')
            require(code == 0, f'container exited {code}; inspect {work}/run.log')
        finally:
            # Exact owned name only; no host services or other workers are touched.
            if process is not None and process.poll() is None:
                stopped = subprocess.run(['docker', 'stop', '--time', '65', name], capture_output=True, text=True)
                save(work / 'interrupted-stop.json', {'exit': stopped.returncode,
                                                     'stdout': stopped.stdout, 'stderr': stopped.stderr})
                process.wait(timeout=15)
                (work / 'container.exit').write_text(str(process.returncode) + '\n')
            cleanup = subprocess.run(['docker', 'rm', '-f', name], capture_output=True, text=True)
            save(work / 'cleanup.json', {'command': ['docker', 'rm', '-f', name], 'exit': cleanup.returncode,
                                         'stdout': cleanup.stdout, 'stderr': cleanup.stderr})
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, default=ROOT / 'build/repro-selected-20260918/selected-9-90/first/source/build/release/bin/monerod')
    parser.add_argument('--profile', type=Path, default=HERE / 'profile.json')
    parser.add_argument('--work', type=Path)
    parser.add_argument('--check-only', action='store_true')
    parser.add_argument('--inside', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.inside:
        return inside()
    if args.work is None:
        parser.error('--work requires a fresh directory path')
    fresh = not args.work.exists() and not args.work.is_symlink()
    code = 2
    try:
        code = launch(args)
    except KeyboardInterrupt:
        print('Interrupted; owned container stopped', file=sys.stderr)
        code = 130
    except (OSError, ValueError, KeyError) as error:
        print(f'REFUSED: {error}', file=sys.stderr)
    finally:
        if fresh and (args.work / 'launcher-command.json').exists():
            (args.work / 'launcher.exit').write_text(str(code) + '\n')
            public = sorted(p for p in args.work.iterdir() if p.is_file() and p.name != 'EVIDENCE.sha256')
            (args.work / 'EVIDENCE.sha256').write_text(''.join(f'{digest(p)}  {p.name}\n' for p in public))
    return code


if __name__ == '__main__':
    sys.exit(main())
