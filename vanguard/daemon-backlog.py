#!/usr/bin/env python3
"""Finite 8+8 native backlog/drain witness. Run only in the capped container."""
import asyncio
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import shutil
import signal
import subprocess
import threading
import time

spec = importlib.util.spec_from_file_location('load', '/harness/daemon-load.py')
load = importlib.util.module_from_spec(spec)
spec.loader.exec_module(load)
p2p = load.p2p
PUBLIC, PRIVATE = p2p.PUBLIC, p2p.PRIVATE
SEED, COHORTS, FUNDING, MAX_BLOCKS, LIMIT_SECONDS = 1346, (8, 8), 90, 96, 1000
raw_request = p2p.request
rpc_lock = threading.Lock()
RPC_ROWS = []


def request(port, path, body):
    began = time.monotonic()
    response = raw_request(port, path, body)
    # Disposable wallet seeds remain private. Record only their digests.
    observed = response
    if body.get('method') == 'query_key':
        observed = {'redacted_seed_sha256': hashlib.sha256(response['result']['key'].encode()).hexdigest()}
    with rpc_lock, (PUBLIC / 'rpc.jsonl').open('a') as stream:
        row = {'id': len(RPC_ROWS), 'port': port, 'path': path, 'request': body,
               'response': observed, 'began_s': began, 'ended_s': time.monotonic()}
        RPC_ROWS.append(row)
        stream.write(json.dumps(row, sort_keys=True) + '\n')
    return response


p2p.request = request


async def snapshot():
    row = {'tips': [], 'pools': [], 'rpc_ids': {'tips': [], 'pools': []}}
    for field, query in (('tips', p2p.tip), ('pools', p2p.pool)):
        for n in (0, 1):
            value = await query(n)
            row[field].append(sorted(value) if field == 'pools' else value)
            row['rpc_ids'][field].append(len(RPC_ROWS) - 1)
    return row


async def state(name):
    await load.wallet(name, 'refresh')
    balance = await load.wallet(name, 'get_balance')
    transfers = (await load.wallet(name, 'incoming_transfers',
                 {'transfer_type': 'all', 'account_index': 0})).get('transfers', [])
    fields = ('tx_hash', 'amount', 'key_image', 'pubkey', 'block_height', 'spent')
    row = {'balance': {k: balance[k] for k in ('balance', 'unlocked_balance')},
           'outputs': sorted([{k: t[k] for k in fields} for t in transfers],
                             key=lambda t: (t['tx_hash'], t['pubkey']))}
    row['rpc_ids'] = {'refresh': len(RPC_ROWS) - 3, 'balance': len(RPC_ROWS) - 2,
                      'outputs': len(RPC_ROWS) - 1}
    return row


async def exact_pools(ids):
    pools = [await p2p.pool(n) for n in (0, 1)]
    return pools if all(pool == set(ids) for pool in pools) else None


async def confirmation(ids):
    rows, rpc_ids = [], []
    for n in (0, 1):
        rows.append((await p2p.endpoint(n, 'get_transactions',
                    {'txs_hashes': ids, 'decode_as_json': True})).get('txs', []))
        rpc_ids.append(len(RPC_ROWS) - 1)
    if all(len(r) == len(ids) and {tx['tx_hash'] for tx in r} == set(ids) and
           all(tx.get('in_pool') is False and tx.get('block_height', 0) > 0 for tx in r) for r in rows):
        return {'nodes': [[{'txid': tx['tx_hash'], 'height': tx['block_height']} for tx in r] for r in rows],
                'rpc_ids': rpc_ids}
    return None


