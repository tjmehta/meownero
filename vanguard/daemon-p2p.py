#!/usr/bin/env python3
"""Offline FCMP++ daemon P2P witness over a bounded AF_UNIX byte bridge.

Run only inside the network-disabled, resource-capped container in
run-daemon-p2p.py. The daemons retain their native Levin P2P implementation:
the bridge copies whole native frames between loopback endpoints through one
private Unix stream. It also replays and mutates captured native notifications.
"""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import struct
import subprocess
import time
import urllib.request

WORK = Path('/out')
PRIVATE = WORK / 'private'
PUBLIC = WORK / 'public'
BIN = Path('/src/build/vanguard/bin')
SIGNATURE = 0x0101010101012101
HEADER = struct.Struct('<QQBIiII')
MAX_FRAME = 16 * 1024 * 1024
TX_COMMAND = 2002
BLOCK_COMMANDS = (2001, 2008)
PROCS = {}
EVENTS = []


def digest(data):
    return hashlib.sha256(data).hexdigest()


def record(event, **fields):
    row = {'event': event, 'monotonic_s': round(time.monotonic(), 3), **fields}
    EVENTS.append(row)
    with (PUBLIC / 'events.jsonl').open('a') as stream:
        stream.write(json.dumps(row, sort_keys=True) + '\n')
    print(json.dumps(row, sort_keys=True), flush=True)


