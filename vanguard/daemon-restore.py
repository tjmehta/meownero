#!/usr/bin/env python3
"""Restore a CARROT receiver and spend after a native two-daemon reorg."""
import asyncio
import importlib.util
import json
from pathlib import Path
import shutil
import signal
import subprocess
import time

spec = importlib.util.spec_from_file_location('daemon_p2p', '/harness/daemon-p2p.py')
p2p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p2p)

WORK, PRIVATE, PUBLIC, BIN = p2p.WORK, p2p.PRIVATE, p2p.PUBLIC, p2p.BIN
COIN = 10**12


async def wallet(port, method, params=None):
    result = await asyncio.to_thread(p2p.request, port, 'json_rpc',
        {'jsonrpc': '2.0', 'id': '0', 'method': method, 'params': params or {}})
    if 'error' in result:
        # RPC errors may contain private wallet details; leave them in the private logs.
        raise RuntimeError(f'wallet RPC failed: {method} at {port}, code {result["error"].get("code")}')
    return result['result']


def start_wallet(name, port, node):
    directory = PRIVATE / name
    directory.mkdir(mode=0o700)
    p2p.start(name, [str(BIN / 'monero-wallet-rpc'), '--rpc-bind-ip', '127.0.0.1',
        '--rpc-bind-port', str(port), '--disable-rpc-login', '--wallet-dir', str(directory),
        '--daemon-address', f'http://127.0.0.1:{19081 + node * 100}', '--trusted-daemon',
        '--allow-mismatched-daemon-version', '--max-concurrency', '1',
        '--log-file', str(PRIVATE / f'{name}.log')])


async def state(port):
    await wallet(port, 'refresh')
    balance = await wallet(port, 'get_balance')
    rows = (await wallet(port, 'incoming_transfers', {'transfer_type': 'all', 'account_index': 0}))['transfers']
    fields = ('tx_hash', 'amount', 'key_image', 'pubkey', 'block_height', 'global_index', 'spent')
    return {'balance': {key: balance[key] for key in ('balance', 'unlocked_balance')},
            'outputs': sorted([{key: row[key] for key in fields} for row in rows],
                              key=lambda row: (row['tx_hash'], row['pubkey']))}


async def transaction(node, txid):
    row = (await p2p.endpoint(node, 'get_transactions',
           {'txs_hashes': [txid], 'decode_as_json': True}))['txs'][0]
    decoded = json.loads(row['as_json'])
    if decoded['rct_signatures']['type'] != 7 or not decoded['vout'] or \
       not all('carrot_v1' in output['target'] for output in decoded['vout']):
        raise AssertionError('transaction lacks FCMP++ and CARROT outputs')
    return decoded, row


async def rejected_raw(node, blob, label):
    result = await asyncio.to_thread(p2p.request, 19081 + node * 100,
        'send_raw_transaction', {'tx_as_hex': blob, 'do_not_relay': False})
    if result.get('status') == 'OK':
        raise AssertionError(f'{label} accepted on daemon {node}')
    return {'node': node, 'status': result.get('status'),
            'double_spend': result.get('double_spend', False),
            'invalid_input': result.get('invalid_input', False)}


async def orphan_absent(txid):
    return all([txid not in await p2p.pool(node) for node in (0, 1)])


