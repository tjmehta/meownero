#!/usr/bin/env python3
"""Fresh 30-minute native payment/recovery trial. Capped offline container only."""
import asyncio
from collections import Counter
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import random
import signal
import subprocess
import threading
import time

spec = importlib.util.spec_from_file_location('p2p', '/harness/daemon-p2p.py')
p2p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p2p)
PUBLIC, PRIVATE = p2p.PUBLIC, p2p.PRIVATE
PORTS = {'senderA': 19090, 'senderB': 19190, 'recipientA': 19092,
         'recipientB': 19192, 'restored': 19093}
NODES = {'senderA': 0, 'senderB': 1, 'recipientA': 0, 'recipientB': 1, 'restored': 0}
FIELDS = ('tx_hash', 'amount', 'key_image', 'pubkey', 'block_height', 'spent')
RPC_ROWS, GENERATIONS, SAMPLES = [], [], []
LOCK = threading.Lock()
RAW = p2p.request
RESULT = {'schema': 'vanguard-soak/1', 'result': 'INCOMPLETE', 'cohorts': [],
          'generated': [], 'generations': GENERATIONS, 'controls': {},
          'workload_seed': int.from_bytes(os.urandom(16), 'big')}
STARTED = None


class Reply(dict):
    pass


def request(port, path, body):
    with LOCK:
        began = time.monotonic()
        value = RAW(port, path, body)
        observed_body = json.loads(json.dumps(body))
        observed_value = json.loads(json.dumps(value))
        if body.get('method') == 'query_key':
            key = value.get('result', {}).get('key', '')
            observed_value = {'redacted_seed_sha256': hashlib.sha256(key.encode()).hexdigest()}
        if body.get('method') == 'restore_deterministic_wallet':
            seed = observed_body['params'].pop('seed')
            observed_body['params']['redacted_seed_sha256'] = hashlib.sha256(seed.encode()).hexdigest()
            if 'error' in observed_value:
                observed_value = {'error': {'code': observed_value['error'].get('code')}}
        row = {'id': len(RPC_ROWS), 'port': port, 'path': path,
               'request': observed_body, 'response': observed_value,
               'began_s': began, 'ended_s': time.monotonic()}
        RPC_ROWS.append(row)
        with (PUBLIC / 'rpc.jsonl').open('a') as stream:
            stream.write(json.dumps(row, sort_keys=True) + '\n')
        reply = Reply(value)
        reply.rpc_id = row['id']
        return reply


p2p.request = request


async def call(port, path, body):
    return await asyncio.to_thread(request, port, path, body)


async def rpc(node, method, params=None):
    reply = await call(19081 + 100 * node, 'json_rpc',
                       {'jsonrpc': '2.0', 'id': '0', 'method': method, 'params': params or {}})
    if 'error' in reply:
        raise RuntimeError(f'daemon RPC {method}, code {reply["error"].get("code")}')
    result = Reply(reply['result'])
    result.rpc_id = reply.rpc_id
    return result


async def wallet(name, method, params=None):
    reply = await call(PORTS[name], 'json_rpc',
                       {'jsonrpc': '2.0', 'id': '0', 'method': method, 'params': params or {}})
    if 'error' in reply:
        raise RuntimeError(f'{name} wallet RPC {method}, code {reply["error"].get("code")}')
    result = Reply(reply['result'])
    result.rpc_id = reply.rpc_id
    return result


async def endpoint(node, path, params=None):
    return await call(19081 + 100 * node, path, params or {})


async def snapshot():
    row = {'tips': [], 'pools': [], 'rpc_ids': []}
    for node in (0, 1):
        h = await rpc(node, 'get_last_block_header')
        header = h['block_header']
        row['tips'].append([header['height'], header['hash'], header['wide_cumulative_difficulty']])
        row['rpc_ids'].append(h.rpc_id)
    for node in (0, 1):
        pool = await endpoint(node, 'get_transaction_pool')
        row['pools'].append(sorted(tx['id_hash'] for tx in pool.get('transactions', [])))
        row['rpc_ids'].append(pool.rpc_id)
    return row


