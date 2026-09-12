"""Fixed-work fork selection; explicit block delivery models a partition.

Uses the upstream generateblocks/submit_block flow, not a chain-selection model.
No P2P latency or normal difficulty claim. No keys loaded; address is a test fixture.
"""
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time
import urllib.request

WORK = Path('/work')
ADDRESS = 'M9Lds8CcBgCJbqSiUvYfS3BfhEdxZmv8pDt25oW1LzxrZv9Uq6ARagiFViMGUE3gJk5VPWingCXVf1p2tyAy6SUeSLMMvfc'
REWARD = 900_000_000_000
MODE = sys.argv[1]
BASE_TIME = int(time.time()) - 100_000
processes = {}


def rpc(node, method, params=None, reject=False):
    body = {'jsonrpc': '2.0', 'id': '0', 'method': method,
            'params': {} if params is None else params}
    req = urllib.request.Request(f'http://127.0.0.1:{19081 + node * 100}/json_rpc',
                                 json.dumps(body).encode(), {'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=90) as response:
        result = json.load(response)
    if reject:
        assert 'error' in result, ('unexpected acceptance', method, result)
        return result['error']
    assert 'error' not in result, (method, result)
    return result['result']


def start(node):
    with (WORK / f'n{node}.stdout.log').open('a') as log:
        processes[node] = subprocess.Popen([
            '/src/build/release/bin/monerod', '--data-dir', str(WORK / f'n{node}'),
            *(['--regtest', '--keep-fakechain', '--fixed-difficulty', '1'] if MODE == 'regtest' else []),
            '--offline',
            '--non-interactive', '--no-igd', '--disable-dns-checkpoints', '--check-updates', 'disabled',
            '--p2p-bind-ip', '127.0.0.1', '--p2p-bind-port', str(19080 + node * 100),
            '--rpc-bind-ip', '127.0.0.1', '--rpc-bind-port', str(19081 + node * 100),
            '--zmq-rpc-bind-ip', '127.0.0.1', '--zmq-rpc-bind-port', str(19082 + node * 100),
            '--log-file', str(WORK / f'n{node}.log')], stdout=log, stderr=subprocess.STDOUT)
    for _ in range(120):
        assert processes[node].poll() is None, 'daemon exited'
        try:
            rpc(node, 'get_info')
            return
        except OSError:
            time.sleep(0.5)
    raise AssertionError('daemon startup timeout')


def stop(node):
    p = processes.pop(node)
    p.terminate()
    try:
        assert p.wait(timeout=20) == 0
    except subprocess.TimeoutExpired:
        p.kill()
        p.wait()
        raise


def tip(node):
    h = rpc(node, 'get_last_block_header')['block_header']
    return h['height'], h['hash'], h['wide_cumulative_difficulty']


def generate(node, count):
    if MODE == 'regtest':
        return rpc(node, 'generateblocks', {'wallet_address': ADDRESS, 'amount_of_blocks': count})['blocks']
    hashes = []
    for _ in range(count):
        template = rpc(node, 'get_block_template', {'wallet_address': ADDRESS})
        # Controlled historical 120-second timestamps keep the *real* DAA at one.
        # No fixed-difficulty override or PoW verification bypass is active.
        assert template['difficulty'] == 1
        blob = bytearray.fromhex(template['blocktemplate_blob'])
        _, offset = read_varint(blob, 0)
        _, offset = read_varint(blob, offset)
        _, end = read_varint(blob, offset)
        blob[offset:end] = varint(BASE_TIME + template['height'] * 120)
        assert rpc(node, 'submit_block', [blob.hex()])['status'] == 'OK'
        hashes.append(tip(node)[1])
    return hashes


def deliver(source, destination, hashes):
    for block_hash in hashes:
        blob = rpc(source, 'get_block', {'hash': block_hash})['blob']
        assert rpc(destination, 'submit_block', [blob])['status'] == 'OK'


def read_varint(data, offset):
    value = shift = 0
    while True:
        byte = data[offset]
        offset += 1
        value |= (byte & 127) << shift
        if byte < 128:
            return value, offset
        shift += 7
        assert shift < 64


def varint(value):
    result = bytearray()
    while value >= 128:
        result.append((value & 127) | 128)
        value >>= 7
    result.append(value)
    return result


try:
    start(0)
    start(1)
    base = generate(0, 65 if MODE == 'regtest' else 738)
    deliver(0, 1, base)
    assert tip(0) == tip(1)
    root = tip(0)
    branch_a = generate(0, 3)
    branch_b = generate(1, 2)
    old_tip = tip(0)
    deliver(1, 0, branch_b)
    assert tip(0) == old_tip, 'shorter branch replaced main chain'
    branch_b += generate(1, 1)
    deliver(1, 0, branch_b[-1:])
    assert tip(0) == old_tip, 'equal-work branch replaced main chain'
    branch_b += generate(1, 1)
    deliver(1, 0, branch_b[-1:])
    assert tip(0) == tip(1)
    assert tip(0)[0] == root[0] + 4
    for block_hash in branch_a:
        assert rpc(0, 'get_block_header_by_hash', {'hash': block_hash})['block_header']['orphan_status']
    for node in (0, 1):
        height = tip(node)[0]
        assert int(tip(node)[2], 16) == height + 1
        supply = rpc(node, 'get_coinbase_tx_sum', {'height': 0, 'count': height + 1})
        assert supply['emission_amount'] == height * REWARD
        assert supply['fee_amount'] == 0
    print('PASS: shorter/equal-work forks retained; greater-work fork reorged depth 3; supply/work agree')

    before = tip(0)
    stop(0)
    start(0)
    assert tip(0) == before, 'restart changed selected chain/work'
    print('PASS: daemon restart retains selected tip and cumulative work')

    template = rpc(0, 'get_block_template', {'wallet_address': ADDRESS})
    blob = bytearray.fromhex(template['blocktemplate_blob'])
    _, major_end = read_varint(blob, 0)
    _, minor_end = read_varint(blob, major_end)
    _, time_end = read_varint(blob, minor_end)
    headers = rpc(0, 'get_block_headers_range', {'start_height': before[0] - 59,
                                               'end_height': before[0]})['headers']
    median = int(statistics.median(h['timestamp'] for h in headers))
    variants = {
        'malformed': bytearray([0]),
        'obsolete_block_version': varint(1) + blob[major_end:],
        'future_timestamp': blob[:minor_end] + varint(int(time.time()) + 7300) + blob[time_end:],
        'below_median_timestamp': blob[:minor_end] + varint(median - 1) + blob[time_end:],
    }
    # Locate the actual coinbase amount by decoding its prefix, never search/replace bytes.
    offset = time_end + 32 + 4  # previous hash and nonce
    tx_version, offset = read_varint(blob, offset)
    assert tx_version == 2
    _, offset = read_varint(blob, offset)  # unlock height
    inputs, offset = read_varint(blob, offset)
    assert inputs == 1 and blob[offset] == 255  # txin_gen
    _, offset = read_varint(blob, offset + 1)  # generation height
    outputs, offset = read_varint(blob, offset)
    assert outputs == 1
    amount, amount_end = read_varint(blob, offset)
    assert amount == REWARD
    variants['inflated_coinbase'] = blob[:offset] + varint(REWARD + 1) + blob[amount_end:]
    rejected = {}
    for label, candidate in variants.items():
        rejected[label] = rpc(0, 'submit_block', [candidate.hex()], reject=True)
        assert tip(0) == before, (label, 'changed chain')
        print(f'PASS: {label} rejected without changing tip/work')
    # Positive control: the unmodified template is valid at fixed difficulty one.
    assert rpc(0, 'submit_block', [blob.hex()])['status'] == 'OK'
    assert tip(0)[0] == before[0] + 1
    summary = {'result': 'PASS', 'reorg_depth': 3, 'restart_preserved': True,
               'rejected': rejected, 'positive_control_accepted': True,
               'scope': ('two regtest daemons; fixed difficulty 1' if MODE == 'regtest' else
                         'two mainnet-mode daemons; native DAA at floor 1; 120-second historical headers'),
               'common_height': root[0], 'delivery': 'explicit RPC blocks; no P2P or transactions'}
    (WORK / 'result.json').write_text(json.dumps(summary, indent=2) + '\n')
finally:
    for node in list(processes):
        stop(node)
