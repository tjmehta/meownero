#!/usr/bin/env python3
"""Four finite native payments across build-mac and an authenticated Railway peer."""
import asyncio
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import socket
import time
import urllib.request

spec = importlib.util.spec_from_file_location('p2p', Path(__file__).with_name('daemon-p2p.py'))
p2p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p2p)
PUBLIC, PRIVATE = p2p.PUBLIC, p2p.PRIVATE
URL = os.environ.get('MEOWNERO_REMOTE_CONTROL_URL', '')
TOKEN = os.environ.get('MEOWNERO_CONTROL_TOKEN', '')
ROWS = []
RESULT = {'schema': 'vanguard-cross-host/1', 'result': 'INCOMPLETE', 'payments': [],
          'resource_samples': [], 'generated_blocks': 0}
SECRET_FIELDS = {'seed', 'key', 'spend_key', 'view_key', 'tx_key', 'tx_keys', 'tx_metadata', 'password'}


def public_value(value):
    if isinstance(value, dict):
        return {key: '[redacted]' if key in SECRET_FIELDS and item else public_value(item)
                for key, item in value.items()}
    if isinstance(value, list):
        return [public_value(item) for item in value]
    return value


async def call(target, path, body):
    began = time.monotonic()
    if target == 'railway':
        def remote():
            req = urllib.request.Request(URL + '/rpc', json.dumps({'path': path, 'body': body}).encode(),
                {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + TOKEN})
            with urllib.request.urlopen(req, timeout=40) as response:
                return json.load(response)
        value = await asyncio.to_thread(remote)
    else:
        ports = {'build-mac': 19081, 'sender': 19090, 'recipient': 19190}
        value = await asyncio.to_thread(p2p.request, ports[target], path, body)
    row = {'id': len(ROWS), 'target': target, 'path': path, 'request': public_value(body),
           'response': public_value(value), 'began_s': began, 'ended_s': time.monotonic()}
    ROWS.append(row)
    with (PUBLIC / 'rpc.jsonl').open('a') as stream:
        stream.write(json.dumps(row, sort_keys=True) + '\n')
    return value, row['id']


async def rpc(target, method, params=None):
    value, ref = await call(target, 'json_rpc', {'jsonrpc': '2.0', 'id': '0',
                            'method': method, 'params': params or {}})
    assert 'error' not in value, f'{target} {method} failed'
    return value['result'], ref


async def control(path):
    def request():
        req = urllib.request.Request(URL + '/' + path, b'{}',
            {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + TOKEN})
        with urllib.request.urlopen(req, timeout=45) as reply:
            return json.load(reply)
    value = await asyncio.to_thread(request)
    with (PUBLIC / 'control.jsonl').open('a') as stream:
        stream.write(json.dumps({'path': path, 'response': value, 'observed_s': time.monotonic()}) + '\n')
    return value


async def snapshot():
    tips, pools, peers = [], [], []
    refs = []
    for node in ('build-mac', 'railway'):
        value, ref = await rpc(node, 'get_last_block_header')
        h = value['block_header']
        tips.append([h['height'], h['hash'], h['wide_cumulative_difficulty']])
        refs.append(ref)
        value, ref = await call(node, 'get_transaction_pool', {})
        assert value.get('status') == 'OK'
        pools.append(sorted(tx['id_hash'] for tx in value.get('transactions', [])))
        refs.append(ref)
        value, ref = await rpc(node, 'get_connections')
        peers.append(value.get('connections', []))
        assert len(peers[-1]) <= 1, 'unexpected additional native peer'
        refs.append(ref)
    return {'tips': tips, 'pools': pools, 'peers': peers, 'rpc_ids': refs}


async def converge(txids=()):
    state = await snapshot()
    return state if (state['tips'][0] == state['tips'][1] and
                     state['pools'] == [sorted(txids)] * 2 and all(state['peers'])) else None


async def wait(check, label, seconds=180):
    return await p2p.wait_for(check, label, seconds)