async def converged(ids=()):
    row = await snapshot()
    return row if row['tips'][0] == row['tips'][1] and row['pools'] == [sorted(ids)] * 2 else None


async def equal_tips():
    row = await snapshot()
    return row if row['tips'][0] == row['tips'][1] else None


async def wait(check, label, seconds=180):
    return await p2p.wait_for(check, label, seconds)


async def state(name):
    refresh = await wallet(name, 'refresh')
    balance = await wallet(name, 'get_balance')
    incoming = await wallet(name, 'incoming_transfers', {'transfer_type': 'all', 'account_index': 0})
    rows = sorted([{k: t[k] for k in FIELDS} for t in incoming.get('transfers', [])],
                  key=lambda t: (t['tx_hash'], t['pubkey']))
    row = {'balance': {k: balance[k] for k in ('balance', 'unlocked_balance')}, 'outputs': rows,
           'rpc_ids': [refresh.rpc_id, balance.rpc_id, incoming.rpc_id]}
    assert len({t['pubkey'] for t in rows}) == len(rows), 'duplicate wallet output'
    assert len({t['key_image'] for t in rows}) == len(rows), 'duplicate wallet key image'
    assert row['balance']['balance'] == sum(t['amount'] for t in rows if not t['spent']), 'wallet balance'
    return row


def comparable(state_row):
    return {key: state_row[key] for key in ('balance', 'outputs')}


def identity(name):
    proc = p2p.PROCS[name]
    path = Path(f'/proc/{proc.pid}')
    stat_text = (path / 'stat').read_text().rsplit(')', 1)[1].split()
    executable = path / 'exe'
    data = executable.read_bytes()
    assert data[:4] == b'\x7fELF' and int.from_bytes(data[18:20], 'little') == 183, 'not native ARM64 ELF'
    return {'name': name, 'pid': proc.pid, 'start_ticks': int(stat_text[19]),
            'executable_path': os.readlink(executable), 'sha256': hashlib.sha256(data).hexdigest(),
            'bytes': len(data), 'command': (path / 'cmdline').read_bytes().decode().rstrip('\0').split('\0'),
            'monotonic_s': time.monotonic()}


async def start(name, command=None):
    if command is None:
        if name.startswith('daemon'):
            p2p.daemon(int(name[-1]))
        else:
            directory = PRIVATE / name
            directory.mkdir(mode=0o700)
            p2p.start(name, [str(p2p.BIN / 'monero-wallet-rpc'), '--rpc-bind-ip', '127.0.0.1',
                '--rpc-bind-port', str(PORTS[name]), '--disable-rpc-login', '--wallet-dir', str(directory),
                '--daemon-address', f'http://127.0.0.1:{19081 + 100 * NODES[name]}', '--trusted-daemon',
                '--allow-mismatched-daemon-version', '--max-concurrency', '1',
                '--log-file', str(PRIVATE / f'{name}.log')])
    else:
        p2p.start(name, command)
    # Wait for exec before inspecting the live process image.
    for _ in range(100):
        expected = 'monerod' if name.startswith('daemon') else 'monero-wallet-rpc'
        if os.readlink(f'/proc/{p2p.PROCS[name].pid}/exe').endswith('/' + expected):
            break
        await asyncio.sleep(0.01)
    row = identity(name)
    row['generation'] = 1 + sum(g['name'] == name for g in GENERATIONS)
    row['exit'] = None
    GENERATIONS.append(row)
    p2p.record('live_generation', **row)
    if not name.startswith('daemon'):
        await wait(lambda: wallet(name, 'get_version'), name + ' startup')
    return row