async def main():
    PRIVATE.mkdir(mode=0o700)
    PUBLIC.mkdir(mode=0o755)
    if sorted(path.name for path in Path('/sys/class/net').iterdir()) != ['lo'] or \
       Path('/proc/net/route').read_text().splitlines()[1:]:
        raise AssertionError('container network is not isolated')
    p2p.record('network_containment', interfaces=['lo'], routes=0)
    bridge = p2p.Bridge()
    await bridge.start()
    try:
        p2p.daemon(0)
        p2p.daemon(1)
        await p2p.wait_for(p2p.equal_tip, 'initial daemon convergence')
        peers = await p2p.wait_for(p2p.peer_connections, 'native P2P handshake')
        listeners = p2p.live_listeners()
        (PUBLIC / 'network-live.json').write_text(json.dumps({'interfaces': ['lo'],
            'routes': [], 'listeners': listeners,
            'socket_mode': oct(bridge.socket.stat().st_mode & 0o777)}, indent=2) + '\n')
        p2p.record('p2p_ready', tip=await p2p.equal_tip(), daemon_peer_counts=peers)

        ports = {'sender': 19090, 'original': 19190, 'orphan': 19092, 'restored': 19093}
        for name, node in (('sender', 0), ('original', 1), ('orphan', 0), ('restored', 0)):
            start_wallet(name, ports[name], node)
            await p2p.wait_for(lambda port=ports[name]: wallet(port, 'get_version'), f'{name} wallet RPC')
        for name in ('sender', 'original', 'orphan'):
            await wallet(ports[name], 'create_wallet',
                         {'filename': name, 'password': '', 'language': 'English'})
        addresses = {name: (await wallet(ports[name], 'get_address'))['address']
                     for name in ('sender', 'original', 'orphan')}
        seed = (await wallet(ports['original'], 'query_key', {'key_type': 'mnemonic'}))['key']
        if len(seed.split()) != 25:
            raise AssertionError('unexpected mnemonic format')

        funded = await p2p.rpc(0, 'generateblocks',
            {'wallet_address': addresses['sender'], 'amount_of_blocks': 70})
        if len(funded['blocks']) != 70:
            raise AssertionError('funding block count')
        await p2p.wait_for(p2p.equal_tip, 'funding synchronization', 180)
        await wallet(ports['sender'], 'refresh')
        sent = await wallet(ports['sender'], 'transfer',
            {'destinations': [{'amount': 5 * COIN, 'address': addresses['original']}]})
        stable_tx = sent['tx_hash']
        await p2p.wait_for(lambda: p2p.pool_contains(1, stable_tx), 'receiver funding relay')
        stable_decoded, _ = await transaction(0, stable_tx)
        await p2p.rpc(0, 'generateblocks',
            {'wallet_address': addresses['sender'], 'amount_of_blocks': 12})
        await p2p.wait_for(p2p.equal_tip, 'receiver funding confirmation', 180)
        original = await state(ports['original'])
        if original['balance']['balance'] != 5 * COIN or len(original['outputs']) != 1 or \
           original['outputs'][0]['tx_hash'] != stable_tx or \
           original['outputs'][0]['amount'] != 5 * COIN or \
           not original['outputs'][0]['key_image']:
            raise AssertionError('unexpected original CARROT receiver output')
        image = original['outputs'][0]['key_image']
        stable_height = original['outputs'][0]['block_height']
        restore_height = stable_height - 1
        p2p.record('carrot_received', txid=stable_tx, tx_version=stable_decoded['version'],
                   output_count=len(stable_decoded['vout']), output=original['outputs'][0],
                   balance=original['balance'], restore_height=restore_height)

        began = time.monotonic()
        restored = await wallet(ports['restored'], 'restore_deterministic_wallet',
            {'seed': seed, 'restore_height': restore_height, 'filename': 'restored',
             'password': '', 'autosave_current': True})
        restore_seconds = time.monotonic() - began
        del seed
        if restored['address'] != addresses['original']:
            raise AssertionError('restored address mismatch')
        first = await state(ports['restored'])
        if first != original:
            raise AssertionError('restored outputs, key images or balance differ')
        began = time.monotonic()
        await wallet(ports['restored'], 'rescan_blockchain', {'hard': True})
        rescanned = await state(ports['restored'])
        rescan_seconds = time.monotonic() - began
        if rescanned != original:
            raise AssertionError('hard rescan outputs, key images or balance differ')
        p2p.record('restored_and_rescanned', address_matches=True,
            restore_height=restore_height, output_height=stable_height,
            restore_seconds=restore_seconds, rescan_seconds=rescan_seconds,
            original=original, restored=rescanned)

        bridge.partition()
        common_tip = await p2p.tip(0)
        orphan_sent = await wallet(ports['sender'], 'transfer', {'destinations': [
            {'amount': 2 * COIN, 'address': addresses['original']},
            {'amount': 2 * COIN, 'address': addresses['orphan']}]})
        orphan_tx = orphan_sent['tx_hash']
        await transaction(0, orphan_tx)
        old_branch = await p2p.rpc(0, 'generateblocks',
            {'wallet_address': addresses['sender'], 'amount_of_blocks': 11})
        if await p2p.tip(1) != common_tip:
            raise AssertionError('partition leaked old branch')
        old_view = await state(ports['restored'])
        orphan_view = await state(ports['orphan'])
        if old_view['balance']['balance'] != 7 * COIN or \
           sorted(row['tx_hash'] for row in old_view['outputs']) != sorted([stable_tx, orphan_tx]) or \
           len(orphan_view['outputs']) != 1 or orphan_view['outputs'][0]['tx_hash'] != orphan_tx or \
           orphan_view['balance']['unlocked_balance'] < COIN:
            raise AssertionError('orphan branch outputs not visible and spendable')
        orphan_spend = await wallet(ports['orphan'], 'transfer',
            {'destinations': [{'amount': COIN, 'address': addresses['sender']}],
             'do_not_relay': True, 'get_tx_hex': True})
        orphan_blob = orphan_spend['tx_blob']
        orphan_spend_tx = orphan_spend['tx_hash']
        if not orphan_blob or orphan_spend['spent_key_images']['key_images'] != \
           [orphan_view['outputs'][0]['key_image']]:
            raise AssertionError('orphan spend did not use orphan output')
        if orphan_spend_tx in await p2p.pool(0):
            raise AssertionError('orphan negative-control spend was relayed')
        competing = await p2p.rpc(1, 'generateblocks',
            {'wallet_address': addresses['sender'], 'amount_of_blocks': 12})
        if await p2p.tip(0) == await p2p.tip(1):
            raise AssertionError('partition did not produce competing branches')
        p2p.record('partition_and_branch', common_tip=common_tip,
            old_tip=await p2p.tip(0), competing_tip=await p2p.tip(1),
            old_blocks=old_branch['blocks'], competing_blocks=competing['blocks'],
            orphan_txid=orphan_tx, orphan_spend_txid=orphan_spend_tx,
            old_wallet=old_view, orphan_output=orphan_view['outputs'][0])
        bridge.rejoin()
        await p2p.wait_for(p2p.equal_tip, 'native P2P reorg', 180)
        after_reorg = await state(ports['restored'])
        original_after = await state(ports['original'])
        pool_rows = {}
        for name in ('original', 'restored'):
            rows = (await wallet(ports[name], 'get_transfers', {'pool': True})).get('pool', [])
            pool_rows[name] = sorted([[row['txid'], row['amount']] for row in rows])
        p2p.record('reorg_wallet_observed', original_before=original,
                   restored_after=after_reorg, original_after=original_after,
                   pool_incoming=pool_rows)
        if after_reorg != original_after or after_reorg['outputs'] != original['outputs'] or \
           after_reorg['balance'] != {'balance': 7 * COIN, 'unlocked_balance': 5 * COIN} or \
           pool_rows != {'original': [[orphan_tx, 2 * COIN]],
                         'restored': [[orphan_tx, 2 * COIN]]}:
            raise AssertionError('orphan credit was not represented once in each wallet pool')
        for node in (0, 1):
            if orphan_tx in await p2p.pool(node):
                await p2p.rpc(node, 'flush_txpool', {'txids': [orphan_tx]})
        await p2p.wait_for(lambda: orphan_absent(orphan_tx), 'orphan pool flush')
        settled = await state(ports['restored'])
        original_settled = await state(ports['original'])
        if settled != original or original_settled != original:
            raise AssertionError('restored wallet did not settle after orphan pool removal')
        old_header = (await p2p.rpc(0, 'get_block_header_by_hash',
            {'hash': old_branch['blocks'][-1]}))['block_header']
        if not old_header['orphan_status']:
            raise AssertionError('old recipient branch not orphaned')
        p2p.record('restored_reorg_rollback', state=settled,
                   orphan=old_branch['blocks'][-1], tip=await p2p.equal_tip())

        before_negative = await p2p.snapshot(image)
        orphan_rejections = [await rejected_raw(node, orphan_blob, 'orphan spend') for node in (0, 1)]
        await p2p.unchanged(before_negative, image)
        p2p.record('orphan_spend_refused', txid=orphan_spend_tx,
                   key_image=orphan_view['outputs'][0]['key_image'], rejections=orphan_rejections,
                   state=before_negative)

        spent = await wallet(ports['restored'], 'transfer',
            {'destinations': [{'amount': 2 * COIN, 'address': addresses['sender']}],
             'get_tx_hex': True})
        spend_tx = spent['tx_hash']
        spend_blob = spent['tx_blob']
        if image not in spent['spent_key_images']['key_images']:
            raise AssertionError('restored spend did not use recovered key image')
        await p2p.wait_for(lambda: p2p.pool_contains(1, spend_tx), 'restored spend relay', 180)
        await p2p.wait_for(lambda: p2p.pool_contains(0, spend_tx), 'restored spend origin pool')
        spend_decoded, _ = await transaction(0, spend_tx)
        pooled = await p2p.snapshot(image)
        p2p.record('restored_spend_pool_observed', txid=spend_tx,
                   key_image=image, state=pooled)
        if pooled['key_images'] != [2, 2] or any(spend_tx not in pool for pool in pooled['pools']):
            raise AssertionError('restored FCMP++ spend not in both pools')
        p2p.record('restored_spend_pooled', txid=spend_tx, key_image=image,
                   tx_version=spend_decoded['version'], state=pooled)
        confirmed = await p2p.rpc(1, 'generateblocks',
            {'wallet_address': addresses['sender'], 'amount_of_blocks': 1})
        await p2p.wait_for(p2p.equal_tip, 'restored spend block relay', 180)
        await p2p.wait_for(lambda: p2p.key_images_confirmed(image), 'restored spend key image')
        final_original = await state(ports['original'])
        final_restored = await state(ports['restored'])
        stable_rows = [row for row in final_original['outputs'] if row['tx_hash'] == stable_tx]
        if final_original != final_restored or len(stable_rows) != 1 or \
           not stable_rows[0]['spent'] or stable_rows[0]['key_image'] != image:
            raise AssertionError('original wallet missed restored key-image spend')
        chain = await p2p.snapshot(image)
        if chain['key_images'] != [1, 1] or any(spend_tx in pool for pool in chain['pools']):
            raise AssertionError('restored spend not confirmed on both daemons')
        p2p.record('restored_spend_confirmed', txid=spend_tx,
            block=confirmed['blocks'][0], state=chain, original=final_original,
            restored=final_restored)
        before_replay = await p2p.snapshot(image)
        replay_rejections = [await rejected_raw(node, spend_blob, 'spent key-image replay')
                             for node in (0, 1)]
        await p2p.unchanged(before_replay, image)
        p2p.record('spent_key_image_replay_refused', txid=spend_tx,
                   rejections=replay_rejections, state=before_replay)
        (PUBLIC / 'result.json').write_text(json.dumps({'result': 'PASS',
            'stable_txid': stable_tx, 'stable_key_image': image, 'orphan_txid': orphan_tx,
            'orphan_spend_txid': orphan_spend_tx, 'restored_spend_txid': spend_tx,
            'restore_seconds': restore_seconds, 'rescan_seconds': rescan_seconds,
            'initial': original, 'rescanned': rescanned, 'old_branch': old_view,
            'after_reorg': settled, 'reorg_pool_credit': after_reorg,
            'pooled': pooled, 'confirmed': chain,
            'final_original': final_original, 'final_restored': final_restored,
            'orphan_rejections': orphan_rejections, 'replay_rejections': replay_rejections,
            'final_tip': await p2p.equal_tip(), 'bridge_connections': bridge.connections,
            'bridge_bytes': bridge.forwarded}, indent=2) + '\n')
    finally:
        listeners_before_shutdown = p2p.live_listeners()
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
            'listeners_before_shutdown': listeners_before_shutdown,
            'tcp': Path('/proc/net/tcp').read_text(),
            'tcp6': Path('/proc/net/tcp6').read_text()}, indent=2) + '\n')


if __name__ == '__main__':
    asyncio.run(main())