async def wallet_state(name):
    await rpc(name, 'refresh')
    balance, balance_ref = await rpc(name, 'get_balance')
    incoming, incoming_ref = await rpc(name, 'incoming_transfers', {'transfer_type': 'all'})
    fields = ('tx_hash', 'amount', 'key_image', 'pubkey', 'block_height', 'spent')
    outputs = [{key: row[key] for key in fields} for row in incoming.get('transfers', [])]
    assert len({row['pubkey'] for row in outputs}) == len(outputs)
    return {'balance': {key: balance[key] for key in ('balance', 'unlocked_balance')},
            'outputs': outputs, 'rpc_ids': [balance_ref, incoming_ref]}


async def generate(address, count):
    assert RESULT['generated_blocks'] + count <= 90
    value, ref = await rpc('build-mac', 'generateblocks', {'wallet_address': address, 'amount_of_blocks': count})
    assert len(value['blocks']) == count
    RESULT['generated_blocks'] += count
    return {'blocks': value['blocks'], 'rpc_id': ref}


async def binding(payment):
    bindings = []
    for node in ('build-mac', 'railway'):
        value, ref = await call(node, 'get_transactions', {'txs_hashes': [payment['txid']], 'decode_as_json': True})
        assert len(value.get('txs', [])) == 1
        tx = value['txs'][0]
        assert tx['tx_hash'] == payment['txid'] and tx['in_pool'] is False and tx['block_height'] > 0
        decoded = json.loads(tx['as_json'])
        assert decoded['rct_signatures']['type'] == 7
        assert int(decoded['rct_signatures']['txnFee']) == payment['fee']
        assert all('carrot_v1' in row['target'] for row in decoded['vout'])
        assert sorted(row['key']['k_image'] for row in decoded['vin']) == sorted(payment['key_images'])
        raw = tx.get('as_hex') or tx.get('pruned_as_hex', '') + tx.get('prunable_as_hex', '')
        assert raw == payment['blob']
        block, block_ref = await rpc(node, 'get_block', {'height': tx['block_height']})
        header = block['block_header']
        assert header['orphan_status'] is False and header['height'] == tx['block_height']
        assert json.loads(block['json'])['tx_hashes'].count(payment['txid']) == 1
        bindings.append({'height': tx['block_height'], 'hash': header['hash'], 'previous': header['prev_hash'],
                         'tx_rpc_id': ref, 'block_rpc_id': block_ref})
    assert all(bindings[0][key] == bindings[1][key] for key in ('height', 'hash', 'previous'))
    return bindings


async def sample():
    remote = await control('state')
    local = {}
    for name, proc in p2p.PROCS.items():
        if proc.poll() is None:
            path = Path(f'/proc/{proc.pid}')
            local[name] = {'rss_bytes': next(int(row.split()[1]) * 1024 for row in
                (path / 'status').read_text().splitlines() if row.startswith('VmRSS:')),
                'exe_sha256': hashlib.sha256((path / 'exe').read_bytes()).hexdigest(),
                'start_ticks': (path / 'stat').read_text().rsplit(')', 1)[1].split()[19],
                'command': (path / 'cmdline').read_bytes().decode().split('\0')[:-1]}
            expected = os.environ['MEOWNERO_LOCAL_DAEMON_SHA256' if name == 'daemon0'
                                  else 'MEOWNERO_LOCAL_WALLET_SHA256']
            assert local[name]['exe_sha256'] == expected, 'local executable differs from frozen inputs'
    assert remote['process']['exe_sha256'] == os.environ['MEOWNERO_REMOTE_DAEMON_SHA256']
    remote_limit = int(os.environ['MEOWNERO_REMOTE_MEMORY_LIMIT_BYTES'])
    assert int(remote['memory.peak']) <= remote_limit, 'remote exceeded frozen provider limit'
    for events in (remote['memory.events'], Path('/sys/fs/cgroup/memory.events').read_text()):
        values = dict(line.split() for line in events.splitlines())
        assert int(values['oom']) == int(values['oom_kill']) == 0, 'OOM event'
    row = {'observed_s': time.monotonic(), 'railway': remote, 'local_rss': local,
           'local_memory_peak': Path('/sys/fs/cgroup/memory.peak').read_text().strip(),
           'local_memory_events': Path('/sys/fs/cgroup/memory.events').read_text().strip()}
    RESULT['resource_samples'].append(row)
    return row