async def stop(name):
    proc = p2p.PROCS[name]
    current = next(g for g in reversed(GENERATIONS) if g['name'] == name)
    if proc.poll() is None:
        live = identity(name)
        assert (live['pid'], live['start_ticks'], live['sha256']) == (current['pid'], current['start_ticks'], current['sha256'])
        proc.send_signal(signal.SIGTERM)
    try:
        code = await asyncio.to_thread(proc.wait, timeout=20)
    except subprocess.TimeoutExpired:
        proc.kill()
        code = await asyncio.to_thread(proc.wait)
    current['exit'] = code
    current['exited_s'] = time.monotonic()
    p2p.record('generation_exit', name=name, generation=current['generation'], pid=proc.pid, returncode=code)
    del p2p.PROCS[name]
    assert code == 0, 'native child exit: ' + name


def sample():
    proc_rows = {}
    for name, proc in list(p2p.PROCS.items()):
        try:
            fields = Path(f'/proc/{proc.pid}/stat').read_text().rsplit(')', 1)[1].split()
        except FileNotFoundError:
            continue
        proc_rows[name] = {'pid': proc.pid, 'start_ticks': int(fields[19]),
                          'cpu_ticks': int(fields[11]) + int(fields[12]),
                          'rss_bytes': int(fields[21]) * os.sysconf('SC_PAGE_SIZE')}
    row = {'monotonic_s': time.monotonic(), 'processes': proc_rows,
           'memory_current_bytes': int(Path('/sys/fs/cgroup/memory.current').read_text()),
           'memory_peak_bytes': int(Path('/sys/fs/cgroup/memory.peak').read_text()),
           'cpu': {k: int(v) for k, v in (s.split() for s in Path('/sys/fs/cgroup/cpu.stat').read_text().splitlines())},
           'memory_events': {k: int(v) for k, v in (s.split() for s in Path('/sys/fs/cgroup/memory.events').read_text().splitlines())}}
    SAMPLES.append(row)
    with (PUBLIC / 'samples.jsonl').open('a') as stream:
        stream.write(json.dumps(row, sort_keys=True) + '\n')
    assert row['memory_peak_bytes'] <= 4 * 1024**3 and not row['memory_events']['oom'] and not row['memory_events']['oom_kill']
    return row


async def monitor():
    while True:
        sample()
        await asyncio.sleep(10)


async def delay_until(offset):
    while time.monotonic() < STARTED + offset:
        for node in (0, 1):
            info = await endpoint(node, 'get_info')
            assert info.get('status') == 'OK', 'unhealthy idle RPC'
        await wait(p2p.peer_connections, 'idle native peers')
        p2p.record('heartbeat', offset_s=time.monotonic() - STARTED, snapshot=await snapshot())
        await asyncio.sleep(min(30, max(0, STARTED + offset - time.monotonic())))


async def generate(node, count, address, label, synchronize=True):
    assert sum(g['count'] for g in RESULT['generated']) + count <= 210, 'block budget'
    before = await snapshot()
    reply = await rpc(node, 'generateblocks', {'wallet_address': address, 'amount_of_blocks': count})
    assert len(reply['blocks']) == count
    if synchronize:
        await wait(equal_tips, label + ' convergence')
    row = {'label': label, 'node': node, 'count': count, 'hashes': reply['blocks'],
           'rpc_id': reply.rpc_id, 'before': before, 'after': await snapshot()}
    RESULT['generated'].append(row)
    return row


async def binding(payment):
    rows = []
    for node in (0, 1):
        fetched = await endpoint(node, 'get_transactions', {'txs_hashes': [payment['txid']], 'decode_as_json': True})
        assert len(fetched.get('txs', [])) == 1, 'transaction missing'
        tx = fetched['txs'][0]
        assert tx['tx_hash'] == payment['txid'] and tx['in_pool'] is False and tx['block_height'] > 0
        decoded = json.loads(tx['as_json'])
        assert decoded['rct_signatures']['type'] == 7 and all('carrot_v1' in o['target'] for o in decoded['vout'])
        assert sorted(v['key']['k_image'] for v in decoded['vin']) == sorted(payment['key_images'])
        full_hex = tx.get('as_hex') or tx.get('pruned_as_hex', '') + tx.get('prunable_as_hex', '')
        assert full_hex == payment['blob'], 'native transaction byte mismatch'
        block = await rpc(node, 'get_block', {'height': tx['block_height']})
        header = block['block_header']
        body = json.loads(block['json'])
        assert header['orphan_status'] is False and header['height'] == tx['block_height']
        assert body['tx_hashes'].count(payment['txid']) == 1
        rows.append({'tx_rpc_id': fetched.rpc_id, 'block_rpc_id': block.rpc_id,
                     'height': tx['block_height'], 'block_hash': header['hash'], 'previous_hash': header['prev_hash']})
    assert rows[0]['height'] == rows[1]['height'] and rows[0]['block_hash'] == rows[1]['block_hash']
    assert rows[0]['previous_hash'] == rows[1]['previous_hash']
    return rows


