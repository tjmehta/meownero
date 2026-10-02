#!/usr/bin/env python3
"""Finite, valueless two-daemon FCMP++/CARROT load witness. Container only."""
import asyncio
import hashlib
import importlib.util
import json
import random
from pathlib import Path
import shutil
import signal
import subprocess
import time

spec = importlib.util.spec_from_file_location('daemon_p2p', '/harness/daemon-p2p.py')
p2p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p2p)

PUBLIC, PRIVATE = p2p.PUBLIC, p2p.PRIVATE
PORTS = {'sender': 19090, 'receiver': 19190, 'restored': 19092}
SEED = 1171
LEVELS = (1, 2)
COIN = 10**12
MAX_TRANSACTIONS = sum(LEVELS) + 1
MAX_BLOCKS = 90
LIMIT_SECONDS = 1000


async def wallet(name, method, params=None):
    result = await asyncio.to_thread(p2p.request, PORTS[name], 'json_rpc',
        {'jsonrpc': '2.0', 'id': '0', 'method': method, 'params': params or {}})
    if 'error' in result:
        raise RuntimeError(f'{name} wallet {method}: code {result["error"].get("code")}')
    return result['result']


def start_wallet(name, node):
    directory = PRIVATE / name
    directory.mkdir(mode=0o700)
    p2p.start(name, [str(p2p.BIN / 'monero-wallet-rpc'), '--rpc-bind-ip', '127.0.0.1',
        '--rpc-bind-port', str(PORTS[name]), '--disable-rpc-login', '--wallet-dir', str(directory),
        '--daemon-address', f'http://127.0.0.1:{19081 + node * 100}', '--trusted-daemon',
        '--allow-mismatched-daemon-version', '--max-concurrency', '1',
        '--log-file', str(PRIVATE / f'{name}.log')])


def sample():
    cpu = dict(line.split() for line in Path('/sys/fs/cgroup/cpu.stat').read_text().splitlines())
    rss = {}
    for name, proc in p2p.PROCS.items():
        status = Path(f'/proc/{proc.pid}/status')
        if status.exists():
            row = next((line for line in status.read_text().splitlines()
                        if line.startswith('VmRSS:')), 'VmRSS: 0 kB')
            rss[name] = int(row.split()[1]) * 1024
    return {'cpu_usec': int(cpu['usage_usec']),
            'memory_current_bytes': int(Path('/sys/fs/cgroup/memory.current').read_text()),
            'memory_peak_bytes': int(Path('/sys/fs/cgroup/memory.peak').read_text()),
            'rss_bytes': rss}


async def measured(label, awaitable):
    before, began = sample(), time.monotonic()
    value = await awaitable
    after = sample()
    metric = {'wall_seconds': time.monotonic() - began,
              'cpu_seconds': (after['cpu_usec'] - before['cpu_usec']) / 1e6,
              'memory_current_before_bytes': before['memory_current_bytes'],
              'memory_current_after_bytes': after['memory_current_bytes'],
              'memory_peak_bytes': after['memory_peak_bytes'],
              'rss_before_bytes': before['rss_bytes'], 'rss_after_bytes': after['rss_bytes']}
    if not 0 < metric['wall_seconds'] < 180:
        raise AssertionError(f'{label} exceeded 180 seconds')
    return value, metric


async def state(name):
    await wallet(name, 'refresh')
    balance = await wallet(name, 'get_balance')
    rows = (await wallet(name, 'incoming_transfers',
                         {'transfer_type': 'all', 'account_index': 0}))['transfers']
    fields = ('tx_hash', 'amount', 'key_image', 'pubkey', 'block_height', 'spent')
    return {'balance': {key: balance[key] for key in ('balance', 'unlocked_balance')},
            'outputs': sorted([{key: row[key] for key in fields} for row in rows],
                              key=lambda row: (row['tx_hash'], row['pubkey']))}


async def submit(node, blob):
    return await asyncio.to_thread(p2p.request, 19081 + node * 100,
        'send_raw_transaction', {'tx_as_hex': blob, 'do_not_relay': False})


async def confirmed(txids):
    for node in (0, 1):
        rows = (await p2p.endpoint(node, 'get_transactions',
                                  {'txs_hashes': txids, 'decode_as_json': True}))['txs']
        if len(rows) != len(txids) or not all(row.get('in_pool') is False and
                                               row.get('block_height', 0) > 0 for row in rows):
            return False
    return True


