#!/usr/bin/env python3
"""Reconcile finite backlog receipts and local bytes; live tips remain unverified."""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import random
import subprocess

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('load_verifier', ROOT / 'vanguard/verify-daemon-load.py')
load = importlib.util.module_from_spec(spec)
spec.loader.exec_module(load)
require, sha = load.require, load.sha
SOURCES = ('vanguard/source-lock.json', 'vanguard/daemon-p2p.py', 'vanguard/daemon-load.py',
           'vanguard/run-daemon-p2p.py', 'vanguard/verify-daemon-load.py',
           'vanguard/daemon-backlog.py', 'vanguard/run-daemon-backlog.py',
           'vanguard/verify-daemon-backlog.py', 'vanguard/test-daemon-backlog-refusals.py')
NAMES = ('daemon0', 'daemon1', 'sender', 'receiver')


def phase(m):
    require(math.isfinite(m['wall_seconds']) and 0 < m['wall_seconds'] < 180,
            'phase time budget')
    require(math.isfinite(m['cpu_seconds']) and m['cpu_seconds'] >= 0 and
            0 < m['memory_peak_bytes'] <= 4 * 1024**3 and
            all(0 <= v <= 4 * 1024**3 for v in m['rss_after_bytes'].values()), 'phase resources')


def verify(out, src):
    receipt = json.loads((out / 'receipt.json').read_text())
    require(receipt['schema'] == 'meownero-vanguard-daemon-backlog/1', 'receipt schema')
    commit = receipt['candidate_commit']
    require(len(commit) == 40 and all(c in '0123456789abcdef' for c in commit), 'candidate commit')
    subprocess.run(['git', '-C', str(ROOT), 'merge-base', '--is-ancestor', commit, 'HEAD'], check=True)
    expected = {name: hashlib.sha256(subprocess.check_output(
        ['git', '-C', str(ROOT), 'show', f'{commit}:{name}'])).hexdigest() for name in SOURCES}
    require(receipt['source_sha256'] == expected, 'exact committed source hashes')
    manifest = {}
    for line in (out / 'MANIFEST.sha256').read_text().splitlines():
        digest, name = line.split('  ', 1)
        p = Path(name)
        require(not p.is_absolute() and '..' not in p.parts and 'private' not in p.parts and
                name not in manifest, 'unsafe manifest')
        manifest[name] = digest
    require(manifest == {str(p.relative_to(out)): sha(p) for p in out.rglob('*')
            if p.is_file() and 'private' not in p.relative_to(out).parts and p.name != 'MANIFEST.sha256'},
            'manifest mismatch')
    pin = json.loads((ROOT / 'vanguard/source-lock.json').read_text())
    require(json.loads((out / 'source-lock.json').read_text()) == pin, 'source lock')
    for field, value in (('upstream_commit', pin['upstream']['commit']),
                         ('builder_image', pin['builder']['image_id']), ('rustc', pin['builder']['rustc']),
                         ('submodules', pin['upstream']['submodules']),
                         ('cargo_lock_sha256', pin['rust']['cargo_lock_sha256'])):
        require(receipt[field] == value, 'lineage ' + field)
    require(receipt['build_mode'] in ('cached', 'rebuilt') and len(receipt['commands']) == 3 and
            set(receipt['metrics']) == {'build', 'run1', 'run2'}, 'two finite trials')
    for stage, command in zip(('build', 'run1', 'run2'), receipt['commands']):
        load.container_command(command, pin['builder']['image_id'], stage)
        if stage != 'build':
            script = 'timeout --signal=TERM 1040 python3 -B /harness/daemon-backlog.py'
        else:
            script = ('sha256sum /src/build/vanguard/bin/monerod /src/build/vanguard/bin/monero-wallet-rpc'
                      if receipt['build_mode'] == 'cached' else
                      'cd /src/build/vanguard\ntimeout 1700 make -j1 daemon wallet_rpc_server > /out/make.log 2>&1')
        trap = (f'trap \'cat /sys/fs/cgroup/memory.peak > /out/{stage}.memory; '
                f'cat /sys/fs/cgroup/memory.events > /out/{stage}.memory-events; '
                f'cat /sys/fs/cgroup/cpu.stat > /out/{stage}.cpu\' EXIT\n')
        require(command[-1] == trap + script, 'exact container script')
        m = receipt['metrics'][stage]
        work = out if stage == 'build' else out / stage
        require(m['exit'] == int((work / f'{stage}.exit').read_text()) == 0 and
                0 < m['wall_seconds'] < (1800 if stage == 'build' else 1060), 'container exit/time')
        ev = dict(line.split() for line in (work / f'{stage}.memory-events').read_text().splitlines())
        require(ev['oom'] == ev['oom_kill'] == '0' and
                0 < int((work / f'{stage}.memory').read_text()) <= 4 * 1024**3, 'cgroup memory/OOM')
        require(int(dict(line.split() for line in (work / f'{stage}.cpu').read_text().splitlines())
                    ['usage_usec']) > 0, 'cgroup CPU')
    require(set(receipt['binary']) == set(load.BINARIES), 'binary set')
    for name, (digest, size) in load.BINARIES.items():
        path = src / 'monero-fcmp/build/vanguard/bin' / name
        require(path.stat().st_size == size and sha(path) == digest, 'local executable bytes: ' + name)
        require(receipt['binary'][name] == {'sha256': digest, 'bytes': size}, 'binary claim')

    trial_transcripts, trial_seeds, trial_transactions = set(), set(), set()
    for number in (1, 2):
        public = out / f'run{number}/public'
        r = json.loads((public / 'result.json').read_text())
        require(r['schema'] == 'vanguard-backlog/1' and r['result'] == 'PASS_SCENARIO' and
                r['workload_seed'] == 1346 and r['cohort_sizes'] == [8, 8] and
                r['funding_blocks'] == 90 and r['max_blocks'] == 96 and
                r['time_limit_seconds'] == 1000 and r['transactions'] == 16 and
                0 < r['wall_seconds'] < 1000 and len(r['cohorts']) == 2, 'workload count/budget')
        raw = [json.loads(line) for line in (public / 'rpc.jsonl').read_text().splitlines()]
        transcript = hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest()
        require(transcript not in trial_transcripts, 'fresh trial RPC transcript')
        trial_transcripts.add(transcript)
        seeds = r['wallet_seed_sha256']
        require(set(seeds) == {'sender', 'receiver'} and len(set(seeds.values())) == 2 and
                not trial_seeds.intersection(seeds.values()), 'fresh trial wallet seeds')
        trial_seeds.update(seeds.values())
        require([row['id'] for row in raw] == list(range(len(raw))) and
                all(math.isfinite(row['began_s']) and math.isfinite(row['ended_s']) and
                    0 <= row['began_s'] <= row['ended_s'] < row['began_s'] + 180 for row in raw) and
                all(a['ended_s'] <= b['began_s'] for a, b in zip(raw, raw[1:])),
                'RPC receipt sequence/time')
        require(not any(row['request'].get('method') == 'start_mining' or row['path'] == 'start_mining'
                        for row in raw), 'paused mining RPCs')

        def rpc(i, port, path, method=None):
            require(isinstance(i, int) and 0 <= i < len(raw), 'RPC reference')
            row = raw[i]
            require(row['port'] == port and row['path'] == path and
                    (method is None or row['request']['method'] == method), 'RPC reference method/port')
            return row

        def ordered(refs, label):
            require(all(isinstance(i, int) and 0 <= i < len(raw) for i in refs) and
                    all(a < b for a, b in zip(refs, refs[1:])), label)

        def snap(s):
            require(len(s['tips']) == len(s['pools']) == 2 and s['tips'][0] == s['tips'][1], 'tip equality')
            refs = s['rpc_ids']['tips'] + s['rpc_ids']['pools']
            require(len(refs) == 4, 'snapshot RPC count')
            ordered(refs, 'snapshot RPC chronology')
            for n in (0, 1):
                h = rpc(s['rpc_ids']['tips'][n], 19081 + n * 100, 'json_rpc',
                        'get_last_block_header')['response']['result']['block_header']
                require(s['tips'][n] == [h['height'], h['hash'], h['wide_cumulative_difficulty']],
                        'tip RPC reconciliation')
                pools = rpc(s['rpc_ids']['pools'][n], 19081 + n * 100,
                            'get_transaction_pool')['response'].get('transactions', [])
                require(s['pools'][n] == sorted(tx['id_hash'] for tx in pools), 'pool RPC reconciliation')
            return refs

        def wallet(w, name):
            port = {'sender': 19090, 'receiver': 19190}[name]
            refs = [w['rpc_ids'][key] for key in ('refresh', 'balance', 'outputs')]
            ordered(refs, 'wallet RPC chronology')
            rpc(refs[0], port, 'json_rpc', 'refresh')
            balance = rpc(w['rpc_ids']['balance'], port, 'json_rpc', 'get_balance')['response']['result']
            rows = rpc(w['rpc_ids']['outputs'], port, 'json_rpc', 'incoming_transfers')['response']['result'].get('transfers', [])
            fields = ('tx_hash', 'amount', 'key_image', 'pubkey', 'block_height', 'spent')
            require(w['balance'] == {k: balance[k] for k in ('balance', 'unlocked_balance')} and
                    w['outputs'] == sorted([{k: row[k] for k in fields} for row in rows],
                                            key=lambda row: (row['tx_hash'], row['pubkey'])),
                    'wallet RPC reconciliation')
            require(len({row['key_image'] for row in w['outputs']}) == len(w['outputs']) and
                    len({row['pubkey'] for row in w['outputs']}) == len(w['outputs']) and
                    w['balance']['balance'] == sum(row['amount'] for row in w['outputs'] if not row['spent']) and
                    0 <= w['balance']['unlocked_balance'] <= w['balance']['balance'], 'wallet identity/balance')
            return refs

        genesis_refs = snap(r['genesis'])
        require(r['genesis']['tips'][0][0] == 0 and r['genesis']['pools'] == [[], []], 'fresh genesis')
        address_calls = [row for row in raw if row['request'].get('method') == 'get_address']
        require(len(address_calls) == 2 and {row['port'] for row in address_calls} == {19090, 19190},
                'wallet address RPC set')
        addresses = {}
        for row in address_calls:
            value = rpc(row['id'], row['port'], 'json_rpc', 'get_address')['response']['result']
            require(value['address'] and value['addresses'][0]['address_index'] == 0 and
                    value['addresses'][0]['address'] == value['address'], 'wallet address RPC binding')
            addresses[row['port']] = value['address']
        require(addresses[19090] != addresses[19190], 'distinct sender/receiver addresses')
        generated = r['generated']
        require(3 <= len(generated) <= 7 and generated[0]['label'] == 'funding' and
                generated[0]['count'] == 90 and r['blocks'] == sum(g['count'] for g in generated) <= 96,
                'generated block count/budget')
        generate_calls = [row for row in raw if row['request'].get('method') == 'generateblocks']
        require([g['rpc_id'] for g in generated] == [row['id'] for row in generate_calls],
                'all generated block RPCs accounted')
        prior_tip, block_hashes = r['genesis']['tips'], []
        generated_end = genesis_refs[-1]
        for g in generated:
            call = rpc(g['rpc_id'], 19081, 'json_rpc', 'generateblocks')
            require(call['request']['params']['amount_of_blocks'] == g['count'] == len(g['hashes']) and
                    call['response']['result']['blocks'] == g['hashes'], 'generated RPC count/hashes')
            require(call['request']['params']['wallet_address'] == addresses[19090], 'funding recipient')
            before_refs, after_refs = snap(g['before']), snap(g['after'])
            ordered([generated_end, *before_refs, g['rpc_id'], *after_refs], 'generated RPC chronology')
            generated_end = after_refs[-1]
            require(g['before']['tips'] == prior_tip and
                    g['after']['tips'][0][0] == prior_tip[0][0] + g['count'] and
                    g['after']['tips'][0][1] == g['hashes'][-1], 'generated tip continuity')
            phase(g['admission']); phase(g['convergence'])
            prior_tip = g['after']['tips']
            block_hashes.extend(g['hashes'])
        require(len(set(block_hashes)) == r['blocks'], 'duplicate generated block')
        funded_refs = wallet(r['funded_sender'], 'sender')
        original_inputs = {row['key_image']: row for row in r['funded_sender']['outputs']}
        require(len(original_inputs) >= 16 and all(not row['spent'] for row in original_inputs.values()),
                'independent funding outputs')
        rng, ids, images, amounts, immutable = random.Random(1346), [], set(), {}, {}
        require(not r['initial_receiver']['outputs'] and r['initial_receiver']['balance']['balance'] == 0,
                'fresh receiver')
        initial_refs = wallet(r['initial_receiver'], 'receiver')
        ordered([*snap(generated[0]['after']), *funded_refs, *initial_refs], 'funded wallet RPC chronology')
        ordered([genesis_refs[-1], *[row['id'] for row in address_calls],
                 snap(generated[0]['before'])[0]], 'wallet address RPC chronology')
        cursor = initial_refs[-1]
        labels = []
        for index, c in enumerate(r['cohorts'], 1):
            require(c['cohort'] == index and c['count'] == len(c['transactions']) == 8, 'cohort transaction count')
            before_refs, queued_refs, after_refs = [snap(c[s]) for s in ('before', 'queued', 'after')]
            ordered([cursor, *before_refs], 'refill RPC chronology')
            cursor = before_refs[-1]
            require(c['before']['pools'] == c['after']['pools'] == [[], []] and
                    c['before']['tips'] == (generated[0]['after']['tips'] if index == 1 else
                                           r['cohorts'][0]['after']['tips']), 'refill/drain continuity')
            current, decoded_outputs = [], {}
            for tx in c['transactions']:
                require(tx['txid'] not in ids, 'duplicate transaction')
                selected = tx['key_images']
                require(selected and len(selected) == len(set(selected)) and not images.intersection(selected) and
                        all(image in original_inputs for image in selected) and
                        tx['selected_inputs'] == [original_inputs[image] for image in selected], 'disjoint funded inputs')
                made = rpc(tx['construction_rpc_id'], 19090, 'json_rpc', 'transfer')
                require(made['request']['params']['do_not_relay'] is True and
                        made['request']['params']['get_tx_hex'] is True, 'separate construction boundary')
                value = made['response']['result']
                require(tx['amount'] == 10**12 + rng.randrange(1, 10) * 10**10 == value['amount'] and
                        tx['txid'] == value['tx_hash'] and tx['fee'] == value['fee'] and
                        tx['key_images'] == value['spent_key_images']['key_images'] and
                        tx['bytes'] == len(bytes.fromhex(value['tx_blob'])) > 1000, 'construction RPC binding')
                require(made['request']['params']['destinations'] ==
                        [{'address': addresses[19190], 'amount': tx['amount']}], 'transfer destination binding')
                admission = rpc(tx['admission_rpc_id'], 19081, 'send_raw_transaction')
                require(admission['response']['status'] == 'OK' and
                        admission['request']['tx_as_hex'] == value['tx_blob'] and
                        admission['request']['do_not_relay'] is False, 'admission RPC binding')
                decoded_call = rpc(tx['decoded_rpc_id'], 19081, 'get_transactions')
                require(decoded_call['request']['txs_hashes'] == [tx['txid']], 'decoded identity')
                native = decoded_call['response'].get('txs', [])
                require(len(native) == 1 and native[0]['tx_hash'] == tx['txid'] and
                        native[0]['in_pool'] is True, 'decoded native identity/pool')
                require(not native[0]['as_hex'] or native[0]['as_hex'] == value['tx_blob'],
                        'decoded native serialized bytes')
                decoded = json.loads(native[0]['as_json'])
                require(decoded['rct_signatures']['type'] == 7 and
                        sorted(v['key']['k_image'] for v in decoded['vin']) == sorted(selected) and
                        all('carrot_v1' in v['target'] for v in decoded['vout']), 'FCMP CARROT input shape')
                decoded_outputs[tx['txid']] = decoded['vout']
                ids.append(tx['txid']); current.append(tx['txid']); images.update(selected)
                amounts[tx['txid']] = tx['amount']
                pending_refs = snap(tx['pending'])
                ordered([cursor, made['id'], admission['id'], decoded_call['id'], *pending_refs],
                        'queue RPC chronology')
                cursor = pending_refs[-1]
                require(tx['pending']['tips'] == c['before']['tips'] and
                        tx['pending']['pools'] == [sorted(current)] * 2, 'paused mining incremental queue')
                for name in ('construction', 'origin_admission', 'peer_pool_convergence', 'reservation_refresh'):
                    phase(tx[name])
            ordered([cursor, *queued_refs], 'queued snapshot RPC chronology')
            cursor = queued_refs[-1]
            require(c['queued']['pools'] == [sorted(current)] * 2 and
                    c['queued']['tips'] == c['before']['tips'], 'eight simultaneous peer pools')
            require(0 < c['queue_seconds'] < c['duration_seconds'] < 180 and
                    0 < c['drain_seconds'] <= c['backlog_seconds'] <= c['duration_seconds'] and
                    abs(c['confirmed_tps'] - 8 / c['duration_seconds']) < 1e-12, 'queue/drain timing arithmetic')
            require(len(c['generated_labels']) == len(c['block_contents']) == len(c['block_rpc_ids']) and
                    1 <= len(c['generated_labels']) <= 3, 'drain block count')
            labels.extend(c['generated_labels'])
            mined, heights = [], {}
            for label, contents, refs in zip(c['generated_labels'], c['block_contents'], c['block_rpc_ids']):
                g = next(row for row in generated if row['label'] == label)
                require(g['count'] == 1 and g['label'].startswith(f'cohort{index}-drain'), 'cohort block binding')
                drain_before, drain_after = snap(g['before']), snap(g['after'])
                ordered([cursor, *drain_before, g['rpc_id'], *drain_after],
                        'queue before drain RPC chronology')
                cursor = drain_after[-1]
                for n in (0, 1):
                    call = rpc(refs[n], 19081 + n * 100, 'json_rpc', 'get_block')
                    require(call['request']['params']['hash'] == g['hashes'][0] and
                            contents[n] == json.loads(call['response']['result']['json']), 'block RPC binding')
                    require(call['response']['result']['block_header']['height'] == g['after']['tips'][0][0],
                            'block height binding')
                    header = call['response']['result']['block_header']
                    require(header['hash'] == g['hashes'][0] and header['orphan_status'] is False,
                            'native block identity/main-chain')
                    require(header['prev_hash'] == g['before']['tips'][0][1] == contents[n]['prev_id'] and
                            header['num_txes'] == len(contents[n]['tx_hashes']), 'native block body binding')
                require(contents[0]['tx_hashes'] == contents[1]['tx_hashes'], 'peer block membership')
                mined.extend(contents[0]['tx_hashes'])
                heights.update({txid: g['after']['tips'][0][0] for txid in contents[0]['tx_hashes']})
            require(Counter(mined) == Counter(current) and len(mined) == 8, 'exactly once confirmation')
            require(c['after']['tips'] == g['after']['tips'], 'drained tip continuity')
            confirmed = c['confirmed']
            ordered([cursor, *confirmed['rpc_ids'],
                     *[ref for pair in c['block_rpc_ids'] for ref in pair],
                     *wallet(c['receiver'], 'receiver'), *after_refs], 'confirmation RPC chronology')
            cursor = after_refs[-1]
            for n in (0, 1):
                call = rpc(confirmed['rpc_ids'][n], 19081 + n * 100, 'get_transactions')
                txs = call['response'].get('txs', [])
                require(call['request']['txs_hashes'] == ids and len(txs) == len(ids) and
                        {tx['tx_hash'] for tx in txs} == set(ids) and all(tx['in_pool'] is False for tx in txs) and
                        confirmed['nodes'][n] == [{'txid': tx['tx_hash'], 'height': tx['block_height']} for tx in txs],
                        'confirmed RPC identity/count')
                require(all(tx['block_height'] == heights.get(tx['tx_hash'], immutable.get(tx['tx_hash'], [0]*5)[4])
                            for tx in txs), 'confirmed block height')
            outputs = c['receiver']['outputs']
            require(len(outputs) == len(ids) and {o['tx_hash']: o['amount'] for o in outputs} == amounts and
                    all(not o['spent'] for o in outputs) and c['receiver']['balance'] ==
                    {'balance': sum(amounts.values()), 'unlocked_balance': 0}, 'receiver workload outputs/balance')
            identities = {o['tx_hash']: [o[k] for k in ('tx_hash', 'amount', 'key_image', 'pubkey', 'block_height')]
                          for o in outputs}
            require(all(identities[k] == v for k, v in immutable.items()), 'receiver immutable identities')
            require(all(o['block_height'] == heights[o['tx_hash']] for o in outputs if o['tx_hash'] in heights),
                    'receiver confirmation height')
            require(all(o['pubkey'] in [v['target']['carrot_v1']['key'] for v in decoded_outputs[o['tx_hash']]]
                        for o in outputs if o['tx_hash'] in decoded_outputs), 'receiver CARROT output binding')
            immutable = identities
        require(labels == [g['label'] for g in generated[1:]] and len(ids) == 16, 'all drain blocks accounted')
        require(not trial_transactions.intersection(ids), 'fresh trial transaction identities')
        trial_transactions.update(ids)
        require([row['id'] for row in raw if row['request'].get('method') == 'transfer'] ==
                [tx['construction_rpc_id'] for c in r['cohorts'] for tx in c['transactions']],
                'all wallet constructions accounted')
        require([row['id'] for row in raw if row['path'] == 'send_raw_transaction'] ==
                [tx['admission_rpc_id'] for c in r['cohorts'] for tx in c['transactions']],
                'all native admissions accounted')
        final_refs = snap(r['final'])
        require(r['final']['tips'] == prior_tip and r['final']['pools'] == [[], []], 'final convergence/drain')
        final_sender_refs = wallet(r['final_sender'], 'sender')
        final_receiver_refs = wallet(r['final_receiver'], 'receiver')
        ordered([cursor, *final_sender_refs, *final_receiver_refs, *final_refs], 'final RPC chronology')
        require(load.output_identities(r['final_receiver']) == load.output_identities(r['cohorts'][-1]['receiver']) and
                r['final_receiver']['balance'] == r['cohorts'][-1]['receiver']['balance'], 'final receiver identities')
        final_inputs = {o['key_image']: o for o in r['final_sender']['outputs']}
        require(all(final_inputs[k]['spent'] and all(final_inputs[k][f] == original_inputs[k][f]
                    for f in ('tx_hash', 'amount', 'key_image', 'pubkey', 'block_height')) for k in images),
                'confirmed sender input identities')
        require(r['process_exits'] == {name: 0 for name in NAMES}, 'successful child exits')
        events = [json.loads(line) for line in (public / 'events.jsonl').read_text().splitlines()]
        require(Counter(e['name'] for e in events if e['event'] == 'process_exit') == Counter(NAMES) and
                all(e['returncode'] == 0 for e in events if e['event'] == 'process_exit'), 'child exit events')
        starts = [e for e in events if e['event'] == 'process_started']
        require(Counter(e['name'] for e in starts) == Counter(NAMES) and
                all(e['pid'] == r['executing_binaries'][e['name']]['pid'] for e in starts), 'process identity claims')
        for e in starts:
            command = e['command']
            require(command[0] == '/src/build/vanguard/bin/' +
                    ('monerod' if e['name'].startswith('daemon') else 'monero-wallet-rpc'), 'native process executable')
            if e['name'].startswith('daemon'):
                require('--regtest' in command and '--keep-fakechain' in command and
                        command.count('--fixed-difficulty') == 1 and
                        command[command.index('--fixed-difficulty') + 1] == '1' and
                        not any(option.startswith('--start-mining') for option in command), 'fixed nonmining regtest')
        require([e['transaction'] for e in events if e['event'] == 'queue_arrival'] ==
                [tx for c in r['cohorts'] for tx in c['transactions']] and
                [e['snapshot'] for e in events if e['event'] == 'cohort_queued'] == [c['queued'] for c in r['cohorts']],
                'queue event reconciliation')
        complete = [e for e in events if e['event'] == 'scenario_complete']
        require(len(complete) == 1 and complete[0]['snapshot'] == r['final'] and
                complete[0]['blocks'] == r['blocks'] and complete[0]['transactions'] == 16, 'completion event')
        require(set(r['executing_binaries']) == set(NAMES) and all(v['sha256'] == load.BINARIES[
            'monerod' if name.startswith('daemon') else 'monero-wallet-rpc'][0]
            for name, v in r['executing_binaries'].items()), 'writer live executable claims')
        containment = json.loads((public / 'containment.json').read_text())
        require(containment['interfaces'] == ['lo'] and not containment['routes'] and
                containment['socket_mode'] == '0o600' and len(containment['listeners_before_shutdown']) >= 6,
                'loopback containment claims')
        ready = [e for e in events if e['event'] == 'bridge_ready']
        require(len(ready) == 1 and ready[0]['socket_mode'] == containment['socket_mode'],
                'observed socket mode reconciliation')
        seed_rows = [row for row in raw if row['request'].get('method') == 'query_key']
        require(len(seed_rows) == 2 and {row['port']: row['response']['redacted_seed_sha256'] for row in seed_rows}
                == {19090: r['wallet_seed_sha256']['sender'], 19190: r['wallet_seed_sha256']['receiver']},
                'seed digest reconciliation')
        require(all(row['local'].startswith(('0100007F:', '00000000000000000000000001000000:'))
                    for row in containment['listeners_before_shutdown']), 'loopback listener addresses')
        require(r['bridge']['connections'] >= 1 and r['bridge']['bytes'] > 0 and
                any(json.loads(line)['command'] == 2002 for line in (public / 'wire.jsonl').read_text().splitlines()),
                'native P2P transaction activity')
    print('PASS_BACKLOG_RECEIPT_RECONCILIATION two_trials=2 cohorts=8+8')
    print('PASS_LOCAL_EXECUTABLE_BYTES monerod+wallet_rpc')
    print('UNVERIFIED_LIVE_TIPS post-run RPC records are historical claims, including writer /proc hashes')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('out', type=Path)
    parser.add_argument('--src', type=Path, required=True)
    args = parser.parse_args()
    try:
        verify(args.out.resolve(), args.src.resolve())
    except (AssertionError, KeyError, ValueError, OSError, IndexError, TypeError,
            StopIteration, subprocess.CalledProcessError) as error:
        raise SystemExit('FAIL_DAEMON_BACKLOG: ' + str(error))