async def cohort(number, sender, recipient, addresses, inputs, bridge, partition=False):
    began = time.monotonic()
    before = await wait(lambda: converged(), 'cohort empty pools')
    origin = NODES[sender]
    sender_before = await state(sender)
    inputs[sender] = {o['key_image']: o for o in sender_before['outputs'] if not o['spent']}
    if partition:
        bridge.partition()
        await asyncio.sleep(2)
    rows = []
    existing = {i for c in RESULT['cohorts'] for t in c['transactions'] for i in t['key_images']}
    rng = random.Random(RESULT['workload_seed'] + number)
    for _ in range(8):
        amount = 10**12 + rng.randrange(1, 10) * 10**10
        made = await wallet(sender, 'transfer', {'destinations': [{'amount': amount, 'address': addresses[recipient]}],
                                               'do_not_relay': True, 'get_tx_hex': True})
        images = made['spent_key_images']['key_images']
        assert images and len(images) == len(set(images)) and not set(images) & existing
        assert set(images) <= set(inputs[sender]), 'unfunded input'
        existing.update(images)
        admission = await endpoint(origin, 'send_raw_transaction', {'tx_as_hex': made['tx_blob'], 'do_not_relay': False})
        assert admission.get('status') == 'OK'
        arrived = time.monotonic()
        expected = sorted([t['txid'] for t in rows] + [made['tx_hash']])
        if not partition:
            await wait(lambda: converged(expected), 'incremental peer queue')
        reservation = await wallet(sender, 'refresh')
        pending = await snapshot()
        expected_pools = [[], []]
        expected_pools[origin] = expected
        if not partition:
            expected_pools = [expected] * 2
        assert pending['tips'] == before['tips'] and pending['pools'] == expected_pools
        decoded_reply = await endpoint(origin, 'get_transactions', {'txs_hashes': [made['tx_hash']], 'decode_as_json': True})
        decoded = json.loads(decoded_reply['txs'][0]['as_json'])
        assert decoded['rct_signatures']['type'] == 7 and all('carrot_v1' in v['target'] for v in decoded['vout'])
        assert sorted(v['key']['k_image'] for v in decoded['vin']) == sorted(images)
        row = {'txid': made['tx_hash'], 'blob': made['tx_blob'], 'fee': made['fee'], 'amount': amount,
               'destination': addresses[recipient], 'sender': sender, 'recipient': recipient,
               'key_images': images, 'selected_inputs': [inputs[sender][i] for i in images],
               'construction_rpc_id': made.rpc_id, 'admission_rpc_id': admission.rpc_id,
               'reservation_rpc_id': reservation.rpc_id, 'decoded_rpc_id': decoded_reply.rpc_id,
               'pending': pending, 'origin_arrival_s': arrived, 'peer_arrival_s': time.monotonic() if not partition else None}
        rows.append(row)
        p2p.record('payment_queued', cohort=number, txid=row['txid'], pending=pending)
    queued = await snapshot()
    retry_rpc_id = None
    if partition:
        bridge.rejoin()
        await wait(p2p.peer_connections, 'reconnected native peers')
        retried = await rpc(origin, 'relay_tx', {'txids': [r['txid'] for r in rows]})
        assert retried['status'] == 'OK'
        retry_rpc_id = retried.rpc_id
        await wait(lambda: converged([r['txid'] for r in rows]), 'queued reconnect')
        for row in rows:
            row['peer_arrival_s'] = time.monotonic()
    full_queue = await snapshot()
    assert full_queue['pools'] == [sorted(r['txid'] for r in rows)] * 2
    assert full_queue['tips'] == before['tips']
    drains = []
    for i in range(3):
        drains.append(await generate(origin, 1, addresses[sender], f'cohort{number}-drain{i + 1}'))
        if (await snapshot())['pools'] == [[], []]:
            break
    assert (await snapshot())['pools'] == [[], []]
    for row in rows:
        row['confirmed'] = await binding(row)
        row['confirmed_s'] = time.monotonic()
    observed = await state(recipient)
    wanted = {t['txid']: t['amount'] for c in RESULT['cohorts'] for t in c['transactions'] if t['recipient'] == recipient}
    wanted.update({r['txid']: r['amount'] for r in rows})
    assert len(observed['outputs']) == len(wanted) and {o['tx_hash']: o['amount'] for o in observed['outputs']} == wanted
    spent = {o['tx_hash'] for o in observed['outputs'] if o['spent']}
    expected_spent = {RESULT['restored_spend']['source_txid']} if recipient == 'recipientA' and 'restored_spend' in RESULT else set()
    assert spent == expected_spent
    assert observed['balance']['balance'] == sum(v for k, v in wanted.items() if k not in spent)
    ended = time.monotonic()
    duration = ended - began
    assert duration <= 300, 'cohort deadline'
    row = {'number': number, 'sender': sender, 'recipient': recipient, 'partition': partition,
           'began_s': began, 'ended_s': ended, 'before': before, 'isolated_queue': queued,
           'full_queue': full_queue, 'after': await snapshot(), 'transactions': rows,
           'drain_labels': [g['label'] for g in drains], 'recipient_state': observed,
           'sender_before': sender_before,
           'reconnect_relay_rpc_id': retry_rpc_id,
           'confirmed_tps': 8 / duration}
    RESULT['cohorts'].append(row)
    p2p.record('cohort_complete', number=number, duration_s=duration, payments=8)