async def sampling():
    while True:
        await sample()
        await asyncio.sleep(10)


async def main():
    assert URL.startswith('https://') and len(TOKEN) >= 32, 'secured runtime control access required'
    PRIVATE.mkdir(mode=0o700)
    PUBLIC.mkdir()
    host = os.environ['MEOWNERO_PEER_HOST']
    port = int(os.environ['MEOWNERO_PEER_PORT'])
    ip = socket.gethostbyname(host)
    RESULT['transport'] = {'kind': 'native Railway TCP proxy', 'host': host, 'port': port, 'resolved_ipv4': ip}
    sampler = None
    measured_start = None
    try:
        args = [str(p2p.BIN / 'monerod'), '--data-dir', str(PRIVATE / 'daemon0'), '--regtest',
            '--keep-fakechain', '--fixed-difficulty', '1', '--non-interactive', '--no-igd',
            '--allow-local-ip', '--disable-dns-checkpoints', '--check-updates', 'disabled',
            '--hide-my-port', '--max-concurrency', '1', '--no-zmq', '--rpc-ssl', 'disabled',
            '--p2p-bind-ip', '127.0.0.1', '--p2p-bind-port', '19080', '--rpc-bind-ip', '127.0.0.1',
            '--rpc-bind-port', '19081', '--add-exclusive-node', f'{ip}:{port}',
            '--log-file', str(PRIVATE / 'daemon.log')]
        p2p.start('daemon0', args)
        RESULT['genesis'] = await wait(converge, 'native cross-host genesis handshake')
        RESULT['runtime_network'] = {node: (await rpc(node, 'get_info'))[0]
                                     for node in ('build-mac', 'railway')}
        for name, wallet_port in (('sender', 19090), ('recipient', 19190)):
            directory = PRIVATE / name
            directory.mkdir(mode=0o700)
            p2p.start(name, [str(p2p.BIN / 'monero-wallet-rpc'), '--rpc-bind-ip', '127.0.0.1',
                '--rpc-bind-port', str(wallet_port), '--disable-rpc-login', '--wallet-dir', str(directory),
                '--daemon-address', 'http://127.0.0.1:19081', '--trusted-daemon',
                '--allow-mismatched-daemon-version', '--max-concurrency', '1',
                '--log-file', str(PRIVATE / (name + '.log'))])
            await wait(lambda n=name: rpc(n, 'get_version'), name + ' RPC')
            await rpc(name, 'create_wallet', {'filename': name, 'password': '', 'language': 'English'})
        addresses = {name: (await rpc(name, 'get_address'))[0]['address'] for name in ('sender', 'recipient')}
        RESULT['addresses'] = addresses
        RESULT['funding'] = await generate(addresses['sender'], 70)
        RESULT['funded'] = await wait(converge, 'funded chain sync')
        assert (await wallet_state('sender'))['balance']['unlocked_balance'] >= 4 * 10**12
        measured_start = time.monotonic()
        RESULT['measured_start_s'] = measured_start
        sampler = asyncio.create_task(sampling())
        used_images = set()
        for number in range(1, 5):
            assert time.monotonic() - measured_start < 900
            if number == 4:
                before = await wait(converge, 'pre-restart tips')
                # Freeze this owned peer so remote reopening cannot be mistaken for a fresh sync.
                p2p.PROCS['daemon0'].send_signal(signal.SIGSTOP)
                try:
                    restart = await control('restart')
                    reopened = restart['reopened_tip']['result']['block_header']
                    assert [reopened['height'], reopened['hash'], reopened['wide_cumulative_difficulty']] == before['tips'][1]
                finally:
                    p2p.PROCS['daemon0'].send_signal(signal.SIGCONT)
                after = await wait(converge, 'persistent remote restart and native reconnect')
                assert before['tips'] == after['tips']
                assert restart['before']['process']['start_ticks'] != restart['after']['process']['start_ticks']
                RESULT['recovery'] = {'before': before, 'control': restart, 'after': after}
            amount = 10**12 + number * 10**10
            began = time.monotonic()
            inputs = {row['key_image']: row for row in (await wallet_state('sender'))['outputs'] if not row['spent']}
            made, ref = await rpc('sender', 'transfer', {'destinations': [{'address': addresses['recipient'], 'amount': amount}],
                'do_not_relay': True, 'get_tx_hex': True})
            images = made['spent_key_images']['key_images']
            assert images and not used_images.intersection(images) and len(images) == len(set(images))
            assert set(images) <= set(inputs)
            used_images.update(images)
            payment = {'txid': made['tx_hash'], 'blob': made['tx_blob'], 'fee': made['fee'],
                       'amount': amount, 'destination': addresses['recipient'], 'key_images': images,
                       'construction_rpc_id': ref, 'selected_inputs': [inputs[image] for image in images]}
            admitted, ref = await call('build-mac', 'send_raw_transaction', {'tx_as_hex': made['tx_blob'], 'do_not_relay': False})
            assert admitted.get('status') == 'OK'
            payment['admission_rpc_id'] = ref
            payment['queued'] = await wait(lambda tx=made['tx_hash']: converge([tx]), 'native remote pool arrival')
            await rpc('sender', 'refresh')
            payment['generation'] = await generate(addresses['sender'], 1)
            await wait(converge, 'payment block sync')
            payment['binding'] = await binding(payment)
            received = await wallet_state('recipient')
            outputs = [row for row in received['outputs'] if row['tx_hash'] == made['tx_hash']]
            assert len(outputs) == 1 and outputs[0]['amount'] == amount
            assert outputs[0]['block_height'] == payment['binding'][0]['height']
            payment['recipient'] = received
            payment['wall_seconds'] = time.monotonic() - began
            RESULT['payments'].append(payment)
            await sample()
        RESULT['final_bindings'] = [await binding(payment) for payment in RESULT['payments']]
        RESULT['final'] = await wait(converge, 'final empty pools and tip')
        recipient = await wallet_state('recipient')
        assert len(recipient['outputs']) == 4
        assert recipient['balance']['balance'] == sum(payment['amount'] for payment in RESULT['payments'])
        RESULT['final_recipient'] = recipient
        RESULT['measured_seconds'] = time.monotonic() - measured_start
        assert RESULT['measured_seconds'] <= 900
        await sample()
        RESULT['result'] = 'PASS_WRITER_NATIVE_WITNESS'
    except Exception as err:
        RESULT['result'] = 'FAIL'
        RESULT['failure'] = type(err).__name__ + ': ' + str(err)
        raise
    finally:
        if sampler:
            sampler.cancel()
            try:
                await sampler
            except asyncio.CancelledError:
                pass
            except Exception as err:
                RESULT['result'] = 'FAIL'
                RESULT['resource_failure'] = type(err).__name__ + ': ' + str(err)
        RESULT['local_exits'] = {}
        for name, proc in p2p.PROCS.items():
            if proc.poll() is None:
                proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(20)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(5)
            RESULT['local_exits'][name] = proc.returncode
        try:
            RESULT['remote_shutdown'] = await control('stop')
            assert all(row.get('exit') == 0 for row in RESULT['remote_shutdown']['generations'])
            events = dict(line.split() for line in RESULT['remote_shutdown']['memory.events'].splitlines())
            assert int(events['oom']) == int(events['oom_kill']) == 0
        except OSError as err:
            RESULT['remote_shutdown_error'] = type(err).__name__
            RESULT['result'] = 'FAIL'
        except (AssertionError, KeyError) as err:
            RESULT['remote_shutdown_error'] = type(err).__name__
            RESULT['result'] = 'FAIL'
        if any(code != 0 for code in RESULT['local_exits'].values()):
            RESULT['result'] = 'FAIL'
        # Provider deletion/proxy cleanup must be recorded by the deployment owner separately.
        RESULT['provider_cleanup'] = 'UNVERIFIED'
        (PUBLIC / 'result.json').write_text(json.dumps(RESULT, indent=2) + '\n')


if __name__ == '__main__':
    asyncio.run(asyncio.wait_for(main(), 1500))
