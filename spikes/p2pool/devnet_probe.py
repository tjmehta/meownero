#!/usr/bin/env python3
"""Offline native-DAA daemon experiment; no P2Pool node or custody/payout claim."""
import ctypes
import ctypes.util
import hashlib
import json
from pathlib import Path
import subprocess
import time
import urllib.request

WORK = Path('/work')
ADDRESS = 'M9Lds8CcBgCJbqSiUvYfS3BfhEdxZmv8pDt25oW1LzxrZv9Uq6ARagiFViMGUE3gJk5VPWingCXVf1p2tyAy6SUeSLMMvfc'
REWARD = 900000000000


def rpc(method, params=None):
    request = urllib.request.Request('http://127.0.0.1:19081/json_rpc',
        json.dumps({'jsonrpc': '2.0', 'id': '0', 'method': method,
                    'params': {} if params is None else params}).encode(),
        {'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=90) as response:
        result = json.load(response)
    transcript.append({'method': method, 'response': result})
    return result


def value(method, params=None):
    response = rpc(method, params)
    assert 'error' not in response, response
    return response['result']


def varint(n):
    result = bytearray()
    while n >= 128:
        result.append((n & 127) | 128)
        n >>= 7
    result.append(n)
    return result


def read(data, offset):
    result = shift = 0
    while True:
        byte = data[offset]
        offset += 1
        result |= (byte & 127) << shift
        if byte < 128:
            return result, offset
        shift += 7
        assert shift < 64


class Subscriber:
    """Use installed libzmq directly; no Python package or pool dependency."""
    def __init__(self):
        self.lib = ctypes.CDLL(ctypes.util.find_library('zmq'))
        for name, args, result in [
            ('zmq_ctx_new', [], ctypes.c_void_p),
            ('zmq_socket', [ctypes.c_void_p, ctypes.c_int], ctypes.c_void_p),
            ('zmq_setsockopt', [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_size_t], ctypes.c_int),
            ('zmq_connect', [ctypes.c_void_p, ctypes.c_char_p], ctypes.c_int),
            ('zmq_recv', [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int], ctypes.c_int),
            ('zmq_close', [ctypes.c_void_p], ctypes.c_int),
            ('zmq_ctx_term', [ctypes.c_void_p], ctypes.c_int),
        ]:
            fn = getattr(self.lib, name)
            fn.argtypes, fn.restype = args, result
        self.context = self.lib.zmq_ctx_new()
        self.socket = self.lib.zmq_socket(self.context, 2)  # ZMQ_SUB
        assert self.context and self.socket
        topic = b'json-full-miner_data'
        assert self.lib.zmq_setsockopt(self.socket, 6, topic, len(topic)) == 0
        timeout = ctypes.c_int(10000)
        assert self.lib.zmq_setsockopt(self.socket, 27, ctypes.byref(timeout), 4) == 0
        assert self.lib.zmq_connect(self.socket, b'tcp://127.0.0.1:19083') == 0

    def receive(self):
        buffer = ctypes.create_string_buffer(65536)
        size = self.lib.zmq_recv(self.socket, buffer, len(buffer), 0)
        assert 0 < size < len(buffer), 'ZMQ notification absent or too large'
        return buffer.raw[:size].decode()

    def close(self):
        self.lib.zmq_close(self.socket)
        self.lib.zmq_ctx_term(self.context)


transcript = []
daemon = subscriber = None
try:
    binary = '/src/build/release/bin/monerod'
    (WORK / 'daemon.sha256').write_text(hashlib.sha256(Path(binary).read_bytes()).hexdigest() + '\n')
    with (WORK / 'daemon.stdout.log').open('w') as log:
        daemon = subprocess.Popen([binary, '--data-dir', '/work/node', '--offline',
            '--non-interactive', '--no-igd', '--disable-dns-checkpoints', '--check-updates', 'disabled',
            '--max-concurrency', '1', '--p2p-bind-ip', '127.0.0.1', '--p2p-bind-port', '19080',
            '--rpc-bind-ip', '127.0.0.1', '--rpc-bind-port', '19081',
            '--zmq-rpc-bind-ip', '127.0.0.1', '--zmq-rpc-bind-port', '19082',
            '--log-level', '1,blockchain:DEBUG,verify:ERROR',
            '--zmq-pub', 'tcp://127.0.0.1:19083', '--log-file', '/work/daemon.log'],
            stdout=log, stderr=subprocess.STDOUT)
    for _ in range(120):
        assert daemon.poll() is None, 'daemon exited'
        try:
            info = value('get_info')
            break
        except OSError:
            time.sleep(0.5)
    else:
        raise AssertionError('startup timeout')
    assert info['mainnet'] and not info['testnet'] and not info['stagenet']
    assert value('get_version')['version'] >= (3 << 16 | 10)
    genesis = value('get_block_header_by_height', {'height': 0})['block_header']
    assert genesis['reward'] == 0
    miner = value('get_miner_data')
    assert miner['major_version'] == 16 and miner['height'] == 1
    assert miner['already_generated_coins'] == 0
    assert int(miner['difficulty'], 16) == 1
    assert miner['seed_hash'] == genesis['hash'] == miner['prev_id']
    # P2Pool's RPC parser accepts an omitted empty backlog (unlike its ZMQ parser).
    assert miner['median_weight'] >= 300000 and miner.get('tx_backlog', []) == []
    upstream = json.loads(subprocess.check_output(['/work/probe',
        str(miner['already_generated_coins']), str(miner['height']), '0']))
    assert upstream['major_version'] != miner['major_version']
    assert upstream['reward'] > REWARD
    template = value('get_block_template', {'wallet_address': ADDRESS})
    assert template['expected_reward'] == REWARD and template['difficulty'] == 1
    blob = bytearray.fromhex(template['blocktemplate_blob'])
    offset = 0
    for _ in range(3):
        _, offset = read(blob, offset)
    offset += 32 + 4
    version, offset = read(blob, offset)
    unlock, offset = read(blob, offset)
    inputs, offset = read(blob, offset)
    assert version == 2 and unlock == 61 and inputs == 1 and blob[offset] == 255
    height, offset = read(blob, offset + 1)
    outputs, offset = read(blob, offset)
    amount, end = read(blob, offset)
    assert height == 1 and outputs == 1 and amount == REWARD and blob[end] == 3
    inflated = blob[:offset] + varint(upstream['reward']) + blob[end:]
    rejection = rpc('submit_block', [inflated.hex()])
    assert 'error' in rejection, rejection
    underpaid = blob[:offset] + varint(600000000000) + blob[end:]
    underpayment_rejection = rpc('submit_block', [underpaid.hex()])
    assert 'error' in underpayment_rejection, underpayment_rejection
    assert value('get_last_block_header')['block_header']['height'] == 0
    subscriber = Subscriber()
    time.sleep(1)  # Allow the local PUB/SUB subscription handshake.
    assert value('submit_block', [blob.hex()])['status'] == 'OK'
    notification = subscriber.receive()
    (WORK / 'zmq-miner-data.txt').write_text(notification + '\n')
    assert notification.startswith('json-full-miner_data:')
    notified = json.loads(notification.split(':', 1)[1])
    assert notified['height'] == 2 and notified['major_version'] == 16
    headers = value('get_block_headers_range', {'start_height': 0, 'end_height': 1})['headers']
    assert [h['reward'] for h in headers] == [0, REWARD]
    daemon_log = (WORK / 'daemon.log').read_text()
    assert 'coinbase transaction spend too much money' in daemon_log
    assert "coinbase transaction doesn't use full amount of block reward" in daemon_log
    result = {'compatible': False, 'pool_started': False,
        'native_daa': True, 'fixed_difficulty_override': False,
        'genesis': genesis['hash'], 'daemon_network_label': 'mainnet',
        'offline_synchronized': info['synchronized'],
        'p2pool_reward_at_height_1': upstream['reward'], 'meownero_reward_at_height_1': amount,
        'p2pool_version_at_height_1': upstream['major_version'], 'meownero_version_at_height_1': 16,
        'p2pool_amount_mutation_rejected': rejection['error'],
        'tail_amount_mutation_rejected': underpayment_rejection['error'],
        'original_template_accepted': True, 'zmq_miner_height': notified['height'],
        'rpc_methods_exercised': sorted({entry['method'] for entry in transcript})}
    (WORK / 'devnet-results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
finally:
    (WORK / 'rpc-transcript.json').write_text(json.dumps(transcript, indent=2) + '\n')
    if subscriber:
        subscriber.close()
    if daemon:
        daemon.terminate()
        try:
            assert daemon.wait(timeout=20) == 0
        except subprocess.TimeoutExpired:
            daemon.kill()
            daemon.wait()
            raise
