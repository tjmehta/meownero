#!/usr/bin/env python3
"""Independent TJS-1347 raw-receipt checks and rehashed counterexamples.

All mutations are receipt data. No mutated command is executed.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import shutil
import subprocess


def read(path):
    return json.loads(path.read_text())


def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def dump(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def manifest(out):
    (out / 'MANIFEST.sha256').write_text(''.join(
        f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(out)}\n'
        for p in sorted(out.rglob('*')) if p.is_file() and p.name != 'MANIFEST.sha256'))
    check = subprocess.run(['sha256sum', '--status', '-c', 'MANIFEST.sha256'], cwd=out)
    assert check.returncode == 0


def audit(bundle):
    summaries = []
    seeds = []
    trial_ids = []
    for number in (1, 2):
        public = bundle / f'run{number}/public'
        r = read(public / 'result.json')
        raw = lines(public / 'rpc.jsonl')
        events = lines(public / 'events.jsonl')
        assert [x['id'] for x in raw] == list(range(len(raw)))
        assert all(a['ended_s'] <= b['began_s'] for a, b in zip(raw, raw[1:]))
        assert all(0 <= x['ended_s'] - x['began_s'] < 180 for x in raw)
        assert not any(x['request'].get('method') in ('start_mining', 'stop_mining') for x in raw)
        assert all('error' not in x['response'] and x['response'].get('status', 'OK') == 'OK' for x in raw)
        addresses = {x['port']: x['response']['result']['address'] for x in raw
                     if x['request'].get('method') == 'get_address'}
        assert len(addresses) == 2 and addresses[19090] != addresses[19190]
        seeds.append(r['wallet_seed_sha256'])

        def snapshot(s):
            assert s['tips'][0] == s['tips'][1]
            refs = []
            for n in (0, 1):
                ti, pi = s['rpc_ids']['tips'][n], s['rpc_ids']['pools'][n]
                refs.extend((ti, pi))
                tip, pool = raw[ti], raw[pi]
                assert tip['port'] == pool['port'] == 19081 + 100 * n
                assert tip['request']['method'] == 'get_last_block_header'
                assert pool['path'] == 'get_transaction_pool'
                h = tip['response']['result']['block_header']
                assert s['tips'][n] == [h['height'], h['hash'], h['wide_cumulative_difficulty']]
                assert s['pools'][n] == sorted(t['id_hash'] for t in pool['response'].get('transactions', []))
            return min(refs), max(refs)

        def wallet(w, port):
            refs = w['rpc_ids']
            assert refs['refresh'] < refs['balance'] < refs['outputs']
            for key, method in (('refresh', 'refresh'), ('balance', 'get_balance'), ('outputs', 'incoming_transfers')):
                assert raw[refs[key]]['port'] == port and raw[refs[key]]['request']['method'] == method
            balance = raw[refs['balance']]['response']['result']
            outputs = raw[refs['outputs']]['response']['result'].get('transfers', [])
            fields = ('tx_hash', 'amount', 'key_image', 'pubkey', 'block_height', 'spent')
            assert w['outputs'] == sorted([{k: t[k] for k in fields} for t in outputs], key=lambda t: (t['tx_hash'], t['pubkey']))
            assert w['balance'] == {k: balance[k] for k in ('balance', 'unlocked_balance')}
            assert balance['balance'] == sum(t['amount'] for t in outputs if not t['spent'])
            assert len({t['key_image'] for t in outputs}) == len({t['pubkey'] for t in outputs}) == len(outputs)

        assert r['cohort_sizes'] == [8, 8] and r['transactions'] == 16 and r['funding_blocks'] == 90
        snapshot(r['genesis'])
        assert r['genesis']['tips'][0][0] == 0 and r['genesis']['pools'] == [[], []]
        assert r['blocks'] == sum(g['count'] for g in r['generated']) == 92
        assert len(r['generated']) == 3 and r['generated'][0]['count'] == 90
        prior = r['genesis']['tips']
        for g in r['generated']:
            b, e = snapshot(g['before']), snapshot(g['after'])
            call = raw[g['rpc_id']]
            assert b[1] < g['rpc_id'] < e[0]
            assert call['request']['method'] == 'generateblocks' and call['port'] == 19081
            assert call['request']['params']['wallet_address'] == addresses[19090]
            assert call['request']['params']['amount_of_blocks'] == g['count'] == len(g['hashes'])
            assert call['response']['result']['blocks'] == g['hashes']
            assert g['before']['tips'] == prior
            assert g['after']['tips'][0][0] == prior[0][0] + g['count']
            assert g['after']['tips'][0][1] == g['hashes'][-1]
            prior = g['after']['tips']
        wallet(r['funded_sender'], 19090)
        wallet(r['initial_receiver'], 19190)
        assert not r['initial_receiver']['outputs']
        funded = {t['key_image']: t for t in r['funded_sender']['outputs']}
        assert len(funded) == 90 and all(not t['spent'] for t in funded.values())
        rng = random.Random(1346)
        ids, images, blobs, amounts, immutable = [], set(), {}, {}, {}
        cohort_summaries = []
        for index, c in enumerate(r['cohorts'], 1):
            assert c['cohort'] == index and c['count'] == len(c['transactions']) == 8
            before, queued, after = snapshot(c['before']), snapshot(c['queued']), snapshot(c['after'])
            assert c['before']['pools'] == c['after']['pools'] == [[], []]
            assert c['before']['tips'] == (r['generated'][0]['after']['tips'] if index == 1 else r['cohorts'][0]['after']['tips'])
            current = []
            previous = before[1]
            decoded = {}
            for tx in c['transactions']:
                make, admit, decode = (raw[tx[k]] for k in ('construction_rpc_id', 'admission_rpc_id', 'decoded_rpc_id'))
                assert previous < make['id'] < admit['id'] < decode['id'] < snapshot(tx['pending'])[0]
                assert make['request']['params']['destinations'] == [{'address': addresses[19190], 'amount': tx['amount']}]
                val = make['response']['result']
                assert val['tx_hash'] == tx['txid'] and val['fee'] == tx['fee']
                assert val['amount'] == tx['amount'] == 10**12 + rng.randrange(1, 10) * 10**10
                assert val['spent_key_images']['key_images'] == tx['key_images']
                assert admit['request']['tx_as_hex'] == val['tx_blob'] and admit['response']['status'] == 'OK'
                assert len(decode['response']['txs']) == 1
                native = decode['response']['txs'][0]
                assert native['tx_hash'] == tx['txid'] and native['in_pool'] is True
                # JSON is a native decoded view; the RPC may return empty as_hex when decode_as_json is requested.
                assert not native['as_hex'] or native['as_hex'] == val['tx_blob']
                obj = json.loads(native['as_json'])
                assert obj['rct_signatures']['type'] == 7 and obj['vout']
                assert all('carrot_v1' in o['target'] for o in obj['vout'])
                assert sorted(v['key']['k_image'] for v in obj['vin']) == sorted(tx['key_images'])
                assert tx['txid'] not in ids and tx['key_images'] and not images.intersection(tx['key_images'])
                assert len(tx['key_images']) == len(set(tx['key_images']))
                assert tx['selected_inputs'] == [funded[k] for k in tx['key_images']]
                images.update(tx['key_images']); ids.append(tx['txid']); current.append(tx['txid'])
                amounts[tx['txid']] = tx['amount']; blobs[tx['txid']] = val['tx_blob']; decoded[tx['txid']] = obj
                assert tx['pending']['tips'] == c['before']['tips']
                assert tx['pending']['pools'] == [sorted(current)] * 2
                previous = snapshot(tx['pending'])[1]
            assert previous < queued[0]
            assert c['queued']['tips'] == c['before']['tips'] and c['queued']['pools'] == [sorted(current)] * 2
            mined, heights = [], {}
            for label, refs, contents in zip(c['generated_labels'], c['block_rpc_ids'], c['block_contents']):
                g = next(g for g in r['generated'] if g['label'] == label)
                assert queued[1] < g['rpc_id'] < min(refs) < after[0]
                for n, ref in enumerate(refs):
                    row = raw[ref]
                    block = row['response']['result']
                    h = block['block_header']
                    assert row['port'] == 19081 + 100 * n and row['request']['method'] == 'get_block'
                    assert row['request']['params']['hash'] == h['hash'] == g['hashes'][0]
                    assert not h['orphan_status'] and h['height'] == g['after']['tips'][0][0]
                    assert h['prev_hash'] == g['before']['tips'][0][1]
                    assert contents[n] == json.loads(block['json']) and contents[n]['prev_id'] == h['prev_hash']
                    assert h['num_txes'] == len(contents[n]['tx_hashes'])
                assert contents[0] == contents[1]
                mined.extend(contents[0]['tx_hashes'])
                heights.update({tid: g['after']['tips'][0][0] for tid in contents[0]['tx_hashes']})
            assert Counter(mined) == Counter(current)
            assert c['after']['tips'] == g['after']['tips']
            for n, ref in enumerate(c['confirmed']['rpc_ids']):
                row = raw[ref]
                assert row['port'] == 19081 + 100 * n and row['request']['txs_hashes'] == ids
                assert len(row['response']['txs']) == len(ids)
                assert {t['tx_hash'] for t in row['response']['txs']} == set(ids)
                for t in row['response']['txs']:
                    assert t['in_pool'] is False
                    assert t['block_height'] == heights.get(t['tx_hash'], immutable.get(t['tx_hash'], {}).get('block_height'))
                    assert not t['as_hex'] or t['as_hex'] == blobs[t['tx_hash']]
            wallet(c['receiver'], 19190)
            assert len(c['receiver']['outputs']) == len(ids)
            assert {t['tx_hash']: t['amount'] for t in c['receiver']['outputs']} == amounts
            assert c['receiver']['balance'] == {'balance': sum(amounts.values()), 'unlocked_balance': 0}
            for output in c['receiver']['outputs']:
                assert not output['spent']
                tid = output['tx_hash']
                if tid in immutable:
                    assert output == immutable[tid]
                else:
                    assert output['block_height'] == heights[tid]
                    assert output['pubkey'] in [v['target']['carrot_v1']['key'] for v in decoded[tid]['vout']]
            immutable = {t['tx_hash']: t for t in c['receiver']['outputs']}
            cohort_summaries.append({'cohort': index, 'tx_count': len(current), 'queued_pool_counts': [len(x) for x in c['queued']['pools']], 'queued_rpc_ids': c['queued']['rpc_ids'], 'drain_rpc_ids': [g['rpc_id']], 'drain_height': g['after']['tips'][0][0], 'receiver_balance': c['receiver']['balance'], 'duration_seconds': c['duration_seconds']})
        assert [x['id'] for x in raw if x['request'].get('method') == 'generateblocks'] == [g['rpc_id'] for g in r['generated']]
        assert [x['id'] for x in raw if x['request'].get('method') == 'transfer'] == [t['construction_rpc_id'] for c in r['cohorts'] for t in c['transactions']]
        assert [x['id'] for x in raw if x['path'] == 'send_raw_transaction'] == [t['admission_rpc_id'] for c in r['cohorts'] for t in c['transactions']]
        wallet(r['final_receiver'], 19190); wallet(r['final_sender'], 19090)
        assert r['final_receiver']['outputs'] == r['cohorts'][-1]['receiver']['outputs']
        final_inputs = {x['key_image']: x for x in r['final_sender']['outputs']}
        for ki in images:
            assert final_inputs[ki] == {**funded[ki], 'spent': True}
        snapshot(r['final'])
        assert r['final']['tips'] == prior and r['final']['pools'] == [[], []]
        assert r['process_exits'] == {k: 0 for k in ('daemon0', 'daemon1', 'sender', 'receiver')}
        assert Counter(e['name'] for e in events if e['event'] == 'process_exit') == Counter(r['process_exits'].keys())
        assert all(e['returncode'] == 0 for e in events if e['event'] == 'process_exit')
        trial_ids.append(set(ids))
        summaries.append({'trial': number, 'raw_rpc_rows': len(raw), 'generated_blocks': r['blocks'], 'funded_outputs': len(funded), 'selected_disjoint_inputs': len(images), 'cohorts': cohort_summaries, 'final_receiver_outputs': len(r['final_receiver']['outputs']), 'scenario_seconds': r['wall_seconds'], 'process_exits': r['process_exits']})
    assert seeds[0]['sender'] != seeds[1]['sender'] and seeds[0]['receiver'] != seeds[1]['receiver']
    assert not trial_ids[0].intersection(trial_ids[1])
    return {'result': 'PASS_INDEPENDENT_RAW_AUDIT', 'fresh_historical_wallets_distinct': True, 'trials': summaries}


def controls(args):
    result = []
    cases = args.out / 'cases'
    cases.mkdir()

    def run_case(name, mutate, expected):
        out = cases / name
        shutil.copytree(args.bundle, out)
        p = out / 'run1/public'
        r, raw, events = read(p / 'result.json'), lines(p / 'rpc.jsonl'), lines(p / 'events.jsonl')
        mutate(r, raw, events, out)
        dump(p / 'result.json', r)
        for file, rows in (('rpc.jsonl', raw), ('events.jsonl', events)):
            (p / file).write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
        manifest(out)
        observed = subprocess.run(['python3', '-B', str(args.repo / 'vanguard/verify-daemon-backlog.py'), str(out), '--src', str(args.src)], capture_output=True, text=True)
        entry = {'name': name, 'expected': expected, 'exit': observed.returncode, 'stdout': observed.stdout, 'stderr': observed.stderr, 'rehash_verified': True, 'manifest_sha256': hashlib.sha256((out / 'MANIFEST.sha256').read_bytes()).hexdigest()}
        result.append(entry)
        print(name, 'ACCEPTED' if observed.returncode == 0 else 'REFUSED', flush=True)

    def replay(r, raw, e, out):
        shutil.rmtree(out / 'run2/public')
        shutil.copytree(out / 'run1/public', out / 'run2/public')
    run_case('replayed-trial1-as-trial2', replay, 'refuse: two fresh trials')

    def reorder(r, raw, events, out):
        # Move first drain before the eighth construction, while preserving each
        # request/response and rebinding every index. Keep raw times increasing.
        drain = r['generated'][1]['rpc_id']
        eighth = r['cohorts'][0]['transactions'][-1]['construction_rpc_id']
        times = [(x['began_s'], x['ended_s']) for x in raw]
        row = raw.pop(drain); raw.insert(eighth, row)
        mapping = {x['id']: i for i, x in enumerate(raw)}
        for i, x in enumerate(raw):
            x.update(id=i, began_s=times[i][0], ended_s=times[i][1])
        def visit(x):
            if isinstance(x, dict):
                for key, val in list(x.items()):
                    if key.endswith('_rpc_id') or key == 'rpc_id': x[key] = mapping[val]
                    elif key == 'rpc_ids' or key == 'block_rpc_ids': x[key] = refs(val)
                    else: visit(val)
            elif isinstance(x, list):
                for child in x: visit(child)
        def refs(x):
            if isinstance(x, int): return mapping[x]
            if isinstance(x, list): return [refs(v) for v in x]
            return {k: refs(v) for k, v in x.items()}
        visit(r); visit(events)
    run_case('drain-before-eighth-submission', reorder, 'refuse: paused mining and queue before drain')

    def block_hash(r, raw, e, out):
        ref = r['cohorts'][0]['block_rpc_ids'][0][1]
        raw[ref]['response']['result']['block_header']['hash'] = '0' * 64
    run_case('peer-block-header-wrong-hash', block_hash, 'refuse: generated block identity')
    def orphan(r, raw, e, out):
        ref = r['cohorts'][0]['block_rpc_ids'][0][1]
        raw[ref]['response']['result']['block_header']['orphan_status'] = True
    run_case('peer-block-marked-orphan', orphan, 'refuse: block on peer main chain')
    def decoded_hash(r, raw, e, out):
        ref = r['cohorts'][0]['transactions'][0]['decoded_rpc_id']
        raw[ref]['response']['txs'][0]['tx_hash'] = '0' * 64
    run_case('decoded-native-tx-wrong-hash', decoded_hash, 'refuse: decoded transaction identity')
    def decoded_blob(r, raw, e, out):
        txs = r['cohorts'][0]['transactions']
        raw[txs[0]['decoded_rpc_id']]['response']['txs'][0]['as_hex'] = raw[txs[1]['construction_rpc_id']]['response']['result']['tx_blob']
    run_case('decoded-native-tx-unrelated-blob', decoded_blob, 'refuse: decoded/submitted bytes binding')
    def wrong_amount(r, raw, e, out):
        raw[r['cohorts'][0]['transactions'][0]['construction_rpc_id']]['request']['params']['destinations'][0]['amount'] += 1
    run_case('transfer-request-wrong-amount', wrong_amount, 'refuse: requested transfer amount')
    def wrong_address(r, raw, e, out):
        sender = next(x['response']['result']['address'] for x in raw if x['port'] == 19090 and x['request'].get('method') == 'get_address')
        raw[r['cohorts'][0]['transactions'][0]['construction_rpc_id']]['request']['params']['destinations'][0]['address'] = sender
    run_case('transfer-request-pays-sender', wrong_address, 'refuse: requested receiver identity')
    def duplicate(r, raw, e, out):
        r['cohorts'][1]['transactions'][0]['txid'] = r['cohorts'][0]['transactions'][0]['txid']
    run_case('cross-cohort-duplicate', duplicate, 'refuse: duplicate transaction')
    def extra_generate(r, raw, e, out):
        x = json.loads(json.dumps(raw[r['generated'][-1]['rpc_id']]))
        x.update(id=len(raw), began_s=raw[-1]['ended_s'] + 0.1, ended_s=raw[-1]['ended_s'] + 0.2)
        raw.append(x)
    run_case('unaccounted-generate', extra_generate, 'refuse: all generated block RPCs accounted')
    def extra_transfer(r, raw, e, out):
        x = json.loads(json.dumps(raw[r['cohorts'][-1]['transactions'][-1]['construction_rpc_id']]))
        x.update(id=len(raw), began_s=raw[-1]['ended_s'] + 0.1, ended_s=raw[-1]['ended_s'] + 0.2)
        raw.append(x)
    run_case('unaccounted-transfer', extra_transfer, 'refuse: all wallet constructions accounted')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('repo', 'bundle', 'src', 'out'): parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir()
    try:
        observed = audit(args.bundle)
    except AssertionError:
        raise
    dump(args.out / 'independent-raw-audit.json', observed)
    print(observed['result'], flush=True)
    baseline = subprocess.run(['python3', '-B', str(args.repo / 'vanguard/verify-daemon-backlog.py'), str(args.bundle), '--src', str(args.src)], capture_output=True, text=True)
    dump(args.out / 'baseline.json', {'exit': baseline.returncode, 'stdout': baseline.stdout, 'stderr': baseline.stderr})
    assert baseline.returncode == 0, baseline.stderr
    dump(args.out / 'counterexamples.json', controls(args))


if __name__ == '__main__':
    main()