async def controlled_reorg(addresses, bridge):
    before = await wait(lambda: converged(), 'common reorg tip')
    wallets = {n: await state(n) for n in ('recipientA', 'recipientB')}
    bridge.partition()
    await asyncio.sleep(2)
    losing = await generate(0, 1, addresses['senderA'], 'reorg-losing', False)
    winning = await generate(1, 2, addresses['senderB'], 'reorg-winning', False)
    diverged = await snapshot()
    assert diverged['tips'][0][1] != diverged['tips'][1][1]
    bridge.rejoin()
    recovered = await wait(lambda: converged(), 'reorg recovery')
    assert recovered['tips'][0][1] == winning['hashes'][-1]
    orphan = []
    for node in (0,):
        block = await rpc(node, 'get_block', {'hash': losing['hashes'][0]})
        assert block['block_header']['orphan_status'] is True, 'losing block not orphaned'
        orphan.append(block.rpc_id)
    after = {n: await state(n) for n in wallets}
    assert {n: comparable(after[n]) for n in after} == {n: comparable(wallets[n]) for n in wallets}
    rebindings = {t['txid']: await binding(t) for c in RESULT['cohorts'] for t in c['transactions']}
    RESULT['reorg'] = {'before': before, 'losing': losing['hashes'], 'winning': winning['hashes'],
                       'diverged': diverged, 'recovered': recovered, 'orphan_rpc_ids': orphan,
                       'wallets_before': wallets, 'wallets_after': after, 'rebindings': rebindings,
                       'completed_s': time.monotonic()}