async def main():
    PRIVATE.mkdir(mode=0o700)
    PUBLIC.mkdir(mode=0o755)
    started = time.monotonic()
    if sorted(p.name for p in Path('/sys/class/net').iterdir()) != ['lo'] or \
            Path('/proc/net/route').read_text().splitlines()[1:]:
        raise AssertionError('network containment absent')
    p2p.record('network_containment', interfaces=['lo'], routes=0)
    result = {'schema': 'vanguard-backlog/1', 'workload_seed': SEED, 'cohort_sizes': list(COHORTS),
              'funding_blocks': FUNDING, 'max_blocks': MAX_BLOCKS, 'time_limit_seconds': LIMIT_SECONDS,
              'cohorts': [], 'generated': [], 'process_exits': {}}
    bridge = p2p.Bridge()
    await bridge.start()
    try:
        p2p.daemon(0)
        p2p.daemon(1)
        await p2p.wait_for(p2p.equal_tip, 'genesis convergence')
        await p2p.wait_for(p2p.peer_connections, 'native handshake')
        result['genesis'] = await snapshot()
        for name, node in (('sender', 0), ('receiver', 1)):
            load.start_wallet(name, node)
            await p2p.wait_for(lambda n=name: load.wallet(n, 'get_version'), f'{name} RPC')
            await load.wallet(name, 'create_wallet', {'filename': name, 'password': '', 'language': 'English'})
        addresses = {name: (await load.wallet(name, 'get_address'))['address'] for name in ('sender', 'receiver')}
        result['wallet_seed_sha256'] = {}
        for name in addresses:
            seed = (await load.wallet(name, 'query_key', {'key_type': 'mnemonic'}))['key']
            result['wallet_seed_sha256'][name] = hashlib.sha256(seed.encode()).hexdigest()
            del seed

        async def generate(count, label):
            if sum(len(g['hashes']) for g in result['generated']) + count > MAX_BLOCKS:
                raise AssertionError('generated block budget')
            before = await snapshot()
            value, metric = await load.measured(label, p2p.rpc(0, 'generateblocks',
                {'wallet_address': addresses['sender'], 'amount_of_blocks': count}))
            rpc_id = len(RPC_ROWS) - 1
            if len(value['blocks']) != count:
                raise AssertionError('generated block response count')
            _, convergence = await load.measured(label + ' convergence',
                p2p.wait_for(p2p.equal_tip, label + ' convergence', 180))
            row = {'label': label, 'count': count, 'hashes': value['blocks'], 'rpc_id': rpc_id, 'before': before,
                   'after': await snapshot(), 'admission': metric, 'convergence': convergence}
            result['generated'].append(row)
            p2p.record('blocks_generated', **row)
            return row

        await generate(FUNDING, 'funding')
        result['funded_sender'] = await state('sender')
        initial_outputs = {row['key_image']: row for row in result['funded_sender']['outputs']}
        result['initial_receiver'] = await state('receiver')
        if result['initial_receiver']['outputs'] or result['initial_receiver']['balance']['balance']:
            raise AssertionError('receiver not fresh')
        rng = random.Random(SEED)
        all_ids, all_images = [], set()
        for cohort, count in enumerate(COHORTS, 1):
            began = time.monotonic()
            before = await snapshot()
            if before['pools'] != [[], []]:
                raise AssertionError('refill requires drained pools')
            rows = []
            first_arrival = None
            for number in range(count):
                amount = 10**12 + rng.randrange(1, 10) * 10**10
                made, construction = await load.measured('construction', load.wallet('sender', 'transfer',
                    {'destinations': [{'amount': amount, 'address': addresses['receiver']}],
                     'do_not_relay': True, 'get_tx_hex': True}))
                construction_rpc_id = len(RPC_ROWS) - 1
                txid, blob = made['tx_hash'], made['tx_blob']
                images = made['spent_key_images']['key_images']
                if txid in all_ids or not images or len(images) != len(set(images)) or \
                        set(images) & all_images or not set(images) <= set(initial_outputs):
                    raise AssertionError('duplicate pending input/transaction or unfunded input')
                admitted, admission = await load.measured('origin admission', load.submit(0, blob))
                admission_rpc_id = len(RPC_ROWS) - 1
                if admitted.get('status') != 'OK':
                    raise AssertionError('origin refused transaction: ' + str(admitted))
                arrived = time.monotonic()
                if first_arrival is None:
                    first_arrival = arrived
                _, convergence = await load.measured('peer pool convergence',
                    p2p.wait_for(lambda ids=[r['txid'] for r in rows] + [txid]: exact_pools(ids),
                                 'exact incremental peer pools', 120))
                # Preserve the accepted reservation route: wallet scans admitted
                # pool inputs before choosing the next independent mature input.
                _, reservation = await load.measured('sender refresh', load.wallet('sender', 'refresh'))
                decoded = json.loads((await p2p.endpoint(0, 'get_transactions',
                    {'txs_hashes': [txid], 'decode_as_json': True}))['txs'][0]['as_json'])
                decoded_rpc_id = len(RPC_ROWS) - 1
                if decoded['rct_signatures']['type'] != 7 or not all('carrot_v1' in out['target']
                        for out in decoded['vout']) or sorted(v['key']['k_image'] for v in decoded['vin']) != sorted(images):
                    raise AssertionError('FCMP++/CARROT/input binding')
                pending = await snapshot()
                expected = sorted([r['txid'] for r in rows] + [txid])
                if pending['tips'] != before['tips'] or pending['pools'] != [expected, expected]:
                    raise AssertionError('mining advanced or incomplete pending pools')
                row = {'txid': txid, 'amount': amount, 'fee': made['fee'],
                       'bytes': len(bytes.fromhex(blob)), 'key_images': images,
                       'selected_inputs': [initial_outputs[image] for image in images],
                       'construction': construction, 'origin_admission': admission,
                       'construction_rpc_id': construction_rpc_id, 'admission_rpc_id': admission_rpc_id,
                       'decoded_rpc_id': decoded_rpc_id,
                       'peer_pool_convergence': convergence, 'reservation_refresh': reservation,
                       'arrival_offset_seconds': arrived - began, 'pending': pending}
                rows.append(row)
                all_ids.append(txid)
                all_images.update(images)
                p2p.record('queue_arrival', cohort=cohort, number=number + 1, transaction=row)
            queued_at = time.monotonic()
            queued = await snapshot()
            if queued['tips'] != before['tips'] or queued['pools'] != [sorted(r['txid'] for r in rows)] * 2:
                raise AssertionError('eight simultaneous pending transactions absent')
            p2p.record('cohort_queued', cohort=cohort, snapshot=queued)
            generated = []
            for drain_block in range(1, 4):
                generated.append(await generate(1, f'cohort{cohort}-drain{drain_block}'))
                if await exact_pools([]):
                    break
            await p2p.wait_for(lambda: exact_pools([]), 'both pools drained', 120)
            drained_at = time.monotonic()
            confirmed = await p2p.wait_for(lambda: confirmation(list(all_ids)), 'exact confirmations', 120)
            block_rows = []
            block_rpc_ids = []
            for generated_row in generated:
                block_hash = generated_row['hashes'][0]
                contents, rpc_ids = [], []
                for n in (0, 1):
                    contents.append(json.loads((await p2p.rpc(n, 'get_block', {'hash': block_hash}))['json']))
                    rpc_ids.append(len(RPC_ROWS) - 1)
                block_rows.append(contents)
                block_rpc_ids.append(rpc_ids)
            mined_ids = [txid for blocks in block_rows for txid in blocks[0]['tx_hashes']]
            if sorted(mined_ids) != sorted(r['txid'] for r in rows) or \
                    any(blocks[0]['tx_hashes'] != blocks[1]['tx_hashes'] for blocks in block_rows):
                raise AssertionError('exactly-once block membership')
            receiver = await state('receiver')
            expected_amounts = {tx['txid']: tx['amount'] for c in result['cohorts'] for tx in c['transactions']}
            expected_amounts.update({tx['txid']: tx['amount'] for tx in rows})
            if len(receiver['outputs']) != len(all_ids) or \
                    {row['tx_hash']: row['amount'] for row in receiver['outputs']} != expected_amounts or \
                    receiver['balance']['balance'] != sum(expected_amounts.values()) or \
                    receiver['balance']['unlocked_balance'] != 0 or any(row['spent'] for row in receiver['outputs']):
                raise AssertionError('CARROT receiver reconciliation')
            duration = time.monotonic() - began
            if duration >= 180:
                raise AssertionError('cohort phase exceeded 180 seconds')
            row = {'cohort': cohort, 'count': count, 'transactions': rows, 'before': before,
                   'queued': queued, 'after': await snapshot(), 'confirmed': confirmed,
                   'block_contents': block_rows, 'block_rpc_ids': block_rpc_ids,
                   'generated_labels': [g['label'] for g in generated],
                   'receiver': receiver, 'duration_seconds': duration,
                   'queue_seconds': queued_at - began, 'drain_seconds': drained_at - queued_at,
                   'backlog_seconds': drained_at - first_arrival, 'confirmed_tps': count / duration}
            result['cohorts'].append(row)
            p2p.record('cohort_drained', **row)
        result['blocks'] = sum(len(g['hashes']) for g in result['generated'])
        result['transactions'] = len(all_ids)
        result['final_sender'] = await state('sender')
        result['final_receiver'] = await state('receiver')
        result['final'] = await snapshot()
        result['bridge'] = {'connections': bridge.connections, 'bytes': bridge.forwarded}
        result['final_sample'] = load.sample()
        # Writer-side live binding is evidence, not independent authentication.
        result['executing_binaries'] = {name: {'pid': proc.pid,
            'sha256': hashlib.sha256(Path(f'/proc/{proc.pid}/exe').read_bytes()).hexdigest()}
            for name, proc in p2p.PROCS.items()}
        result['wall_seconds'] = time.monotonic() - started
        if result['wall_seconds'] >= LIMIT_SECONDS:
            raise AssertionError('scenario budget exceeded')
        result['result'] = 'PASS_SCENARIO'
        p2p.record('scenario_complete', transactions=16, blocks=result['blocks'], snapshot=result['final'])
    finally:
        listeners = p2p.live_listeners()
        await bridge.close()
        for proc in p2p.PROCS.values():
            if proc.poll() is None:
                proc.send_signal(signal.SIGTERM)
        for name, proc in p2p.PROCS.items():
            try:
                proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            result['process_exits'][name] = proc.returncode
            p2p.record('process_exit', name=name, returncode=proc.returncode)
        for name in ('daemon0', 'daemon1'):
            for suffix in ('.log', '.stdout.log'):
                path = PRIVATE / (name + suffix)
                if path.exists():
                    shutil.copy2(path, PUBLIC / path.name)
        (PUBLIC / 'containment.json').write_text(json.dumps({'interfaces': ['lo'], 'routes': [],
            'listeners_before_shutdown': listeners, 'socket_mode': oct(bridge.socket.stat().st_mode & 0o777)
            if bridge.socket.exists() else '0o600'}, indent=2) + '\n')
        (PUBLIC / 'result.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
        if result['process_exits'] != {name: 0 for name in ('daemon0', 'daemon1', 'sender', 'receiver')}:
            raise AssertionError('unsuccessful native child exit')


if __name__ == '__main__':
    asyncio.run(asyncio.wait_for(main(), LIMIT_SECONDS))
