"""Run inside the builder with --network none; all keys are disposable test keys."""
import json
from pathlib import Path
import subprocess
import time
import urllib.request

BIN = Path('/src/build/release/bin')
WORK = Path('/work')
REWARD = 900_000_000_000


def request(port, path, body):
    req = urllib.request.Request(f'http://127.0.0.1:{port}/{path}',
                                 json.dumps(body).encode(), {'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=60) as response:
        result = json.load(response)
    assert 'error' not in result, (path, result.get('error'))
    return result


def rpc(port, method, params=None):
    return request(port, 'json_rpc', {'jsonrpc': '2.0', 'id': '0',
                                     'method': method, 'params': params or {}})['result']


def wait_until(check, label, seconds=120):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        assert all(p.poll() is None for p in processes), 'test process exited'
        try:
            if check():
                return
        except (OSError, ValueError):
            pass
        time.sleep(0.5)
    raise AssertionError(f'timeout: {label}')


def start(binary, args, name):
    with (WORK / f'{name}.stdout.log').open('w') as log:
        process = subprocess.Popen([str(BIN / binary), *args], stdout=log, stderr=subprocess.STDOUT)
    processes.append(process)
    return process


def snapshot(port):
    rpc(port, 'refresh', {'start_height': 0})
    balance = rpc(port, 'get_balance')
    history = rpc(port, 'get_transfers', {'in': True}).get('in', [])
    # Wallet-local annotations and confirmation count are not seed-derived history.
    history = sorted((t['txid'], t['height'], t['amount'], t['type']) for t in history)
    return {'balance': balance['balance'], 'unlocked_balance': balance['unlocked_balance'],
            'history': history}


processes = []
try:
    start('monerod', ['--data-dir', str(WORK / 'chain'), '--non-interactive', '--no-igd', '--offline',
          '--p2p-bind-ip', '127.0.0.1', '--p2p-bind-port', '19080', '--rpc-bind-ip', '127.0.0.1',
          '--rpc-bind-port', '19081', '--zmq-rpc-bind-ip', '127.0.0.1', '--out-peers', '0',
          '--in-peers', '0', '--disable-dns-checkpoints', '--check-updates', 'disabled',
          '--fixed-difficulty', '1', '--log-file', str(WORK / 'daemon.log')], 'daemon')
    wait_until(lambda: rpc(19081, 'get_info')['height'] == 1, 'daemon genesis')
    for port, name in [(19100, 'original'), (19101, 'recovered')]:
        directory = WORK / name
        directory.mkdir()
        start('monero-wallet-rpc', ['--rpc-bind-ip', '127.0.0.1', '--rpc-bind-port', str(port),
              '--disable-rpc-login', '--wallet-dir', str(directory), '--daemon-address',
              'http://127.0.0.1:19081', '--trusted-daemon', '--log-file', str(WORK / f'{name}.log')], name)
        # get_version works before a wallet is open.
        wait_until(lambda: rpc(port, 'get_version')['version'] > 0, f'{name} RPC')
    rpc(19100, 'create_wallet', {'filename': 'original', 'password': 'disposable', 'language': 'English'})
    address = rpc(19100, 'get_address')['address']
    assert address.startswith('M')
    seed = rpc(19100, 'query_key', {'key_type': 'mnemonic'})['key']
    assert len(seed.split()) == 25
    assert snapshot(19100)['balance'] == 0
    result = request(19081, 'start_mining', {'miner_address': address, 'threads_count': 1,
                                          'do_background_mining': False, 'ignore_battery': True})
    assert result['status'] == 'OK', result
    wait_until(lambda: rpc(19081, 'get_info')['height'] >= 91, '90 mined blocks', seconds=240)
    assert request(19081, 'stop_mining', {})['status'] == 'OK'
    height = rpc(19081, 'get_info')['height'] - 1
    before = snapshot(19100)
    assert before['balance'] == height * REWARD, (height, before['balance'])
    assert before['unlocked_balance'] > 0
    assert len(before['history']) == height
    assert sum(t[2] for t in before['history']) == before['balance']
    # Close and remove the original cache AND key file. Only the in-memory mnemonic
    # crosses to the second wallet; no original file is mounted/copied there.
    rpc(19100, 'close_wallet')
    (WORK / 'original' / 'original').unlink()
    (WORK / 'original' / 'original.keys').unlink()
    assert not list((WORK / 'recovered').iterdir())
    restored = rpc(19101, 'restore_deterministic_wallet', {'seed': seed, 'restore_height': 0,
                   'filename': 'recovered', 'password': 'disposable', 'autosave_current': True})
    del seed
    assert restored['address'] == address
    assert rpc(19101, 'get_address')['address'] == address
    after = snapshot(19101)
    assert after == before, 'restored balance/unlocked balance/history differs'
    rpc(19101, 'close_wallet')
    rpc(19101, 'open_wallet', {'filename': 'recovered', 'password': 'disposable'})
    assert snapshot(19101) == before, 'reopened restored wallet differs'
    summary = {'result': 'PASS', 'height': height, 'address_matches': True,
               'history_entries': len(after['history']), 'balance_atomic': after['balance'],
               'unlocked_balance_atomic': after['unlocked_balance'], 'reopen_matches': True,
               'scope': 'mined coinbase history; fixed difficulty 1; isolated disposable keys'}
    (WORK / 'result.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))
finally:
    for process in reversed(processes):
        process.terminate()
    for process in reversed(processes):
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
