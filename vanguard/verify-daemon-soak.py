#!/usr/bin/env python3
"""Reconcile new soak receipts. Historical live tips are never authenticated here."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import subprocess

ROOT = Path(__file__).resolve().parent.parent
IMAGE = 'sha256:345b4ccbee39f1231271234eddcc38e9e7c492114744ca21796b517913ee544b'
SOURCES = ('vanguard/source-lock.json', 'vanguard/daemon-p2p.py',
           'vanguard/prepare-soak-build-mac.py', 'vanguard/daemon-soak.py',
           'vanguard/run-daemon-soak.py', 'vanguard/verify-daemon-soak.py',
           'vanguard/test-daemon-soak-refusals.py', 'research/vanguard-soak-tjs1816-protocol-2026-10-08.md')
PORTS = {'senderA': 19090, 'senderB': 19190, 'recipientA': 19092, 'recipientB': 19192, 'restored': 19093}
FIELDS = ('tx_hash', 'amount', 'key_image', 'pubkey', 'block_height', 'spent')


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def comparable(row):
    return {key: row[key] for key in ('balance', 'outputs')}


def verify(out, src=None):
    manifest = {}
    for line in (out / 'MANIFEST.sha256').read_text().splitlines():
        digest, name = line.split('  ', 1)
        p = Path(name)
        require(not p.is_absolute() and '..' not in p.parts and 'private' not in p.parts and name not in manifest,
                'unsafe manifest')
        require(not (out / p).is_symlink(), 'symlink evidence')
        manifest[name] = digest
    require(manifest == {str(p.relative_to(out)): sha(p) for p in out.rglob('*')
                        if p.is_file() and 'private' not in p.relative_to(out).parts and p.name != 'MANIFEST.sha256'},
            'manifest mismatch')
    receipt = json.loads((out / 'receipt.json').read_text())
    require(receipt['schema'] == 'meownero-vanguard-soak/1' and receipt['result'] == 'PASS_WRITER_TRIALS', 'writer result')
    commit = receipt['candidate_commit']
    require(len(commit) == 40 and all(c in '0123456789abcdef' for c in commit), 'candidate commit')
    subprocess.run(['git', '-C', str(ROOT), 'merge-base', '--is-ancestor', commit, 'HEAD'], check=True)
    expected = {name: hashlib.sha256(subprocess.check_output(['git', '-C', str(ROOT), 'show', f'{commit}:{name}'])).hexdigest()
                for name in SOURCES}
    require(receipt['source_sha256'] == expected, 'exact source hashes')
    pin = json.loads(subprocess.check_output(['git', '-C', str(ROOT), 'show', f'{commit}:vanguard/source-lock.json']))
    require(receipt['source_lock'] == pin == json.loads((out / 'source-lock.json').read_text()), 'source pin')
    require(receipt['builder_image'] == IMAGE and receipt['architecture'] == 'linux/arm64', 'ARM image provenance')
    build = json.loads((out / 'preparation/receipt.json').read_text())
    require(sha(out / 'preparation/receipt.json') == receipt['build_receipt_sha256'], 'build receipt binding')
    require(build['result'] == 'PASS_BUILD' and build['image'] == IMAGE and build['rustc'] == pin['builder']['rustc'] and
            build['upstream_commit'] == pin['upstream']['commit'] and build['submodules'] == pin['upstream']['submodules'] and
            build['cargo_lock_sha256'] == pin['rust']['cargo_lock_sha256'] and build['binary'] == receipt['binary'], 'build lineage')
    require(len(build['downloads']) == 3 and all(len(d['sha256']) == 64 and d['bytes'] > 0 and
            d['url'].startswith('https://static.rust-lang.org/dist/') and
            '1.93.0-aarch64-unknown-linux-gnu' in d['url'] for d in build['downloads']), 'Rust downloads')
    require(all(c.get('exit') == 0 for c in build['commands']), 'preparation exits')
    build_command = next(c for c in build['commands'] if c['label'] == 'build')
    require(build_command['wall_seconds'] < 3600 and 'make -j1 daemon wallet_rpc_server' in build_command['argv'][-1], 'serial build budget')
    require(set(receipt['binary']) == {'monerod', 'monero-wallet-rpc'}, 'binary set')
    if src is not None:
        for name, value in receipt['binary'].items():
            p = src / 'monero-fcmp/build/vanguard/bin' / name
            require(value == {'sha256': sha(p), 'bytes': p.stat().st_size}, 'local executable bytes')
            with p.open('rb') as stream:
                header = stream.read(20)
            require(header[:4] == b'\x7fELF' and header[4:6] == b'\x02\x01' and
                    int.from_bytes(header[18:20], 'little') == 183, 'native ARM64 ELF executable')
    require(len(receipt['commands']) == len(receipt['trials']) == 2 and 0 < receipt['wall_seconds'] < 7000, 'two trials budget')
    workload_seeds, wallet_seeds, transactions, transcripts = set(), set(), set(), set()
    for number, command in enumerate(receipt['commands'], 1):
        trial = receipt['trials'][number - 1]
        stage = out / f'run{number}'
        require(trial['number'] == number and trial['exit'] == int((stage / 'docker.exit').read_text()) == 0 and
                trial['status'] == 'finished' and trial['container_absent'] is True and 1800 < trial['wall_seconds'] < 3380,
                'container outcome')
        for flag in ('--pull=never', '--network=none', '--cap-drop=ALL', '--security-opt=no-new-privileges',
                     '--cpus=2', '--memory=4g', '--memory-swap=4g', '--pids-limit=256'):
            require(command.count(flag) == 1, 'container cap: ' + flag)
        require(command[:5] == ['docker', '--context', 'colima', 'run', '--rm'] and
                command[command.index('--name') + 1] == trial['name'] and '--ulimit' in command and
                command[command.index('--ulimit') + 1] == 'core=0' and command[-4:-1] == [IMAGE, 'bash', '-euc'] and
                command[-1].endswith('timeout --signal=TERM 3340 python3 -B /harness/daemon-soak.py') and
                not any(c in ('--privileged', '--net', '-p', '--publish', '--publish-all', '--env-file') for c in command),
                'exact contained command')
        live = [json.loads(line) for line in (stage / 'container-live.jsonl').read_text().splitlines()]
        require(len(live) == 6 and live[1] == IMAGE and live[3]['Running'] is True, 'live container')
        config = live[4]
        require(config['NetworkMode'] == 'none' and config['Memory'] == config['MemorySwap'] == 4 * 1024**3 and
                config['NanoCpus'] == 2_000_000_000 and config['PidsLimit'] == 256 and
                config['CapDrop'] == ['ALL'] and 'no-new-privileges' in config['SecurityOpt'] and
                not config['Privileged'] and not config['PortBindings'], 'live containment caps')
        tmpfs = next(c for c in command if c.startswith('--tmpfs=/run/vanguard:')).split(':', 1)[1]
        require(config['Tmpfs'] == {'/run/vanguard': tmpfs} and
                all(flag in tmpfs.split(',') for flag in ('rw', 'noexec', 'nosuid', 'nodev', 'size=1m', 'mode=0700')),
                'private socket tmpfs')
        mounts = {m['Destination']: m for m in live[5]}
        require(set(mounts) in ({'/src', '/harness', '/out'}, {'/src', '/harness', '/out', '/run/vanguard'}) and not mounts['/src']['RW'] and
                not mounts['/harness']['RW'] and mounts['/out']['RW'], 'live mounts')
        available = int(next(line.split()[1] for line in (stage / 'vm-memory-before.txt').read_text().splitlines()
                             if line.startswith('MemAvailable:')))
        require(available >= 5 * 1024**2, 'VM memory precondition')
        final_memory = int((stage / 'final.memory').read_text())
        events = dict(s.split() for s in (stage / 'final.memory-events').read_text().splitlines())
        require(0 < final_memory <= 4 * 1024**3 and events['oom'] == events['oom_kill'] == '0', 'final container OOM/peak')
        cpu = dict(s.split() for s in (stage / 'final.cpu').read_text().splitlines())
        require(int(cpu['usage_usec']) > 0, 'final CPU')
        r = json.loads((stage / 'public/result.json').read_text())
        require(r['schema'] == 'vanguard-soak/1' and r['result'] == 'PASS_SCENARIO' and r['architecture'] == 'aarch64' and
                not r['cleanup_errors'] and not r.get('monitor_error'), 'scenario result')
        require(1800 <= r['measured_seconds'] <= 2400 and r['measured_seconds'] == r['measured_end_s'] - r['measured_start_s'] and
                0 < r['warmup_seconds'] <= 900, 'measured duration')
        require(r['workload_seed'] not in workload_seeds, 'fresh workload seed')
        workload_seeds.add(r['workload_seed'])
        require(set(r['wallet_seed_sha256']) == {'senderA', 'senderB', 'recipientA', 'recipientB'} and
                len(set(r['wallet_seed_sha256'].values())) == 4 and not wallet_seeds.intersection(r['wallet_seed_sha256'].values()),
                'fresh wallet seeds')
        wallet_seeds.update(r['wallet_seed_sha256'].values())
        raw = [json.loads(s) for s in (stage / 'public/rpc.jsonl').read_text().splitlines()]
        transcript = sha(stage / 'public/rpc.jsonl')
        require(transcript not in transcripts, 'fresh RPC transcript')
        transcripts.add(transcript)
        require([row['id'] for row in raw] == list(range(len(raw))) and all(
                math.isfinite(row['began_s']) and math.isfinite(row['ended_s']) and
                0 <= row['began_s'] <= row['ended_s'] < row['began_s'] + 300 for row in raw) and
                all(a['ended_s'] <= b['began_s'] for a, b in zip(raw, raw[1:])), 'RPC chronological linkage')
        require(not any(row['request'].get('method') == 'start_mining' or row['path'] == 'start_mining' for row in raw), 'mining paused')

        def rpc(i, port, path, method=None):
            require(type(i) is int and 0 <= i < len(raw), 'RPC reference')
            row = raw[i]
            require(row['port'] == port and row['path'] == path and
                    (method is None or row['request']['method'] == method), 'RPC method/port')
            return row

        def snap(s, equal=False, empty=False):
            refs = s['rpc_ids']
            require(len(refs) == 4 and refs == sorted(set(refs)), 'snapshot chronology')
            for node in (0, 1):
                header = rpc(refs[node], 19081 + 100 * node, 'json_rpc', 'get_last_block_header')['response']['result']['block_header']
                require(s['tips'][node] == [header['height'], header['hash'], header['wide_cumulative_difficulty']], 'tip RPC binding')
                pool = rpc(refs[2 + node], 19081 + 100 * node, 'get_transaction_pool')['response'].get('transactions', [])
                require(s['pools'][node] == sorted(tx['id_hash'] for tx in pool), 'pool RPC binding')
            require(not equal or s['tips'][0] == s['tips'][1], 'peer convergence')
            require(not empty or s['pools'] == [[], []], 'empty queues')
            return refs

        def wallet(w, name):
            refs = w['rpc_ids']
            require(len(refs) == 3 and refs == sorted(set(refs)), 'wallet chronology')
            rpc(refs[0], PORTS[name], 'json_rpc', 'refresh')
            balance = rpc(refs[1], PORTS[name], 'json_rpc', 'get_balance')['response']['result']
            transfers = rpc(refs[2], PORTS[name], 'json_rpc', 'incoming_transfers')['response']['result'].get('transfers', [])
            expected = sorted([{k: o[k] for k in FIELDS} for o in transfers], key=lambda o: (o['tx_hash'], o['pubkey']))
            require(w['balance'] == {k: balance[k] for k in ('balance', 'unlocked_balance')} and w['outputs'] == expected, 'wallet RPC binding')
            require(len({o['pubkey'] for o in expected}) == len(expected) and
                    len({o['key_image'] for o in expected}) == len(expected) and
                    w['balance']['balance'] == sum(o['amount'] for o in expected if not o['spent']) and
                    0 <= w['balance']['unlocked_balance'] <= w['balance']['balance'], 'wallet credit/balance uniqueness')
            return refs

        def bindings(payment, rows):
            require(len(rows) == 2, 'both node transaction bindings')
            headers = []
            for node, bound in enumerate(rows):
                tx_call = rpc(bound['tx_rpc_id'], 19081 + 100 * node, 'get_transactions')
                require(tx_call['request']['txs_hashes'] == [payment['txid']], 'exact transaction query')
                txs = tx_call['response']['txs']
                require(len(txs) == 1, 'one transaction result')
                tx = txs[0]
                blob = tx.get('as_hex') or tx.get('pruned_as_hex', '') + tx.get('prunable_as_hex', '')
                decoded = json.loads(tx['as_json'])
                require(tx['tx_hash'] == payment['txid'] and tx['in_pool'] is False and tx['block_height'] == bound['height'] > 0 and
                        blob == payment['blob'], 'native tx identity/bytes/height')
                require(decoded['rct_signatures']['type'] == 7 and decoded['vout'] and
                        all('carrot_v1' in o['target'] for o in decoded['vout']) and
                        sorted(v['key']['k_image'] for v in decoded['vin']) == sorted(payment['key_images']), 'FCMP/CARROT/input binding')
                block_call = rpc(bound['block_rpc_id'], 19081 + 100 * node, 'json_rpc', 'get_block')
                block = block_call['response']['result']
                header, body = block['block_header'], json.loads(block['json'])
                require(block_call['request']['params'] == {'height': bound['height']} and header['height'] == bound['height'] and
                        header['hash'] == bound['block_hash'] and header['prev_hash'] == bound['previous_hash'] and
                        header['orphan_status'] is False and body['tx_hashes'].count(payment['txid']) == 1, 'exact main-chain block membership')
                require(bound['tx_rpc_id'] < bound['block_rpc_id'], 'confirmation chronology')
                headers.append((header['height'], header['hash'], header['prev_hash'], body['tx_hashes']))
            require(headers[0] == headers[1], 'peer block agreement')

        def output_binding(output, payment):
            for node, bound in enumerate(payment['confirmed']):
                tx = rpc(bound['tx_rpc_id'], 19081 + 100 * node, 'get_transactions')['response']['txs'][0]
                decoded = json.loads(tx['as_json'])
                keys = [v['target']['carrot_v1']['key'] for v in decoded['vout']]
                require(keys.count(output['pubkey']) == 1 and output['tx_hash'] == payment['txid'] and
                        output['amount'] == payment['amount'] and output['block_height'] == bound['height'],
                        'recipient CARROT output key/amount/height binding')

        snap(r['genesis'], True, True)
        require(r['genesis']['tips'][0][0] == 0, 'fresh chain')
        for name, address in r['addresses'].items():
            call = rpc(r['address_rpc_ids'][name], PORTS[name], 'json_rpc', 'get_address')
            require(call['response']['result']['address'] == address and address, 'wallet address binding')
            seed = rpc(r['seed_rpc_ids'][name], PORTS[name], 'json_rpc', 'query_key')
            require(seed['response'] == {'redacted_seed_sha256': r['wallet_seed_sha256'][name]}, 'seed digest binding')
        require(len(set(r['addresses'].values())) == 4, 'distinct wallet addresses')
        for n in ('senderA', 'senderB'):
            wallet(r['funded'][n], n)
        for n in ('recipientA', 'recipientB'):
            wallet(r['fresh_recipients'][n], n)
            require(not r['fresh_recipients'][n]['outputs'] and not r['fresh_recipients'][n]['balance']['balance'], 'fresh recipient')
        start_refs = snap(r['measured_start'], True, True)
        require(raw[start_refs[-1]]['ended_s'] <= r['measured_start_s'], 'warmup excluded')
        generated = {g['label']: g for g in r['generated']}
        require(len(generated) == len(r['generated']) and 195 <= sum(g['count'] for g in generated.values()) <= 210, 'block budget')
        require([g['rpc_id'] for g in r['generated']] == [row['id'] for row in raw if row['request'].get('method') == 'generateblocks'], 'all mining accounted')
        for g in generated.values():
            snap(g['before']); snap(g['after'])
            call = rpc(g['rpc_id'], 19081 + 100 * g['node'], 'json_rpc', 'generateblocks')
            require(call['request']['params']['amount_of_blocks'] == g['count'] == len(g['hashes']) and
                    call['response']['result']['blocks'] == g['hashes'] and g['before']['rpc_ids'][-1] < g['rpc_id'] < g['after']['rpc_ids'][0],
                    'generated block RPC binding')
        require(generated['funding-senderA']['count'] == generated['funding-senderB']['count'] == 90, 'funding depth')
        require(r['transactions'] == 32 and len(r['cohorts']) == 4, '32 payments')
        trial_ids, images = set(), set()
        payments = {}
        for number, c in enumerate(r['cohorts'], 1):
            sender, recipient = ('senderA', 'recipientB') if number in (1, 3) else ('senderB', 'recipientA')
            origin = 0 if sender == 'senderA' else 1
            require(c['number'] == number and c['sender'] == sender and c['recipient'] == recipient and
                    c['partition'] == (number == 3) and len(c['transactions']) == 8 and
                    0 < c['ended_s'] - c['began_s'] <= 300 and c['confirmed_tps'] == 8 / (c['ended_s'] - c['began_s']), 'cohort identity/count/timing')
            require(c['began_s'] >= r['measured_start_s'] + (0, 360, 720, 1440)[number - 1], 'phase earliest time')
            snap(c['before'], True, True)
            wallet(c['sender_before'], sender)
            inputs = {o['key_image']: o for o in c['sender_before']['outputs'] if not o['spent']}
            rng = random.Random(r['workload_seed'] + number)
            queued = []
            for t in c['transactions']:
                require(t['txid'] not in trial_ids and t['txid'] not in transactions and t['key_images'] and
                        len(t['key_images']) == len(set(t['key_images'])) and not images.intersection(t['key_images']), 'unique payment/input')
                trial_ids.add(t['txid']); images.update(t['key_images']); queued.append(t['txid']); payments[t['txid']] = t
                amount = 10**12 + rng.randrange(1, 10) * 10**10
                require(t['amount'] == amount and t['sender'] == sender and t['recipient'] == recipient and
                        t['destination'] == r['addresses'][recipient] and t['selected_inputs'] == [inputs[i] for i in t['key_images']], 'payment destination/amount/input')
                made = rpc(t['construction_rpc_id'], PORTS[sender], 'json_rpc', 'transfer')
                require(made['request']['params'] == {'destinations': [{'amount': amount, 'address': t['destination']}],
                        'do_not_relay': True, 'get_tx_hex': True}, 'construction destinations')
                value = made['response']['result']
                require(value['tx_hash'] == t['txid'] and value['tx_blob'] == t['blob'] and value['fee'] == t['fee'] and
                        value['spent_key_images']['key_images'] == t['key_images'], 'wallet construction binding')
                admitted = rpc(t['admission_rpc_id'], 19081 + 100 * origin, 'send_raw_transaction')
                require(admitted['request'] == {'tx_as_hex': t['blob'], 'do_not_relay': False} and admitted['response']['status'] == 'OK', 'native admission')
                reserve = rpc(t['reservation_rpc_id'], PORTS[sender], 'json_rpc', 'refresh')
                snap(t['pending'])
                expected_pool = [sorted(queued)] * 2
                if c['partition']:
                    expected_pool = [sorted(queued), []]
                require(t['pending']['pools'] == expected_pool and t['pending']['tips'] == c['before']['tips'], 'paused incremental queued pools')
                require(t['construction_rpc_id'] < t['admission_rpc_id'] < t['reservation_rpc_id'] < t['pending']['rpc_ids'][0] and
                        admitted['ended_s'] <= t['origin_arrival_s'] <= t['peer_arrival_s'] <= t['confirmed_s'], 'payment chronology')
                bindings(t, t['confirmed'])
            snap(c['isolated_queue']); snap(c['full_queue'], True)
            require(c['full_queue']['tips'] == c['before']['tips'] and c['full_queue']['pools'] == [sorted(queued)] * 2 and
                    c['full_queue']['rpc_ids'][-1] < generated[c['drain_labels'][0]]['rpc_id'], 'full queue before drain')
            if c['partition']:
                require(c['isolated_queue']['pools'] == [sorted(queued), []], 'disconnected exact queue')
                retry = rpc(c['reconnect_relay_rpc_id'], 19081, 'json_rpc', 'relay_tx')
                require(retry['request']['params']['txids'] == queued and retry['response']['result']['status'] == 'OK' and
                        c['isolated_queue']['rpc_ids'][-1] < retry['id'] < c['full_queue']['rpc_ids'][0], 'native reconnect retry')
            else:
                require(c['reconnect_relay_rpc_id'] is None, 'unexpected retry')
            require(1 <= len(c['drain_labels']) <= 3, 'bounded drain blocks')
            snap(c['after'], True, True)
            wallet(c['recipient_state'], recipient)
            wanted = {txid: t['amount'] for txid, t in payments.items() if t['recipient'] == recipient}
            outputs = c['recipient_state']['outputs']
            require(len(outputs) == len(wanted) and {o['tx_hash']: o['amount'] for o in outputs} == wanted, 'exact recipient credits')
            for output in outputs:
                output_binding(output, payments[output['tx_hash']])
        transactions.update(trial_ids)
        for name, restart in (('senderB', r['wallet_restart']), ('daemon0', r['daemon_restart'])):
            generations = [g for g in r['generations'] if g['name'] == name]
            require(len(generations) == 2 and generations[0]['command'] == generations[1]['command'] and
                    generations[0]['exited_s'] <= generations[1]['monotonic_s'] <= restart['completed_s'], 'persistent restart generation')
        wr = r['wallet_restart']
        wallet(wr['before'], 'senderB'); wallet(wr['after'], 'senderB')
        require(comparable(wr['before']) == comparable(wr['after']), 'persistent wallet state')
        rpc(wr['open_rpc_id'], PORTS['senderB'], 'json_rpc', 'open_wallet')
        require(rpc(wr['address_rpc_id'], PORTS['senderB'], 'json_rpc', 'get_address')['response']['result']['address'] == r['addresses']['senderB'], 'restart address')
        dr = r['daemon_restart']
        snap(dr['before'], True, True); snap(dr['after'], True, True)
        require(dr['before']['tips'] == dr['after']['tips'], 'persistent daemon chain')
        reorg = r['reorg']
        snap(reorg['before'], True, True); snap(reorg['diverged']); snap(reorg['recovered'], True, True)
        require(reorg['completed_s'] >= r['measured_start_s'] + 1080 and reorg['losing'] == generated['reorg-losing']['hashes'] and
                reorg['winning'] == generated['reorg-winning']['hashes'] and len(reorg['losing']) == 1 and len(reorg['winning']) == 2 and
                reorg['diverged']['tips'][0][1] == reorg['losing'][-1] and reorg['diverged']['tips'][1][1] == reorg['winning'][-1] and
                reorg['recovered']['tips'][0][1] == reorg['winning'][-1], 'controlled longer-chain reorg')
        for node, i in enumerate(reorg['orphan_rpc_ids']):
            call = rpc(i, 19081 + 100 * node, 'json_rpc', 'get_block')
            require(call['request']['params']['hash'] == reorg['losing'][0] and call['response']['result']['block_header']['orphan_status'] is True, 'losing branch orphan')
        for name in ('recipientA', 'recipientB'):
            wallet(reorg['wallets_before'][name], name); wallet(reorg['wallets_after'][name], name)
            require(comparable(reorg['wallets_before'][name]) == comparable(reorg['wallets_after'][name]), 'reorg wallet credit preservation')
        require(set(reorg['rebindings']) == {t['txid'] for c in r['cohorts'][:3] for t in c['transactions']}, 'reorg payment coverage')
        for txid, rows in reorg['rebindings'].items():
            bindings(payments[txid], rows)
        restore = r['restore']
        for field, name in (('original', 'recipientA'), ('restored', 'restored'), ('final_original', 'recipientA'), ('final_restored', 'restored')):
            wallet(restore[field], name)
        require(comparable(restore['original']) == comparable(restore['restored']) and
                comparable(restore['final_original']) == comparable(restore['final_restored']), 'restored wallet state')
        restore_call = rpc(restore['restore_rpc_id'], PORTS['restored'], 'json_rpc', 'restore_deterministic_wallet')
        require('seed' not in restore_call['request']['params'] and
                restore_call['request']['params']['redacted_seed_sha256'] == r['wallet_seed_sha256']['recipientA'] and
                restore_call['response']['result']['address'] == r['addresses']['recipientA'], 'restore seed/address binding')
        rpc(restore['rescan_rpc_id'], PORTS['restored'], 'json_rpc', 'rescan_blockchain')
        spend = r['restored_spend']
        made = rpc(spend['construction_rpc_id'], PORTS['restored'], 'json_rpc', 'sweep_single')
        require(made['response']['result']['tx_hash'] == spend['txid'] and made['response']['result']['tx_blob'] == spend['blob'] and
                made['response']['result']['spent_key_images']['key_images'] == spend['key_images'] and
                made['request']['params']['address'] == spend['destination'] == r['addresses']['senderA'] and
                spend['source_txid'] in payments and spend['source_amount'] == payments[spend['source_txid']]['amount'] and
                spend['amount'] == made['response']['result']['amount'] and spend['fee'] == made['response']['result']['fee'] and
                spend['amount'] + spend['fee'] == spend['source_amount'], 'restored successful spend')
        source_outputs = [o for o in restore['original']['outputs'] if o['tx_hash'] == spend['source_txid']]
        require(len(source_outputs) == 1 and not source_outputs[0]['spent'] and
                source_outputs[0]['amount'] == spend['source_amount'] and
                spend['key_images'] == [source_outputs[0]['key_image']] and
                made['request']['params'] == {'key_image': source_outputs[0]['key_image'], 'do_not_relay': True,
                    'get_tx_hex': True, 'address': spend['destination']}, 'restored source input binding')
        admitted = rpc(spend['admission_rpc_id'], 19081, 'send_raw_transaction')
        require(admitted['request'] == {'tx_as_hex': spend['blob'], 'do_not_relay': False} and
                admitted['response']['status'] == 'OK' and made['id'] < admitted['id'], 'restored spend admission')
        snap(spend['queued'], True)
        require(spend['queued']['pools'] == [[spend['txid']], [spend['txid']]] and
                admitted['id'] < spend['queued']['rpc_ids'][0] and
                spend['queued']['rpc_ids'][-1] < generated['restored-spend']['rpc_id'] and
                generated['restored-spend']['count'] == 1, 'restored spend queue before drain')
        bindings(spend, spend['confirmed'])
        require(spend['txid'] not in transactions, 'fresh restored spend')
        transactions.add(spend['txid'])
        require(set(r['controls']) == {'malformed', 'invalid_signature', 'conflicting_spend'}, 'negative control coverage')
        for label, control in r['controls'].items():
            snap(control['before'], True, True); snap(control['after'], True, True)
            require(control['before']['tips'] == control['after']['tips'], 'rejection state integrity')
            for node in (0, 1):
                rejected = rpc(control['rpc_ids'][node], 19081 + 100 * node, 'send_raw_transaction')
                require(rejected['request']['tx_as_hex'] == control['blob'] and rejected['response']['status'] != 'OK' and
                        (label != 'conflicting_spend' or rejected['response'].get('double_spend')), 'native invalid/conflict rejection')
                a = rpc(control['key_before_ids'][node], 19081 + 100 * node, 'is_key_image_spent')
                b = rpc(control['key_after_ids'][node], 19081 + 100 * node, 'is_key_image_spent')
                require(a['request']['key_images'] == b['request']['key_images'] == spend['key_images'] and a['response'] == b['response'], 'rejection key-image state')
                require(a['id'] < rejected['id'] < b['id'], 'rejection chronology')
                require(rejected['id'] < r['cohorts'][3]['transactions'][0]['admission_rpc_id'], 'healthy payment after bad input')
        mutated = bytearray.fromhex(spend['blob']); mutated[-1] ^= 1
        require(r['controls']['malformed']['blob'] == '00' and r['controls']['invalid_signature']['blob'] == mutated.hex(), 'distinct negative inputs')
        alternate_call = rpc(r['alternate']['construction_rpc_id'], PORTS['recipientA'], 'json_rpc', 'sweep_single')
        alternate = alternate_call['response']['result']
        require(alternate['tx_hash'] == r['alternate']['txid'] != spend['txid'] and
                alternate['tx_blob'] == r['controls']['conflicting_spend']['blob'] and
                alternate['spent_key_images']['key_images'] == spend['key_images'] and
                alternate_call['request']['params'] == {'key_image': source_outputs[0]['key_image'], 'do_not_relay': True,
                    'get_tx_hex': True, 'address': r['addresses']['recipientB']}, 'actual conflicting spend')
        require(set(r['final_bindings']) == trial_ids | {spend['txid']}, 'final complete transaction binding')
        for txid, rows in r['final_bindings'].items():
            bindings(spend if txid == spend['txid'] else payments[txid], rows)
            require(rows[0]['tx_rpc_id'] > r['cohorts'][3]['transactions'][-1]['admission_rpc_id'], 'final binding freshness')
        for name, state_row in r['final_wallets'].items():
            wallet(state_row, name)
        restored_credit = [o for o in r['final_wallets']['senderA']['outputs'] if o['tx_hash'] == spend['txid']]
        require(len(restored_credit) == 1 and not restored_credit[0]['spent'], 'restored spend exactly-once destination credit')
        output_binding(restored_credit[0], spend)
        require(comparable(r['final_wallets']['recipientA']) == comparable(r['final_wallets']['restored']), 'final restored history')
        for name in ('recipientA', 'recipientB'):
            wanted = {t['txid']: t['amount'] for t in payments.values() if t['recipient'] == name}
            outputs = r['final_wallets'][name]['outputs']
            require(len(outputs) == 16 and {o['tx_hash']: o['amount'] for o in outputs} == wanted and
                    {o['tx_hash'] for o in outputs if o['spent']} == ({spend['source_txid']} if name == 'recipientA' else set()),
                    'final exact credits and restored input spend')
            for output in outputs:
                output_binding(output, payments[output['tx_hash']])
        for name in ('senderA', 'senderB'):
            work = [t for t in payments.values() if t['sender'] == name]
            outputs = r['final_wallets'][name]['outputs']
            require({o['key_image'] for o in outputs if o['spent']} == {i for t in work for i in t['key_images']}, 'exact sender input spends')
            require(sum(t['amount'] + t['fee'] for t in work) == sum(o['amount'] for o in outputs if o['spent']) -
                    sum(o['amount'] for o in outputs if o['tx_hash'] in {t['txid'] for t in work}), 'principal/fee/change accounting')
        snap(r['final'], True, True)
        require(len(r['final_peers']) == 2 and all(n > 0 for n in r['final_peers']), 'final native peers')
        for node, i in enumerate(r['final_peer_rpc_ids']):
            peers = rpc(i, 19081 + 100 * node, 'json_rpc', 'get_connections')['response']['result']['connections']
            require(len(peers) == r['final_peers'][node] and peers and raw[i]['ended_s'] >= r['measured_start_s'] + 1800,
                    'final peer RPC binding')
        require(r['interfaces'] == ['lo'] and not r['routes'] and r['listeners_before_shutdown'], 'native network containment')
        require(len(r['generations']) == 9, 'all native generations')
        identities = set()
        for g in r['generations']:
            identity = (g['pid'], g['start_ticks'])
            require(identity not in identities and g['exit'] == 0 and g['exited_s'] > g['monotonic_s'], 'child exits/start identities')
            identities.add(identity)
            binary = receipt['binary']['monerod' if g['name'].startswith('daemon') else 'monero-wallet-rpc']
            require(g['sha256'] == binary['sha256'] and g['bytes'] == binary['bytes'] and
                    g['executable_path'] == g['command'][0] and g['command'][0].startswith('/src/build/vanguard/bin/'), 'live executable generation')
        for name, live_row in r['final_live'].items():
            g = next(g for g in reversed(r['generations']) if g['name'] == name)
            require(all(live_row[k] == g[k] for k in ('pid', 'start_ticks', 'sha256', 'bytes', 'command')) and
                    r['measured_end_s'] - 30 <= live_row['monotonic_s'] <= r['measured_end_s'], 'fresh final live identity')
        samples = [json.loads(s) for s in (stage / 'public/samples.jsonl').read_text().splitlines()]
        require(len(samples) >= 180 and all(a['monotonic_s'] < b['monotonic_s'] for a, b in zip(samples, samples[1:])), 'resource trend samples')
        measured = [s for s in samples if r['measured_start_s'] <= s['monotonic_s'] <= r['measured_end_s']]
        require(len(measured) >= 175 and measured[-1]['monotonic_s'] - measured[0]['monotonic_s'] >= 1790 and
                max(b['monotonic_s'] - a['monotonic_s'] for a, b in zip(measured, measured[1:])) <= 20, 'measured resource coverage')
        for s in samples:
            require(0 < s['memory_peak_bytes'] <= final_memory and 0 <= s['memory_current_bytes'] <= 4 * 1024**3 and
                    s['memory_events']['oom'] == s['memory_events']['oom_kill'] == 0 and s['cpu']['usage_usec'] >= 0, 'resource/OOM samples')
            require(all((p['pid'], p['start_ticks']) in identities and p['cpu_ticks'] >= 0 and p['rss_bytes'] >= 0
                        for p in s['processes'].values()), 'sample child binding')
        require(r['start_sample'] in samples and r['end_sample'] in samples and r['shutdown_sample'] == samples[-1] and
                not r['shutdown_sample']['processes'] and r['shutdown_sample']['memory_peak_bytes'] <= final_memory and
                r['shutdown_sample']['cpu']['usage_usec'] <= int(cpu['usage_usec']), 'final shutdown resources')
        event_rows = [json.loads(s) for s in (stage / 'public/events.jsonl').read_text().splitlines()]
        heartbeats = [e for e in event_rows if e['event'] == 'heartbeat']
        require(len(heartbeats) >= 40 and heartbeats[-1]['offset_s'] >= 1770, 'live heartbeat coverage')
        require(sum(e['event'] == 'bridge_partitioned' for e in event_rows) >= 3 and
                sum(e['event'] == 'bridge_rejoined' for e in event_rows) == 2, 'partition/rejoin history')
        for h in heartbeats:
            snap(h['snapshot'], True)
    return {'result': 'PASS_SOAK_RECEIPT_RECONCILIATION', 'trials': 2, 'workload_payments': 64,
            'limits': 'UNVERIFIED_LIVE_TIPS; writer observations, accelerated local ARM64 regtest only'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('out', type=Path)
    parser.add_argument('--src', type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.out.resolve(), args.src.resolve() if args.src else None), sort_keys=True))


if __name__ == '__main__':
    main()
