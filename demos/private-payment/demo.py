"""Actual current15 binaries; disposable private chain, integer-only accounting.

Derived from chain/test-seed-recovery.py and the template submission in
chain/test-reorg.py. Never imports or changes either original runner.
"""
import hashlib
import json
import platform
from pathlib import Path
import shutil
import subprocess
import time
import urllib.request

BIN = Path('/src/build/release/bin')
WORK = Path('/work')
REWARD = 900_000_000_000
PAYMENT = 123_456_789_012
EXPECTED = {
    'monerod': '850d6eecef1831878d3a8196f3e2135a4c1ebe57f5e887566695ce9ce82e0ddc',
    'monero-wallet-rpc': '3c6df7d56822641f1aca4c064a7d52d931cec566ee8ca480f114ff8147bae097',
    'monero-wallet-cli': '9a3805eccbac710fa5e56cb584cc029b6aae56cef134cc79ca8af772aec1c8b7',
}
processes = {}
timings = {}


def request(port, path, body):
    req = urllib.request.Request(f'http://127.0.0.1:{port}/{path}',
                                 json.dumps(body).encode(), {'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=90) as response:
        result = json.load(response)
    assert 'error' not in result, (path, result.get('error'))
    return result


def rpc(port, method, params=None):
    return request(port, 'json_rpc', {'jsonrpc': '2.0', 'id': '0',
                                     'method': method, 'params': params or {}})['result']


def start(binary, args, name, port):
    with (WORK / f'{name}.stdout.log').open('w') as log:
        processes[name] = subprocess.Popen([str(BIN / binary), *args], stdout=log,
                                            stderr=subprocess.STDOUT)
    for _ in range(120):
        assert all(p.poll() is None for p in processes.values()), 'process exited'
        try:
            rpc(port, 'get_info' if binary == 'monerod' else 'get_version')
            return
        except OSError:
            time.sleep(0.5)
    raise AssertionError(f'{name}: startup timeout')


def stop(name):
    process = processes.pop(name)
    process.terminate()
    try:
        assert process.wait(timeout=20) == 0, f'{name}: nonzero exit'
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        raise


def wallet(name, port):
    directory = WORK / name
    directory.mkdir()
    start('monero-wallet-rpc', ['--rpc-bind-ip', '127.0.0.1', '--rpc-bind-port', str(port),
          '--disable-rpc-login', '--wallet-dir', str(directory), '--daemon-address',
          'http://127.0.0.1:19081', '--trusted-daemon', '--max-concurrency', '1',
          '--log-file', str(WORK / f'{name}.log')], name, port)


def create(port, name):
    rpc(port, 'create_wallet', {'filename': name, 'password': 'disposable', 'language': 'English'})
    rpc(port, 'auto_refresh', {'enable': False})
    return rpc(port, 'get_address')['address']


def snapshot(port):
    rpc(port, 'refresh', {'start_height': 0})
    balance = rpc(port, 'get_balance')
    history = rpc(port, 'get_transfers', {'in': True}).get('in', [])
    return {'balance_atomic': balance['balance'], 'unlocked_atomic': balance['unlocked_balance'],
            'history': sorted((t['txid'], t['height'], t['amount'], t['type']) for t in history)}


def read_varint(data, offset):
    value = shift = 0
    while shift < 64:
        byte = data[offset]
        offset += 1
        value |= (byte & 127) << shift
        if byte < 128:
            return value, offset
        shift += 7
    raise AssertionError('invalid varint')


def varint(value):
    result = bytearray()
    while value >= 128:
        result.append((value & 127) | 128)
        value >>= 7
    return result + bytes([value])


def generate(address, count, base_time):
    # Submit real templates at difficulty 1: avoids a full RandomX mining dataset.
    # This uses a test-only fixed-difficulty flag, not a production DAA measurement.
    for _ in range(count):
        template = rpc(19081, 'get_block_template', {'wallet_address': address})
        assert template['difficulty'] == 1
        blob = bytearray.fromhex(template['blocktemplate_blob'])
        _, offset = read_varint(blob, 0)
        _, offset = read_varint(blob, offset)
        _, end = read_varint(blob, offset)
        blob[offset:end] = varint(base_time + template['height'] * 120)
        assert rpc(19081, 'submit_block', [blob.hex()])['status'] == 'OK'


def main():
    hashes = {}
    for name, expected in EXPECTED.items():
        with (BIN / name).open('rb') as binary:
            digest = hashlib.sha256()
            for chunk in iter(lambda: binary.read(1024 * 1024), b''):
                digest.update(chunk)
        hashes[name] = digest.hexdigest()
        assert hashes[name] == expected, f'{name}: expected current15 binary'
    provenance = {'binary_sha256': hashes, 'platform': platform.platform(),
                  'cpu': next(line.split(':', 1)[1].strip() for line in
                              Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name')),
                  'compiler': subprocess.check_output(['c++', '--version'], text=True).splitlines()[0],
                  'python': platform.python_version(), 'memory_cap_bytes': 512 * 1024**2,
                  'cpu_quota': 2, 'source_tree': '4db958cb96d72943c5c2433bd5f4a8f730037148',
                  'builder_image': (WORK / 'BUILDER_IMAGE_ID').read_text().strip()}
    (WORK / 'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
    start('monerod', ['--data-dir', str(WORK / 'chain'), '--non-interactive', '--no-igd',
          '--offline', '--p2p-bind-ip', '127.0.0.1', '--p2p-bind-port', '19080',
          '--rpc-bind-ip', '127.0.0.1', '--rpc-bind-port', '19081', '--zmq-rpc-bind-ip',
          '127.0.0.1', '--out-peers', '0', '--in-peers', '0', '--disable-dns-checkpoints',
          '--check-updates', 'disabled', '--fixed-difficulty', '1', '--max-concurrency', '1',
          '--log-file', str(WORK / 'daemon.log')], 'daemon', 19081)
    assert rpc(19081, 'get_info')['height'] == 1
    wallet('sender', 19100)
    sender = create(19100, 'sender')
    wallet('recipient', 19101)
    recipient = create(19101, 'recipient')
    seed = rpc(19101, 'query_key', {'key_type': 'mnemonic'})['key']
    assert len(seed.split()) == 25 and sender != recipient
    assert snapshot(19101)['balance_atomic'] == 0
    # Stay within the new wallet's creation-time scan window, with every header
    # in the past even after all 111 blocks. Older headers can be skipped.
    base_time = int(time.time()) - 15_000
    print('Funding disposable sender with 100 template-submitted blocks', flush=True)
    generate(sender, 100, base_time)
    before = snapshot(19100)
    assert before['balance_atomic'] == 100 * REWARD and before['unlocked_atomic'] > PAYMENT, before
    started = time.perf_counter_ns()
    transfer = rpc(19100, 'transfer', {'destinations': [{'address': recipient, 'amount': PAYMENT}],
                   'ring_size': 16, 'priority': 1, 'get_tx_key': False})
    timings['construct_and_local_submit_ns'] = time.perf_counter_ns() - started
    txid, fee = transfer['tx_hash'], transfer['fee']
    assert transfer['amount'] == PAYMENT and type(fee) is int and fee > 0
    print('Payment accepted locally; confirming and checking atomic accounting', flush=True)
    generate(sender, 11, base_time)
    sent = snapshot(19100)
    received = snapshot(19101)
    assert received['balance_atomic'] == received['unlocked_atomic'] == PAYMENT
    assert len(received['history']) == 1 and received['history'][0][0] == txid
    assert received['history'][0][2:] == (PAYMENT, 'in')
    outgoing = rpc(19100, 'get_transfers', {'out': True})['out']
    assert len(outgoing) == 1 and outgoing[0]['txid'] == txid
    assert outgoing[0]['amount'] == PAYMENT and outgoing[0]['fee'] == fee
    assert sent['balance_atomic'] == before['balance_atomic'] - PAYMENT - fee + 11 * REWARD + fee
    supply = rpc(19081, 'get_coinbase_tx_sum', {'height': 0, 'count': 112})
    assert supply['emission_amount'] == 111 * REWARD and supply['fee_amount'] == fee
    assert sent['balance_atomic'] + received['balance_atomic'] == supply['emission_amount']
    # Check the public transaction representation, not just wallet labels.
    tx = request(19081, 'get_transactions', {'txs_hashes': [txid], 'decode_as_json': True})['txs'][0]
    assert not tx['in_pool']
    public = json.loads(tx['as_json'])
    assert public['version'] == 2 and public['rct_signatures']['type'] != 0
    assert all(v['amount'] == 0 for v in public['vout'])
    assert all(v['key']['amount'] == 0 and len(v['key']['key_offsets']) == 16 for v in public['vin'])
    rpc(19101, 'set_tx_notes', {'txids': [txid], 'notes': ['local note deliberately not seed-derived']})
    assert rpc(19101, 'get_tx_notes', {'txids': [txid]})['notes'][0]
    rpc(19101, 'close_wallet')
    stop('recipient')
    shutil.rmtree(WORK / 'recipient')
    rpc(19100, 'close_wallet')
    stop('sender')
    print('Original recipient files removed; restoring seed in a fresh process', flush=True)
    wallet('recovered', 19102)
    assert not list((WORK / 'recovered').iterdir())
    started = time.perf_counter_ns()
    restored = rpc(19102, 'restore_deterministic_wallet', {'seed': seed, 'restore_height': 0,
                   'filename': 'recovered', 'password': 'disposable', 'autosave_current': True})
    del seed
    assert restored['address'] == recipient
    assert snapshot(19102) == received
    timings['restore_and_refresh_ns'] = time.perf_counter_ns() - started
    assert rpc(19102, 'get_tx_notes', {'txids': [txid]})['notes'] == ['']
    rpc(19102, 'close_wallet')
    rpc(19102, 'open_wallet', {'filename': 'recovered', 'password': 'disposable'})
    assert snapshot(19102) == received
    result = {'result': 'PASS', 'height': 111, 'payment_atomic': PAYMENT, 'fee_atomic': fee,
              'sender_before_atomic': before['balance_atomic'], 'sender_after_atomic': sent['balance_atomic'],
              'post_payment_subsidy_atomic': 11 * REWARD, 'miner_fee_received_atomic': fee,
              'emission_atomic': supply['emission_amount'], 'recipient': received,
              'ring_size': 16, 'rct_type': public['rct_signatures']['type'],
              'public_output_amounts_zero': True, 'address_recovered': True,
              'original_recipient_files_removed': True, 'fresh_process_restore_matches': True,
              'reopen_matches': True, 'local_note_not_recovered': True,
              'timings_ns': timings, 'timing_scope': 'single diagnostic sample; no performance claim',
              'scope': 'isolated mainnet-mode private chain; fixed difficulty 1; historical 120s headers; current ring-based cryptography; no P2P'}
    (WORK / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    try:
        main()
    finally:
        for name in list(reversed(processes)):
            stop(name)