async def main():
    PRIVATE.mkdir(mode=0o700)
    PUBLIC.mkdir(mode=0o755)
    if sorted(path.name for path in Path('/sys/class/net').iterdir()) != ['lo'] or \
            Path('/proc/net/route').read_text().splitlines()[1:]:
        raise AssertionError('network containment absent')
    p2p.record('network_containment', interfaces=['lo'], routes=0)
    bridge = p2p.Bridge()
    await bridge.start()
    result = {'schema': 'vanguard-load/1', 'workload_seed': SEED, 'levels': list(LEVELS),
              'max_transactions': MAX_TRANSACTIONS, 'max_blocks': MAX_BLOCKS,
              'time_limit_seconds': LIMIT_SECONDS, 'workloads': [], 'controls': {}}
    blocks = 0
    try:
        p2p.daemon(0)
        p2p.daemon(1)
        await p2p.wait_for(p2p.equal_tip, 'genesis convergence')
        await p2p.wait_for(p2p.peer_connections, 'native P2P handshake')
        for name, node in (('sender', 0), ('receiver', 1), ('restored', 0)):
            start_wallet(name, node)
            await p2p.wait_for(lambda n=name: wallet(n, 'get_version'), f'{name} RPC')
        for name in ('sender', 'receiver'):
            await wallet(name, 'create_wallet',
                         {'filename': name, 'password': '', 'language': 'English'})
        addresses = {name: (await wallet(name, 'get_address'))['address']
                     for name in ('sender', 'receiver')}
        seed = (await wallet('receiver', 'query_key', {'key_type': 'mnemonic'}))['key']
        if len(seed.split()) != 25:
            raise AssertionError('receiver mnemonic format')
        result['wallet_seed_sha256'] = hashlib.sha256(seed.encode()).hexdigest()
        funding, fund_metric = await measured('funding', p2p.rpc(0, 'generateblocks',
            {'wallet_address': addresses['sender'], 'amount_of_blocks': 70}))
        blocks += 70
        if len(funding['blocks']) != 70:
            raise AssertionError('funding block count')
        await p2p.wait_for(p2p.equal_tip, 'funding convergence', 180)
        await wallet('sender', 'refresh')
        result['funding'] = fund_metric

        before = sample()
        began = time.monotonic()
        await asyncio.sleep(3)
        after = sample()
        result['baseline'] = {'wall_seconds': time.monotonic() - began,
            'cpu_seconds': (after['cpu_usec'] - before['cpu_usec']) / 1e6,
            'rss_bytes': after['rss_bytes'], 'memory_peak_bytes': after['memory_peak_bytes'],
            'tips': [await p2p.tip(n) for n in (0, 1)]}
        if result['baseline']['tips'][0] != result['baseline']['tips'][1]:
            raise AssertionError('idle tip divergence')
        p2p.record('idle_baseline', metric=result['baseline'])

        rng = random.Random(SEED)
        all_txids = []
        for level, count in enumerate(LEVELS, 1):
            began = time.monotonic()
            tx_rows = []
            for _ in range(count):
                amount = COIN + rng.randrange(1, 10) * 10**10
                made, construction = await measured('construction', wallet('sender', 'transfer',
                    {'destinations': [{'amount': amount, 'address': addresses['receiver']}],
                     'do_not_relay': True, 'get_tx_hex': True}))
                txid, blob = made['tx_hash'], made['tx_blob']
                if not blob or not made['spent_key_images']['key_images']:
                    raise AssertionError('construction omitted raw FCMP++ transaction')
                admitted, admission = await measured('pool admission', submit(0, blob))
                if admitted.get('status') != 'OK':
                    raise AssertionError(f'origin pool refused level {level}')
                _, convergence = await measured('inter-daemon pool convergence',
                    p2p.wait_for(lambda t=txid: p2p.pool_contains(1, t), 'peer pool', 120))
                decoded = json.loads((await p2p.endpoint(0, 'get_transactions',
                    {'txs_hashes': [txid], 'decode_as_json': True}))['txs'][0]['as_json'])
                if decoded['rct_signatures']['type'] != 7 or not all(
                        'carrot_v1' in out['target'] for out in decoded['vout']):
                    raise AssertionError('wrong FCMP++/CARROT transaction type')
                tx_rows.append({'txid': txid, 'amount': amount, 'bytes': len(bytes.fromhex(blob)),
                    'construction': construction, 'origin_admission': admission,
                    'peer_pool_convergence': convergence})
                all_txids.append(txid)
            _, block_metric = await measured('block admission', p2p.rpc(0, 'generateblocks',
                {'wallet_address': addresses['sender'], 'amount_of_blocks': 1}))
            blocks += 1
            _, tip_metric = await measured('block convergence',
                p2p.wait_for(p2p.equal_tip, 'level block convergence', 120))
            await p2p.wait_for(lambda ids=list(all_txids): confirmed(ids), 'confirmed workload', 120)
            receiver = await state('receiver')
            if len(receiver['outputs']) != len(all_txids) or \
                    {row['tx_hash'] for row in receiver['outputs']} != set(all_txids):
                raise AssertionError('receiver missed workload output')
            duration = time.monotonic() - began
            row = {'level': level, 'count': count, 'transactions': tx_rows,
                   'block_admission': block_metric, 'block_convergence': tip_metric,
                   'duration_seconds': duration, 'confirmed_tps': count / duration,
                   'tips': [await p2p.tip(n) for n in (0, 1)], 'receiver': receiver}
            result['workloads'].append(row)
            p2p.record('workload_level', **row)

        _, unlock_metric = await measured('output unlock', p2p.rpc(0, 'generateblocks',
            {'wallet_address': addresses['sender'], 'amount_of_blocks': 10}))
        blocks += 10
        await p2p.wait_for(p2p.equal_tip, 'unlock convergence', 120)
        original = await state('receiver')
        first = original['outputs'][0]
        restore_height = min(row['block_height'] for row in original['outputs']) - 1
        restored, restore_metric = await measured('wallet restore', wallet('restored',
            'restore_deterministic_wallet', {'seed': seed, 'restore_height': restore_height,
            'filename': 'restored', 'password': '', 'autosave_current': True}))
        del seed
        if restored['address'] != addresses['receiver'] or await state('restored') != original:
            raise AssertionError('restored wallet differs from confirmed receiver')
        _, rescan_metric = await measured('wallet rescan', wallet('restored',
            'rescan_blockchain', {'hard': True}))
        if await state('restored') != original:
            raise AssertionError('rescanned wallet differs')
        result['restore'] = {'restore_height': restore_height,
            'output_count': len(original['outputs']), 'restore': restore_metric,
            'rescan': rescan_metric, 'original': original, 'unlock': unlock_metric}
        p2p.record('wallet_restored', restore_height=restore_height,
                   output_count=len(original['outputs']), metric=restore_metric)

        sweep = {'address': addresses['sender'], 'key_image': first['key_image'],
                 'do_not_relay': True, 'get_tx_hex': True}
        alternate, _ = await measured('alternative construction', wallet('receiver',
            'sweep_single', {**sweep, 'address': addresses['receiver']}))
        valid, spend_construction = await measured('restored spend construction',
            wallet('restored', 'sweep_single', sweep))
        if valid['tx_hash'] == alternate['tx_hash'] or not valid['tx_blob'] or \
                valid['spent_key_images']['key_images'] != [first['key_image']] or \
                alternate['spent_key_images']['key_images'] != [first['key_image']]:
            raise AssertionError('distinct same-key-image candidates absent')
        corrupt = bytearray.fromhex(valid['tx_blob'])
        corrupt[-1] ^= 1
        before_invalid = await p2p.snapshot(first['key_image'])
        invalid = [await submit(node, corrupt.hex()) for node in (0, 1)]
        if any(row.get('status') == 'OK' for row in invalid):
            raise AssertionError('invalid proof mutation accepted')
        await p2p.unchanged(before_invalid, first['key_image'])
        result['controls']['invalid_proof'] = {'mutation': 'last transaction byte xor 01',
            'source_txid': valid['tx_hash'], 'mutated_sha256': p2p.digest(corrupt),
            'responses': invalid, 'state_unchanged': True}
        p2p.record('invalid_proof_refused', **result['controls']['invalid_proof'])

        admitted, admission = await measured('restored pool admission', submit(0, valid['tx_blob']))
        if admitted.get('status') != 'OK':
            raise AssertionError('restored spend admission failed')
        _, pool_convergence = await measured('restored pool convergence',
            p2p.wait_for(lambda: p2p.pool_contains(1, valid['tx_hash']), 'restored peer pool', 120))
        _, spend_block = await measured('restored block admission', p2p.rpc(0, 'generateblocks',
            {'wallet_address': addresses['sender'], 'amount_of_blocks': 1}))
        blocks += 1
        _, spend_tip = await measured('restored block convergence',
            p2p.wait_for(p2p.equal_tip, 'restored block convergence', 120))
        await p2p.wait_for(lambda: confirmed([valid['tx_hash']]), 'restored spend confirmation', 120)
        final_original, final_restored = await state('receiver'), await state('restored')
        if final_original != final_restored or not any(
                row['key_image'] == first['key_image'] and row['spent']
                for row in final_original['outputs']):
            raise AssertionError('confirmed restored spend not wallet visible')
        result['restored_spend'] = {'txid': valid['tx_hash'], 'key_image': first['key_image'],
            'construction': spend_construction, 'origin_admission': admission,
            'peer_pool_convergence': pool_convergence, 'block_admission': spend_block,
            'block_convergence': spend_tip, 'tips': [await p2p.tip(n) for n in (0, 1)],
            'wallet': final_original}
        p2p.record('restored_spend_confirmed', txid=valid['tx_hash'],
                   tips=result['restored_spend']['tips'])
        before_duplicate = await p2p.snapshot(first['key_image'])
        duplicate = [await submit(node, alternate['tx_blob']) for node in (0, 1)]
        if any(row.get('status') == 'OK' or not row.get('double_spend') for row in duplicate):
            raise AssertionError('duplicate key image not explicitly refused')
        await p2p.unchanged(before_duplicate, first['key_image'])
        result['controls']['duplicate_key_image'] = {'alternate_txid': alternate['tx_hash'],
            'confirmed_txid': valid['tx_hash'], 'key_image': first['key_image'],
            'responses': duplicate, 'state_unchanged': True}
        p2p.record('duplicate_key_image_refused', **result['controls']['duplicate_key_image'])

        await p2p.rpc(0, 'generateblocks',
            {'wallet_address': addresses['sender'], 'amount_of_blocks': 1})
        blocks += 1
        await p2p.wait_for(p2p.equal_tip, 'pre-reorg common tip', 120)
        common = await p2p.equal_tip()
        bridge.partition()
        branch0 = await p2p.rpc(0, 'generateblocks',
            {'wallet_address': addresses['sender'], 'amount_of_blocks': 1})
        branch1 = await p2p.rpc(1, 'generateblocks',
            {'wallet_address': addresses['sender'], 'amount_of_blocks': 2})
        blocks += 3
        if await p2p.tip(0) == await p2p.tip(1):
            raise AssertionError('partition did not diverge')
        bridge.rejoin()
        _, recovery = await measured('reorg recovery',
            p2p.wait_for(p2p.equal_tip, 'reorg recovery', 180))
        recovered = await p2p.equal_tip()
        if recovered[1] != branch1['blocks'][-1] or \
                await state('receiver') != await state('restored'):
            raise AssertionError('reorg recovery or wallet convergence failed')
        if not await confirmed(all_txids + [valid['tx_hash']]):
            raise AssertionError('confirmed workload lost after reorg')
        result['reorg'] = {'common_tip': common, 'branch0': branch0['blocks'],
            'branch1': branch1['blocks'], 'recovered_tips': [await p2p.tip(n) for n in (0, 1)],
            'recovery': recovery, 'wallet': await state('restored')}
        result['blocks'] = blocks
        result['bridge'] = {'connections': bridge.connections, 'bytes': bridge.forwarded}
        result['final_sample'] = sample()
        if blocks > MAX_BLOCKS or len(all_txids) + 1 > MAX_TRANSACTIONS or \
                result['final_sample']['memory_peak_bytes'] > 4 * 1024**3:
            raise AssertionError('bounded workload limit exceeded')
        result['result'] = 'PASS_SCENARIO'
        (PUBLIC / 'result.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
        p2p.record('scenario_complete', result='PASS_SCENARIO', blocks=blocks,
                   transactions=len(all_txids) + 1, tips=result['reorg']['recovered_tips'])
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
            p2p.record('process_exit', name=name, returncode=proc.returncode)
        for name in ('daemon0', 'daemon1'):
            for suffix in ('.log', '.stdout.log'):
                path = PRIVATE / (name + suffix)
                if path.exists():
                    shutil.copy2(path, PUBLIC / path.name)
        (PUBLIC / 'containment.json').write_text(json.dumps({
            'interfaces': sorted(path.name for path in Path('/sys/class/net').iterdir()),
            'routes': Path('/proc/net/route').read_text().splitlines()[1:],
            'listeners_before_shutdown': listeners}, indent=2) + '\n')


if __name__ == '__main__':
    asyncio.run(asyncio.wait_for(main(), LIMIT_SECONDS))