async def restore_and_controls(addresses, seeds):
    await generate(0, 12, addresses['senderA'], 'restore-unlock')
    original = await state('recipientA')
    assert original['balance']['unlocked_balance'] == original['balance']['balance'] > 0
    await start('restored')
    restore = await wallet('restored', 'restore_deterministic_wallet',
        {'seed': seeds['recipientA'], 'restore_height': 0, 'filename': 'restored', 'password': '', 'autosave_current': True})
    rescan = await wallet('restored', 'rescan_blockchain', {'hard': True})
    restored = await state('restored')
    assert restore['address'] == addresses['recipientA'] and comparable(restored) == comparable(original)
    first = original['outputs'][0]
    sweep = {'key_image': first['key_image'], 'do_not_relay': True, 'get_tx_hex': True}
    alternate = await wallet('recipientA', 'sweep_single', {**sweep, 'address': addresses['recipientB']})
    made = await wallet('restored', 'sweep_single', {**sweep, 'address': addresses['senderA']})
    images = made['spent_key_images']['key_images']
    assert images == alternate['spent_key_images']['key_images'] == [first['key_image']]
    assert made['tx_hash'] != alternate['tx_hash']
    payment = {'txid': made['tx_hash'], 'blob': made['tx_blob'], 'key_images': images,
               'construction_rpc_id': made.rpc_id, 'fee': made['fee'], 'destination': addresses['senderA'],
               'amount': made['amount'], 'source_txid': first['tx_hash'], 'source_amount': first['amount']}

    async def unchanged_control(label, blob, double_spend=False):
        before = await snapshot()
        keys_before = [await endpoint(n, 'is_key_image_spent', {'key_images': images}) for n in (0, 1)]
        replies = [await endpoint(n, 'send_raw_transaction', {'tx_as_hex': blob, 'do_not_relay': False}) for n in (0, 1)]
        assert all(r.get('status') != 'OK' and (not double_spend or r.get('double_spend')) for r in replies)
        after = await snapshot()
        keys_after = [await endpoint(n, 'is_key_image_spent', {'key_images': images}) for n in (0, 1)]
        assert before['tips'] == after['tips'] and before['pools'] == after['pools']
        assert [dict(r) for r in keys_before] == [dict(r) for r in keys_after]
        RESULT['controls'][label] = {'blob': blob, 'before': before, 'after': after,
            'rpc_ids': [r.rpc_id for r in replies], 'key_before_ids': [r.rpc_id for r in keys_before],
            'key_after_ids': [r.rpc_id for r in keys_after]}

    corrupt = bytearray.fromhex(made['tx_blob'])
    corrupt[-1] ^= 1
    await unchanged_control('malformed', '00')
    await unchanged_control('invalid_signature', corrupt.hex())
    admitted = await endpoint(0, 'send_raw_transaction', {'tx_as_hex': made['tx_blob'], 'do_not_relay': False})
    assert admitted.get('status') == 'OK'
    payment['admission_rpc_id'] = admitted.rpc_id
    payment['queued'] = await wait(lambda: converged([made['tx_hash']]), 'restored spend relay')
    await generate(0, 1, addresses['senderA'], 'restored-spend')
    payment['confirmed'] = await binding(payment)
    final_original, final_restored = await state('recipientA'), await state('restored')
    assert comparable(final_original) == comparable(final_restored)
    assert {o['key_image'] for o in final_original['outputs'] if o['spent']} == set(images)
    await unchanged_control('conflicting_spend', alternate['tx_blob'], True)
    RESULT['restore'] = {'original': original, 'restored': restored, 'restore_rpc_id': restore.rpc_id,
        'rescan_rpc_id': rescan.rpc_id, 'final_original': final_original, 'final_restored': final_restored}
    RESULT['restored_spend'] = payment
    RESULT['alternate'] = {'txid': alternate['tx_hash'], 'construction_rpc_id': alternate.rpc_id}


