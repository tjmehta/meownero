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

        def test(name, label, mutate):
            out = base / name
            controls.copy_public(args.out, out)
            p = out / 'run1/public'
            result = json.loads((p / 'result.json').read_text())
            rpc = [json.loads(line) for line in (p / 'rpc.jsonl').read_text().splitlines()]
            events = [json.loads(line) for line in (p / 'events.jsonl').read_text().splitlines()]
            receipt = json.loads((out / 'receipt.json').read_text())
            mutate(result, rpc, events, receipt)
            (p / 'result.json').write_text(json.dumps(result) + '\n')
            (p / 'rpc.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rpc))
            (p / 'events.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in events))
            (out / 'receipt.json').write_text(json.dumps(receipt) + '\n')
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