def request(port, path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(f'http://127.0.0.1:{port}/{path}', data,
                                 {'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=120) as response:
        return json.load(response)


async def rpc(node, method, params=None):
    port = 19081 + 100 * node
    result = await asyncio.to_thread(request, port, 'json_rpc',
        {'jsonrpc': '2.0', 'id': '0', 'method': method, 'params': params or {}})
    if 'error' in result:
        raise RuntimeError(f'daemon RPC {method}: {result["error"].get("message", "error")}')
    return result['result']


async def endpoint(node, path, params=None):
    result = await asyncio.to_thread(request, 19081 + 100 * node, path, params or {})
    if result.get('status') not in (None, 'OK'):
        raise RuntimeError(f'daemon endpoint {path}: {result.get("status")}')
    return result


async def wallet(method, params=None):
    result = await asyncio.to_thread(request, 19090, 'json_rpc',
        {'jsonrpc': '2.0', 'id': '0', 'method': method, 'params': params or {}})
    if 'error' in result:
        raise RuntimeError(f'wallet RPC {method}: {result["error"].get("message", "error")}')
    return result['result']


async def wait_for(check, label, seconds=120):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if any(p.poll() is not None for p in PROCS.values()):
            raise RuntimeError(f'process exited while waiting for {label}')
        try:
            value = await check()
            if value:
                return value
        except (OSError, KeyError, TimeoutError):
            pass
        await asyncio.sleep(0.25)
    raise TimeoutError(label)


async def tip(node):
    h = (await rpc(node, 'get_last_block_header'))['block_header']
    return [h['height'], h['hash'], h['wide_cumulative_difficulty']]


async def equal_tip():
    a, b = await tip(0), await tip(1)
    return a if a == b else None


async def pool(node):
    return {tx['id_hash'] for tx in (await endpoint(node, 'get_transaction_pool')).get('transactions', [])}


async def key_image_status(node, image):
    return (await endpoint(node, 'is_key_image_spent', {'key_images': [image]}))['spent_status'][0]


async def peer_connections():
    a = (await rpc(0, 'get_connections'))['connections']
    b = (await rpc(1, 'get_connections'))['connections']
    return [len(a), len(b)] if a and b else None


def start(name, args):
    with (PRIVATE / f'{name}.stdout.log').open('a') as log:
        PROCS[name] = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=log,
                                       stderr=subprocess.STDOUT)
    record('process_started', name=name, pid=PROCS[name].pid, command=args)


def daemon(node):
    name = f'daemon{node}'
    data = PRIVATE / name
    data.mkdir(mode=0o700)
    args = [str(BIN / 'monerod'), '--data-dir', str(data), '--regtest', '--keep-fakechain',
            '--fixed-difficulty', '1', '--non-interactive', '--no-igd', '--allow-local-ip',
            '--disable-dns-checkpoints', '--check-updates', 'disabled', '--hide-my-port',
            '--max-concurrency', '1', '--no-zmq', '--rpc-ssl', 'disabled',
            '--p2p-bind-ip', '127.0.0.1', '--p2p-bind-port', str(19080 + 100 * node),
            '--rpc-bind-ip', '127.0.0.1', '--rpc-bind-port', str(19081 + 100 * node),
            '--add-exclusive-node', f'127.0.0.1:{20080 + 100 * node}',
            '--log-level', '1', '--log-file', str(PRIVATE / f'{name}.log')]
    start(name, args)


class Session:
    def __init__(self, u_writer, b_writer):
        self.u_writer, self.b_writer = u_writer, b_writer

    def close(self):
        self.u_writer.close()
        self.b_writer.close()


class Bridge:
    def __init__(self):
        self.enabled = True
        self.session = None
        self.frames = []
        self.connections = 0
        self.forwarded = 0
        self.socket = PRIVATE / 'p2p.sock'
        self.client_unix_writer = None
        self.client_unix_lock = asyncio.Lock()

    async def start(self):
        self.unix_server = await asyncio.start_unix_server(self.unix_side, str(self.socket))
        os.chmod(self.socket, 0o600)
        self.tcp_server = await asyncio.start_server(self.tcp_side, '127.0.0.1', 20080)
        record('bridge_ready', unix_socket=str(self.socket), socket_mode=oct(self.socket.stat().st_mode & 0o777),
               max_frame=MAX_FRAME)

    async def tcp_side(self, a_reader, a_writer):
        if not self.enabled:
            a_writer.close()
            return
        try:
            u_reader, u_writer = await asyncio.open_unix_connection(str(self.socket))
            self.client_unix_writer = u_writer
            await asyncio.gather(self.pipe(a_reader, u_writer, 'a_to_b', capture=False,
                                           lock=self.client_unix_lock),
                                 self.pipe(u_reader, a_writer, 'b_to_a', capture=False))
        except (OSError, asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            if 'u_writer' in locals() and self.client_unix_writer is u_writer:
                self.client_unix_writer = None
            a_writer.close()
            if 'u_writer' in locals():
                u_writer.close()

    async def unix_side(self, u_reader, u_writer):
        if not self.enabled:
            u_writer.close()
            return
        try:
            b_reader, b_writer = await asyncio.open_connection('127.0.0.1', 19180)
            self.connections += 1
            self.session = Session(u_writer, b_writer)
            record('bridge_connected', sequence=self.connections)
            await asyncio.gather(self.pipe(u_reader, b_writer, 'a_to_b', capture=True),
                                 self.pipe(b_reader, u_writer, 'b_to_a', capture=True))
        except (OSError, asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            if 'b_writer' in locals() and self.session and self.session.b_writer is b_writer:
                self.session = None
            u_writer.close()
            if 'b_writer' in locals():
                b_writer.close()

    async def pipe(self, reader, writer, direction, capture, lock=None):
        try:
            while self.enabled:
                head = await reader.readexactly(HEADER.size)
                sig, size, _return, command, _code, _flags, version = HEADER.unpack(head)
                if sig != SIGNATURE or size > MAX_FRAME or version != 1:
                    raise ValueError('bounded Levin frame check')
                packet = head + await reader.readexactly(size)
                if capture:
                    self.frames.append((direction, command, packet))
                    self.forwarded += len(packet)
                    with (PUBLIC / 'wire.jsonl').open('a') as trace:
                        trace.write(json.dumps({'direction': direction, 'command': command,
                            'bytes': len(packet), 'sha256': digest(packet)}) + '\n')
                if lock:
                    async with lock:
                        writer.write(packet)
                        await writer.drain()
                else:
                    writer.write(packet)
                    await writer.drain()
        except (OSError, asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            writer.close()

    def partition(self):
        self.enabled = False
        if self.session:
            self.session.close()
        if self.client_unix_writer:
            self.client_unix_writer.close()
        record('bridge_partitioned', forwarded_bytes=self.forwarded, connections=self.connections)

    def rejoin(self):
        self.enabled = True
        record('bridge_rejoined')

    def captured(self, direction, commands, blob=None):
        for d, cmd, packet in reversed(self.frames):
            if d == direction and cmd in commands and (blob is None or blob in packet[HEADER.size:]):
                return packet
        return None

    async def inject(self, name, direction, packet):
        if direction != 'a_to_b' or not self.session or not self.client_unix_writer:
            raise RuntimeError('no bridge session for injection')
        async with self.client_unix_lock:
            self.client_unix_writer.write(packet)
            await self.client_unix_writer.drain()
        (PUBLIC / 'frames' / f'{name}.bin').write_bytes(packet)
        record('frame_injected', name=name, direction=direction,
               command=HEADER.unpack(packet[:HEADER.size])[3], bytes=len(packet), sha256=digest(packet))

    async def close(self):
        self.partition()
        self.tcp_server.close()
        self.unix_server.close()
        await self.tcp_server.wait_closed()
        await self.unix_server.wait_closed()
        self.socket.unlink(missing_ok=True)


def changed_packet(packet, original, replacement):
    assert len(original) == len(replacement)
    payload = packet[HEADER.size:]
    if payload.count(original) != 1:
        raise RuntimeError(f'expected one exact binary payload, saw {payload.count(original)}')
    return packet[:HEADER.size] + payload.replace(original, replacement, 1)


def varint_end(blob, offset):
    for _ in range(10):
        value = blob[offset]
        offset += 1
        if value < 128:
            return offset
    raise AssertionError('unterminated block header varint')


def miner_tx_offset(block_blob):
    offset = 0
    for _ in range(3):
        offset = varint_end(block_blob, offset)
    return offset + 32 + 4  # previous block id and nonce


def live_listeners():
    rows = []
    for table in ('tcp', 'tcp6'):
        for line in Path('/proc/net/' + table).read_text().splitlines()[1:]:
            fields = line.split()
            if fields[3] == '0A':
                address = fields[1]
                if not address.startswith(('0100007F:', '00000000000000000000000001000000:')):
                    raise AssertionError('non-loopback TCP listener')
                rows.append({'table': table, 'local': address})
    return rows


async def unchanged(before, image):
    now = {'tips': [await tip(n) for n in (0, 1)],
           'pools': [sorted(await pool(n)) for n in (0, 1)],
           'key_images': [await key_image_status(n, image) for n in (0, 1)]}
    if now != before:
        raise AssertionError(f'state changed on rejected/replayed input: {before} != {now}')
    return now


async def snapshot(image):
    return {'tips': [await tip(n) for n in (0, 1)],
            'pools': [sorted(await pool(n)) for n in (0, 1)],
            'key_images': [await key_image_status(n, image) for n in (0, 1)]}


async def main():
    PRIVATE.mkdir(mode=0o700)
    PUBLIC.mkdir(mode=0o755)
    (PUBLIC / 'frames').mkdir()
    if sorted(p.name for p in Path('/sys/class/net').iterdir()) != ['lo']:
        raise RuntimeError('container has a non-loopback network interface')
    if Path('/proc/net/route').read_text().splitlines()[1:]:
        raise RuntimeError('container has a network route')
    record('network_containment', interfaces=['lo'], routes=0,
           tcp_listeners_before=Path('/proc/net/tcp').read_text())
    bridge = Bridge()
    await bridge.start()
    try:
        daemon(0)
        daemon(1)
        await wait_for(lambda: equal_tip(), 'initial daemon convergence')
        await wait_for(lambda: asyncio.sleep(0, result=bridge.session is not None), 'native P2P bridge')
        peers = await wait_for(peer_connections, 'native P2P handshake')
        listeners = live_listeners()
        (PUBLIC / 'network-live.json').write_text(json.dumps({'interfaces': ['lo'],
            'routes': [], 'listeners': listeners, 'socket_mode': oct(bridge.socket.stat().st_mode & 0o777)}, indent=2) + '\n')
        record('p2p_ready', genesis=await equal_tip(), connections=bridge.connections,
               daemon_peer_counts=peers,
               listeners=listeners)
        wallet_dir = PRIVATE / 'wallet'
        wallet_dir.mkdir(mode=0o700)
        start('wallet', [str(BIN / 'monero-wallet-rpc'), '--rpc-bind-ip', '127.0.0.1',
              '--rpc-bind-port', '19090', '--disable-rpc-login', '--wallet-dir', str(wallet_dir),
              '--daemon-address', 'http://127.0.0.1:19081', '--trusted-daemon',
              '--allow-mismatched-daemon-version', '--max-concurrency', '1',
              '--log-file', str(PRIVATE / 'wallet.log')])
        await wait_for(lambda: wallet('get_version'), 'wallet RPC')
        await wallet('create_wallet', {'filename': 'disposable', 'password': '', 'language': 'English'})
        address = (await wallet('get_address'))['address']
        generated = await rpc(0, 'generateblocks', {'wallet_address': address, 'amount_of_blocks': 70})
        if len(generated['blocks']) != 70:
            raise AssertionError('funding block count')
        await wait_for(equal_tip, 'P2P header/block sync after funding', 180)
        record('funded_and_synced', tip=await equal_tip(), bridge_bytes=bridge.forwarded)
        await wallet('refresh')
        balance = await wallet('get_balance')
        if balance['unlocked_balance'] <= 0:
            raise AssertionError('no spendable coinbase')
        sent = await wallet('transfer', {'destinations': [{'amount': 1_000_000_000_000, 'address': address}]})
        txid = sent['tx_hash']
        await wait_for(lambda: pool_contains(1, txid), 'P2P transaction relay', 180)
        txrow = (await endpoint(0, 'get_transactions', {'txs_hashes': [txid], 'decode_as_json': True}))['txs'][0]
        decoded = json.loads(txrow['as_json'])
        if decoded['rct_signatures']['type'] != 7:
            raise AssertionError('expected FCMP++ transaction type 7')
        image = decoded['vin'][0]['key']['k_image']
        txblob = bytes.fromhex(txrow['as_hex'])
        tx_packet = bridge.captured('a_to_b', (TX_COMMAND,), txblob)
        if not tx_packet:
            raise AssertionError('FCMP++ transaction absent from native P2P capture')
        record('fcmp_transaction_relayed', txid=txid, key_image=image,
               tx_bytes=len(txblob), packet_sha256=digest(tx_packet),
               pools=[sorted(await pool(n)) for n in (0, 1)])
        await bridge.inject('duplicate-transaction', 'a_to_b', tx_packet)
        before = await snapshot(image)
        await asyncio.sleep(1)
        await unchanged(before, image)
        bad_tx = bytearray(txblob)
        bad_tx[:10] = b'\x80' * 10  # malformed transaction varint before key-image admission
        await bridge.inject('malformed-transaction', 'a_to_b', changed_packet(tx_packet, txblob, bytes(bad_tx)))
        await asyncio.sleep(2)
        await unchanged(before, image)
        record('transaction_adversarial_unchanged', state=before)
        await rpc(0, 'generateblocks', {'wallet_address': address, 'amount_of_blocks': 1})
        await wait_for(equal_tip, 'confirmed transaction block relay', 120)
        await wait_for(lambda: key_images_confirmed(image), 'confirmed key image', 60)
        empty = await rpc(0, 'generateblocks', {'wallet_address': address, 'amount_of_blocks': 1})
        await wait_for(equal_tip, 'empty block relay', 120)
        confirmed = await snapshot(image)
        record('confirmed_on_both', txid=txid, state=confirmed)
        block_blob = bytes.fromhex((await rpc(0, 'get_block', {'hash': empty['blocks'][0]}))['blob'])
        block_packet = bridge.captured('a_to_b', BLOCK_COMMANDS, block_blob)
        if not block_packet:
            raise AssertionError('confirmed block absent from native P2P capture')
        header0 = (await rpc(0, 'get_block_header_by_hash', {'hash': empty['blocks'][0]}))['block_header']
        header1 = (await rpc(1, 'get_block_header_by_hash', {'hash': empty['blocks'][0]}))['block_header']
        if header0 != header1:
            raise AssertionError('relayed P2P block header differs across daemons')
        record('native_header_block_delivered', hash=empty['blocks'][0],
               major_version=header0['major_version'], height=header0['height'],
               block_bytes=len(block_blob), packet_sha256=digest(block_packet))
        await bridge.inject('duplicate-block', 'a_to_b', block_packet)
        await asyncio.sleep(1)
        await unchanged(confirmed, image)
        bad_header = bytearray(block_blob)
        bad_header[:10] = b'\x80' * 10
        await bridge.inject('malformed-header', 'a_to_b', changed_packet(block_packet, block_blob, bytes(bad_header)))
        await asyncio.sleep(1)
        await unchanged(confirmed, image)
        bad_block = bytearray(block_blob)
        tx_offset = miner_tx_offset(block_blob)
        if bad_block[tx_offset] != 2:
            raise AssertionError('unexpected miner transaction version')
        bad_block[tx_offset] = 0  # invalid coinbase transaction body, valid Levin envelope
        await bridge.inject('malformed-block', 'a_to_b', changed_packet(block_packet, block_blob, bytes(bad_block)))
        await asyncio.sleep(1)
        await unchanged(confirmed, image)
        record('block_adversarial_unchanged', state=confirmed)
        bridge.partition()
        old_tip = await tip(0)
        await endpoint(1, 'pop_blocks', {'nblocks': 2, 'keep_txs': False})
        await rpc(1, 'flush_txpool', {'txids': [txid]})
        branch = await rpc(1, 'generateblocks', {'wallet_address': address, 'amount_of_blocks': 3})
        if await tip(0) != old_tip or await tip(1) == old_tip:
            raise AssertionError('partition did not isolate competing branch')
        record('partition_and_branch', old_tip=old_tip, branch=branch['blocks'], peer_tip=await tip(1))
        bridge.rejoin()
        await wait_for(equal_tip, 'P2P reorg after reconnect', 180)
        rolled = await snapshot(image)
        if any(status == 1 for status in rolled['key_images']):
            raise AssertionError('confirmed key image survived reorg')
        old_header = (await rpc(0, 'get_block_header_by_hash', {'hash': old_tip[1]}))['block_header']
        if not old_header['orphan_status']:
            raise AssertionError('old transaction block not orphaned')
        record('reorg_key_image_rollback', state=rolled, orphan=old_tip[1],
               reconnects=bridge.connections)
        await rpc(1, 'generateblocks', {'wallet_address': address, 'amount_of_blocks': 1})
        await wait_for(equal_tip, 'healthy P2P relay after adversarial inputs', 120)
        record('healthy_subsequent_exchange', tip=await equal_tip(),
               bridge_bytes=bridge.forwarded, reconnects=bridge.connections)
        (PUBLIC / 'result.json').write_text(json.dumps({'result': 'PASS', 'txid': txid,
            'key_image': image, 'confirmed': confirmed, 'rolled_back': rolled,
            'final_tip': await equal_tip(), 'bridge_connections': bridge.connections,
            'bridge_bytes': bridge.forwarded}, indent=2) + '\n')
    finally:
        listeners_before_shutdown = live_listeners()
        await bridge.close()
        for proc in PROCS.values():
            if proc.poll() is None:
                proc.send_signal(signal.SIGTERM)
        for name, proc in PROCS.items():
            try:
                proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            record('process_exit', name=name, returncode=proc.returncode)
        for name in ('daemon0', 'daemon1'):
            for suffix in ('.log', '.stdout.log'):
                path = PRIVATE / (name + suffix)
                if path.exists():
                    shutil.copy2(path, PUBLIC / path.name)
        (PUBLIC / 'containment.json').write_text(json.dumps({
            'interfaces': sorted(p.name for p in Path('/sys/class/net').iterdir()),
            'routes': Path('/proc/net/route').read_text().splitlines()[1:],
            'listeners_before_shutdown': listeners_before_shutdown,
            'tcp': Path('/proc/net/tcp').read_text(),
            'tcp6': Path('/proc/net/tcp6').read_text()}, indent=2) + '\n')


async def pool_contains(node, txid):
    return txid in await pool(node)


async def key_images_confirmed(image):
    return all([(await key_image_status(node, image)) == 1 for node in (0, 1)])


if __name__ == '__main__':
    asyncio.run(main())