async def main():
    global STARTED
    PRIVATE.mkdir(mode=0o700)
    PUBLIC.mkdir(mode=0o755)
    assert sorted(p.name for p in Path('/sys/class/net').iterdir()) == ['lo']
    assert not Path('/proc/net/route').read_text().splitlines()[1:]
    RESULT['architecture'] = os.uname().machine
    bridge = p2p.Bridge()
    bridge.socket = Path('/run/vanguard/p2p.sock')
    await bridge.start()
    sampling = asyncio.create_task(monitor())
    seeds = {}
    try:
        warmup_start = time.monotonic()
        await start('daemon0')
        await start('daemon1')
        RESULT['genesis'] = await wait(lambda: converged(), 'genesis')
        assert RESULT['genesis']['tips'][0][0] == 0
        await wait(p2p.peer_connections, 'warmup native peers')
        addresses, address_ids, seed_ids = {}, {}, {}
        for name in ('senderA', 'senderB', 'recipientA', 'recipientB'):
            await start(name)
            await wallet(name, 'create_wallet', {'filename': name, 'password': '', 'language': 'English'})
            address = await wallet(name, 'get_address')
            addresses[name], address_ids[name] = address['address'], address.rpc_id
            seed = await wallet(name, 'query_key', {'key_type': 'mnemonic'})
            seeds[name], seed_ids[name] = seed['key'], seed.rpc_id
        RESULT['addresses'] = addresses
        RESULT['address_rpc_ids'] = address_ids
        RESULT['seed_rpc_ids'] = seed_ids
        RESULT['wallet_seed_sha256'] = {n: hashlib.sha256(s.encode()).hexdigest() for n, s in seeds.items()}
        assert len(set(RESULT['wallet_seed_sha256'].values())) == 4
        for n, node in (('senderA', 0), ('senderB', 1)):
            await generate(node, 90, addresses[n], 'funding-' + n)
        funded = {n: await state(n) for n in ('senderA', 'senderB')}
        height = (await snapshot())['tips'][0][0]
        inputs = {n: {o['key_image']: o for o in s['outputs'] if not o['spent'] and height - o['block_height'] >= 60}
                  for n, s in funded.items()}
        assert all(len(v) >= 16 for v in inputs.values()), 'insufficient independent mature inputs'
        RESULT['funded'] = funded
        RESULT['fresh_recipients'] = {n: await state(n) for n in ('recipientA', 'recipientB')}
        assert all(not s['outputs'] and not s['balance']['balance'] for s in RESULT['fresh_recipients'].values())
        RESULT['measured_start'] = await wait(lambda: converged(), 'measured start empty pools')
        RESULT['warmup_seconds'] = time.monotonic() - warmup_start
        assert RESULT['warmup_seconds'] <= 900
        STARTED = time.monotonic()
        RESULT['measured_start_s'], RESULT['start_sample'] = STARTED, sample()
        await cohort(1, 'senderA', 'recipientB', addresses, inputs, bridge)
        await delay_until(360)
        wallet_before = await state('senderB')
        old = next(g for g in reversed(GENERATIONS) if g['name'] == 'senderB')
        await stop('senderB')
        await start('senderB', old['command'])
        opened = await wallet('senderB', 'open_wallet', {'filename': 'senderB', 'password': ''})
        address = await wallet('senderB', 'get_address')
        wallet_after = await state('senderB')
        assert address['address'] == addresses['senderB'] and comparable(wallet_before) == comparable(wallet_after)
        RESULT['wallet_restart'] = {'before': wallet_before, 'after': wallet_after,
            'open_rpc_id': opened.rpc_id, 'address_rpc_id': address.rpc_id, 'completed_s': time.monotonic()}
        await cohort(2, 'senderB', 'recipientA', addresses, inputs, bridge)
        await delay_until(720)
        daemon_before = await snapshot()
        old = next(g for g in reversed(GENERATIONS) if g['name'] == 'daemon0')
        await stop('daemon0')
        await start('daemon0', old['command'])
        daemon_after = await wait(lambda: converged(), 'persistent daemon restart')
        assert daemon_before['tips'] == daemon_after['tips'] and daemon_before['pools'] == daemon_after['pools']
        await wait(p2p.peer_connections, 'restarted native handshake')
        RESULT['daemon_restart'] = {'before': daemon_before, 'after': daemon_after, 'completed_s': time.monotonic()}
        await cohort(3, 'senderA', 'recipientB', addresses, inputs, bridge, True)
        await delay_until(1080)
        await controlled_reorg(addresses, bridge)
        await delay_until(1440)
        await asyncio.wait_for(restore_and_controls(addresses, seeds), 300)
        await cohort(4, 'senderB', 'recipientA', addresses, inputs, bridge)
        await delay_until(1740)
        RESULT['final_bindings'] = {t['txid']: await binding(t) for c in RESULT['cohorts'] for t in c['transactions']}
        RESULT['final_bindings'][RESULT['restored_spend']['txid']] = await binding(RESULT['restored_spend'])
        RESULT['final_wallets'] = {n: await state(n) for n in PORTS}
        assert comparable(RESULT['final_wallets']['recipientA']) == comparable(RESULT['final_wallets']['restored'])
        for sender in ('senderA', 'senderB'):
            workload = [t for c in RESULT['cohorts'] for t in c['transactions'] if t['sender'] == sender]
            spent = {o['key_image'] for o in RESULT['final_wallets'][sender]['outputs'] if o['spent']}
            assert spent == {i for t in workload for i in t['key_images']}, 'sender exactly-once spent reconciliation'
            assert sum(t['amount'] + t['fee'] for t in workload) == sum(
                o['amount'] for o in RESULT['final_wallets'][sender]['outputs'] if o['spent']) - sum(
                o['amount'] for o in RESULT['final_wallets'][sender]['outputs'] if o['tx_hash'] in {t['txid'] for t in workload}), 'principal/fee/change'
        await delay_until(1800)
        RESULT['final'] = await wait(lambda: converged(), 'final empty queues')
        RESULT['final_peers'] = await wait(p2p.peer_connections, 'final native peers')
        RESULT['final_peer_rpc_ids'] = [len(RPC_ROWS) - 2, len(RPC_ROWS) - 1]
        RESULT['final_live'] = {name: identity(name) for name in p2p.PROCS}
        RESULT['end_sample'] = sample()
        RESULT['measured_end_s'] = time.monotonic()
        RESULT['measured_seconds'] = RESULT['measured_end_s'] - STARTED
        assert 1800 <= RESULT['measured_seconds'] <= 2400
        RESULT['transactions'] = sum(len(c['transactions']) for c in RESULT['cohorts'])
        assert RESULT['transactions'] == 32
        RESULT['result'] = 'PASS_SCENARIO'
    except BaseException as error:
        RESULT['result'] = 'FAIL_SCENARIO'
        RESULT['error_type'] = type(error).__name__
        raise
    finally:
        seeds.clear()
        sampling.cancel()
        monitor_error = None
        try:
            await sampling
        except asyncio.CancelledError:
            pass
        except BaseException as error:
            monitor_error = type(error).__name__
            RESULT['result'] = 'FAIL_SCENARIO'
            RESULT['monitor_error'] = monitor_error
        RESULT['listeners_before_shutdown'] = p2p.live_listeners()
        await bridge.close()
        cleanup_errors = []
        for name in list(p2p.PROCS):
            try:
                await stop(name)
            except BaseException as error:
                cleanup_errors.append({'name': name, 'error_type': type(error).__name__})
        RESULT['cleanup_errors'] = cleanup_errors
        if cleanup_errors:
            RESULT['result'] = 'FAIL_SCENARIO'
        RESULT['shutdown_sample'] = sample()
        RESULT['bridge'] = {'connections': bridge.connections, 'forwarded_bytes': bridge.forwarded}
        RESULT['interfaces'] = sorted(p.name for p in Path('/sys/class/net').iterdir())
        RESULT['routes'] = Path('/proc/net/route').read_text().splitlines()[1:]
        (PUBLIC / 'result.json').write_text(json.dumps(RESULT, indent=2, sort_keys=True) + '\n')
        p2p.record('trial_complete', result=RESULT['result'], transactions=RESULT.get('transactions', 0))
        assert RESULT['result'] == 'PASS_SCENARIO', 'trial or cleanup failed'


if __name__ == '__main__':
    asyncio.run(asyncio.wait_for(main(), 3300))
