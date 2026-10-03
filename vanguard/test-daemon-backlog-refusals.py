#!/usr/bin/env python3
"""Rehashed contradictory controls for the native backlog receipt gate."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('controls', ROOT / 'vanguard/test-daemon-load-refusals.py')
controls = importlib.util.module_from_spec(spec)
spec.loader.exec_module(controls)


def check(out, src):
    return subprocess.run(['python3', '-B', str(ROOT / 'vanguard/verify-daemon-backlog.py'),
                          str(out), '--src', str(src)], capture_output=True, text=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('out', type=Path)
    parser.add_argument('--src', type=Path, required=True)
    parser.add_argument('--scratch', type=Path, required=True)
    args = parser.parse_args()
    clean = check(args.out, args.src)
    assert clean.returncode == 0, clean.stderr
    args.scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='backlog-controls-', dir=args.scratch) as tmp:
        base = Path(tmp)
        refused = []

        def test(name, label, mutate=None, mutate_bundle=None):
            out = base / name
            controls.copy_public(args.out, out)
            p = out / 'run1/public'
            result = json.loads((p / 'result.json').read_text())
            rpc = [json.loads(line) for line in (p / 'rpc.jsonl').read_text().splitlines()]
            events = [json.loads(line) for line in (p / 'events.jsonl').read_text().splitlines()]
            receipt = json.loads((out / 'receipt.json').read_text())
            if mutate is not None:
                mutate(result, rpc, events, receipt)
            (p / 'result.json').write_text(json.dumps(result) + '\n')
            (p / 'rpc.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rpc))
            (p / 'events.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in events))
            (out / 'receipt.json').write_text(json.dumps(receipt) + '\n')
            if mutate_bundle is not None:
                mutate_bundle(out)
            controls.manifest(out)
            manifest = subprocess.run(['sha256sum', '-c', 'MANIFEST.sha256'], cwd=out, capture_output=True)
            assert manifest.returncode == 0, name
            observed = check(out, args.src)
            if label is None:
                assert observed.returncode == 0 and 'UNVERIFIED_LIVE_TIPS' in observed.stdout, observed.stderr
                print('LIMIT ' + name + ': UNVERIFIED_LIVE_TIPS')
            else:
                assert observed.returncode != 0 and label in observed.stderr, (name, observed.stderr)
                refused.append(name)
                print(f'REFUSED {name}: {label}')

        test('missing-transaction', 'cohort transaction count',
             lambda r, raw, e, b: r['cohorts'][0]['transactions'].pop())
        test('duplicate-transaction', 'duplicate transaction',
             lambda r, raw, e, b: r['cohorts'][0]['transactions'][1].update(
                 txid=r['cohorts'][0]['transactions'][0]['txid']))
        test('pending-input-reuse', 'disjoint funded inputs',
             lambda r, raw, e, b: r['cohorts'][0]['transactions'][1].update(
                 key_images=r['cohorts'][0]['transactions'][0]['key_images']))
        test('fake-pool-convergence', 'pool RPC reconciliation',
             lambda r, raw, e, b: r['cohorts'][0]['queued']['pools'][1].pop())

        def seven(r, raw, events, receipt):
            queued = r['cohorts'][0]['queued']
            for n in (0, 1):
                missing = queued['pools'][n].pop()
                row = raw[queued['rpc_ids']['pools'][n]]
                row['response']['transactions'] = [tx for tx in row['response']['transactions']
                                                    if tx['id_hash'] != missing]
        test('coherent-seven-in-pools', 'eight simultaneous peer pools', seven)
        for field, wrong in (('amount', 1), ('pubkey', '0' * 64), ('key_image', '0' * 64),
                             ('tx_hash', '0' * 64), ('block_height', 999)):
            test('wrong-wallet-' + field, 'wallet RPC reconciliation',
                 lambda r, raw, e, b, f=field, v=wrong: r['cohorts'][0]['receiver']['outputs'][0].update({f: v}))

        def carrot(r, raw, events, receipt):
            w = r['cohorts'][0]['receiver']
            txid = w['outputs'][0]['tx_hash']
            w['outputs'][0]['pubkey'] = '0' * 64
            for t in raw[w['rpc_ids']['outputs']]['response']['result']['transfers']:
                if t['tx_hash'] == txid:
                    t['pubkey'] = '0' * 64
        test('coherent-wrong-CARROT-output', 'receiver CARROT output binding', carrot)
        test('nonzero-child-exit', 'successful child exits',
             lambda r, raw, e, b: r['process_exits'].update(sender=1))
        test('nonzero-child-exit-event', 'child exit events',
             lambda r, raw, e, b: next(row for row in e if row['event'] == 'process_exit').update(returncode=1))
        test('count-budget-mismatch', 'generated block count/budget',
             lambda r, raw, e, b: r.update(blocks=r['blocks'] + 1))
        test('zero-generated-blocks', 'generated block count/budget',
             lambda r, raw, e, b: r.update(blocks=0))
        test('wrong-generated-RPC-count', 'generated RPC count/hashes',
             lambda r, raw, e, b: raw[r['generated'][0]['rpc_id']]['request']['params'].update(amount_of_blocks=89))
        test('silent-cohort-reduction', 'workload count/budget',
             lambda r, raw, e, b: r.update(cohort_sizes=[7, 7]))
        test('nonzero-container-exit', 'container exit/time',
             lambda r, raw, e, b: b['metrics']['run1'].update(exit=1))
        test('wrong-recorded-binary', 'binary claim',
             lambda r, raw, e, b: b['binary']['monerod'].update(sha256='0' * 64))
        test('wrong-upstream-pin', 'lineage upstream_commit',
             lambda r, raw, e, b: b.update(upstream_commit='0' * 40))
        test('conflicting-network-option', 'container containment',
             lambda r, raw, e, b: b['commands'][1].insert(5, '--network=host'))
        test('phase-over-budget', 'phase time budget',
             lambda r, raw, e, b: r['cohorts'][0]['transactions'][0]['construction'].update(wall_seconds=181))
        test('scenario-over-budget', 'workload count/budget',
             lambda r, raw, e, b: r.update(wall_seconds=1001))

        def replay(out):
            shutil.rmtree(out / 'run2/public')
            shutil.copytree(out / 'run1/public', out / 'run2/public')
        test('replayed-trial1-as-trial2', 'fresh trial RPC transcript', mutate_bundle=replay)

        def reused_seed(out):
            seed = json.loads((out / 'run1/public/result.json').read_text())['wallet_seed_sha256']['sender']
            p = out / 'run2/public'
            r = json.loads((p / 'result.json').read_text())
            r['wallet_seed_sha256']['sender'] = seed
            rows = [json.loads(line) for line in (p / 'rpc.jsonl').read_text().splitlines()]
            for row in rows:
                if row['port'] == 19090 and row['request'].get('method') == 'query_key':
                    row['response']['redacted_seed_sha256'] = seed
            (p / 'result.json').write_text(json.dumps(r) + '\n')
            (p / 'rpc.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
        test('reused-trial-wallet-seed', 'fresh trial wallet seeds', mutate_bundle=reused_seed)

        def relabelled_replay(out):
            p = out / 'run2/public'
            seeds = json.loads((p / 'result.json').read_text())['wallet_seed_sha256']
            replay(out)
            r = json.loads((p / 'result.json').read_text())
            r['wallet_seed_sha256'] = seeds
            rows = [json.loads(line) for line in (p / 'rpc.jsonl').read_text().splitlines()]
            for row in rows:
                row['began_s'] += 1000
                row['ended_s'] += 1000
                if row['request'].get('method') == 'query_key':
                    row['response']['redacted_seed_sha256'] = seeds['sender' if row['port'] == 19090 else 'receiver']
            (p / 'result.json').write_text(json.dumps(r) + '\n')
            (p / 'rpc.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
        test('replayed-trial-with-relabelled-seeds', 'fresh trial transaction identities',
             mutate_bundle=relabelled_replay)

        def early_drain(r, raw, events, receipt):
            # Preserve all call contents, rebind references and retain increasing
            # timestamps, as in independent QA's F2 counterexample.
            drain = r['generated'][1]['rpc_id']
            eighth = r['cohorts'][0]['transactions'][-1]['construction_rpc_id']
            times = [(row['began_s'], row['ended_s']) for row in raw]
            raw.insert(eighth, raw.pop(drain))
            mapping = {row['id']: i for i, row in enumerate(raw)}
            for i, row in enumerate(raw):
                row.update(id=i, began_s=times[i][0], ended_s=times[i][1])

            def refs(value):
                if isinstance(value, int):
                    return mapping[value]
                if isinstance(value, list):
                    return [refs(v) for v in value]
                return {k: refs(v) for k, v in value.items()}

            def visit(value):
                if isinstance(value, dict):
                    for key, child in list(value.items()):
                        if key.endswith('_rpc_id') or key == 'rpc_id':
                            value[key] = mapping[child]
                        elif key in ('rpc_ids', 'block_rpc_ids'):
                            value[key] = refs(child)
                        else:
                            visit(child)
                elif isinstance(value, list):
                    for child in value:
                        visit(child)
            visit(r); visit(events)
        test('drain-before-eighth-submission', 'generated RPC chronology', early_drain)
        test('reused-eight-hash-queued-snapshot', 'queued snapshot RPC chronology',
             lambda r, raw, e, b: r['cohorts'][0].update(queued=r['cohorts'][0]['transactions'][-1]['pending']))
        test('reused-refill-snapshot', 'refill RPC chronology',
             lambda r, raw, e, b: r['cohorts'][1].update(before=r['cohorts'][0]['after']))
        test('RPC-timestamp-inversion', 'RPC receipt sequence/time',
             lambda r, raw, e, b: raw[1].update(began_s=raw[0]['began_s'], ended_s=raw[0]['ended_s']))
        test('RPC-nonfinite-timestamp', 'RPC receipt sequence/time',
             lambda r, raw, e, b: raw[0].update(began_s=float('nan')))

        def mining(r, raw, events, receipt):
            raw.append({'id': len(raw), 'port': 19081, 'path': 'start_mining',
                        'request': {'miner_address': 'contradictory-mining-request'},
                        'response': {'status': 'OK'}, 'began_s': raw[-1]['ended_s'] + 0.1,
                        'ended_s': raw[-1]['ended_s'] + 0.2})
        test('unexpected-mining-RPC', 'paused mining RPCs', mining)

        for field, wrong in (('hash', '0' * 64), ('orphan_status', True)):
            test('peer-block-' + field, 'native block identity/main-chain',
                 lambda r, raw, e, b, f=field, v=wrong:
                 raw[r['cohorts'][0]['block_rpc_ids'][0][1]]['response']['result']['block_header'].update({f: v}))
        for field, wrong in (('tx_hash', '0' * 64), ('in_pool', False)):
            test('decoded-native-' + field, 'decoded native identity/pool',
                 lambda r, raw, e, b, f=field, v=wrong:
                 raw[r['cohorts'][0]['transactions'][0]['decoded_rpc_id']]['response']['txs'][0].update({f: v}))
        test('decoded-native-duplicate-response', 'decoded native identity/pool',
             lambda r, raw, e, b: raw[r['cohorts'][0]['transactions'][0]['decoded_rpc_id']]['response']['txs'].append(
                 raw[r['cohorts'][0]['transactions'][0]['decoded_rpc_id']]['response']['txs'][0]))
        test('decoded-native-tx-unrelated-blob', 'decoded native serialized bytes',
             lambda r, raw, e, b: raw[r['cohorts'][0]['transactions'][0]['decoded_rpc_id']]['response']['txs'][0].update(
                 as_hex=raw[r['cohorts'][0]['transactions'][1]['construction_rpc_id']]['response']['result']['tx_blob']))
        test('transfer-request-wrong-amount', 'transfer destination binding',
             lambda r, raw, e, b: raw[r['cohorts'][0]['transactions'][0]['construction_rpc_id']]['request']['params'][
                 'destinations'][0].update(amount=r['cohorts'][0]['transactions'][0]['amount'] + 1))

        def pays_sender(r, raw, events, receipt):
            address = next(row['response']['result']['address'] for row in raw
                           if row['port'] == 19090 and row['request'].get('method') == 'get_address')
            raw[r['cohorts'][0]['transactions'][0]['construction_rpc_id']]['request']['params'][
                'destinations'][0]['address'] = address
        test('transfer-request-pays-sender', 'transfer destination binding', pays_sender)

        def false_genesis(r, raw, events, receipt):
            # A coherent historical forgery is outside receipt authentication.
            # Change all zero-height tips and matching raw headers consistently.
            def visit(value):
                if isinstance(value, dict):
                    if 'tips' in value:
                        for tip in value['tips']:
                            if isinstance(tip, list) and len(tip) >= 2 and tip[0] == 0:
                                tip[1] = '0' * 64
                    for child in value.values():
                        visit(child)
                elif isinstance(value, list):
                    for child in value:
                        visit(child)
            visit(r); visit(events)
            for row in raw:
                if row['request'].get('method') == 'get_last_block_header':
                    h = row['response']['result']['block_header']
                    if h['height'] == 0:
                        h['hash'] = '0' * 64
        test('coherent-equal-wrong-genesis', None, false_genesis)
        forged = base / 'wrong-src/monero-fcmp/build/vanguard/bin'
        forged.mkdir(parents=True)
        (forged / 'monerod').write_bytes(b'wrong executable bytes')
        shutil.copy2(args.src / 'monero-fcmp/build/vanguard/bin/monero-wallet-rpc', forged / 'monero-wallet-rpc')
        observed = check(args.out, base / 'wrong-src')
        assert observed.returncode != 0 and 'local executable bytes: monerod' in observed.stderr
        refused.append('wrong-local-executable')
        print('REFUSED wrong-local-executable: local executable bytes: monerod')
    print(f'PASS_BACKLOG_REFUSALS refused={len(refused)} historical_limit=1')


if __name__ == '__main__':
    main()
