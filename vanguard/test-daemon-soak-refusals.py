#!/usr/bin/env python3
"""Rehashed independent contradictions against a passing two-live-trial baseline."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

spec = importlib.util.spec_from_file_location('verify_soak', Path(__file__).with_name('verify-daemon-soak.py'))
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


def rehash(out):
    (out / 'MANIFEST.sha256').write_text(''.join(verifier.sha(p) + '  ' + str(p.relative_to(out)) + '\n'
        for p in sorted(out.rglob('*')) if p.is_file() and 'private' not in p.relative_to(out).parts and p.name != 'MANIFEST.sha256'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', type=Path)
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    baseline, work = args.baseline.resolve(), args.work.resolve()
    print(json.dumps(verifier.verify(baseline)), flush=True)
    work.mkdir(parents=True, exist_ok=False)
    cases = [
        ('duration', lambda r: r.update(measured_seconds=1799)),
        ('payment-count', lambda r: r.update(transactions=31)),
        ('workload-replay', lambda r: r.update(workload_seed=json.loads((baseline / 'run2/public/result.json').read_text())['workload_seed'])),
        ('early-drain', lambda r: r['cohorts'][0]['full_queue']['rpc_ids'].__setitem__(3, r['generated'][2]['rpc_id'])),
        ('input-reuse', lambda r: r['cohorts'][0]['transactions'][1].update(key_images=r['cohorts'][0]['transactions'][0]['key_images'])),
        ('destination', lambda r: r['cohorts'][0]['transactions'][0].update(destination=r['addresses']['senderA'])),
        ('native-bytes', lambda r: r['cohorts'][0]['transactions'][0].update(blob='00')),
        ('peer-block', lambda r: r['cohorts'][0]['transactions'][0]['confirmed'][1].update(block_hash='0' * 64)),
        ('credit-duplicate', lambda r: r['cohorts'][0]['recipient_state']['outputs'].append(copy.deepcopy(r['cohorts'][0]['recipient_state']['outputs'][0]))),
        ('wallet-restart', lambda r: r['wallet_restart']['after']['balance'].update(balance=0)),
        ('daemon-restart', lambda r: r['daemon_restart']['after']['tips'][0].__setitem__(1, '0' * 64)),
        ('restore-history', lambda r: r['restore']['restored']['outputs'].clear()),
        ('later-spend', lambda r: r['restored_spend'].update(txid='0' * 64)),
        ('rejection-state', lambda r: r['controls']['malformed']['after']['tips'][0].__setitem__(1, '0' * 64)),
        ('reorg', lambda r: r['reorg']['winning'].__setitem__(1, '0' * 64)),
        ('final-pool', lambda r: r['final']['pools'][0].append('0' * 64)),
        ('live-binary', lambda r: r['generations'][0].update(sha256='0' * 64)),
        ('child-exit', lambda r: r['generations'][0].update(exit=None)),
        ('shutdown-metrics', lambda r: r['shutdown_sample'].update(memory_peak_bytes=0)),
    ]
    results = []
    for name, mutate in cases:
        target = work / name
        shutil.copytree(baseline, target, ignore=shutil.ignore_patterns('private'))
        path = target / 'run1/public/result.json'
        r = json.loads(path.read_text())
        mutate(r)
        path.write_text(json.dumps(r, indent=2) + '\n')
        rehash(target)
        try:
            verifier.verify(target)
        except (AssertionError, KeyError, ValueError, IndexError) as error:
            results.append({'case': name, 'result': 'REFUSED', 'reason': str(error)})
        else:
            raise AssertionError('contradiction accepted: ' + name)
        shutil.rmtree(target)
    for name, control in (('invalid-accepted', 'altered_transaction'), ('conflict-accepted', 'conflicting_spend'),
                          ('healthy-payment-after-controls-failed', None), ('private-rpc-material', 'private')):
        target = work / name
        shutil.copytree(baseline, target, ignore=shutil.ignore_patterns('private'))
        scenario = json.loads((target / 'run1/public/result.json').read_text())
        path = target / 'run1/public/rpc.jsonl'
        raw = [json.loads(line) for line in path.read_text().splitlines()]
        if control == 'private':
            raw[scenario['restore']['restore_rpc_id']]['response']['result']['seed'] = 'synthetic refusal marker'
            ids = []
        else:
            ids = scenario['controls'][control]['rpc_ids'] if control else [
                scenario['cohorts'][3]['transactions'][0]['admission_rpc_id']]
        for i in ids:
            raw[i]['response']['status'] = 'OK' if control else 'Failed'
        path.write_text(''.join(json.dumps(row) + '\n' for row in raw))
        rehash(target)
        try:
            verifier.verify(target)
        except (AssertionError, KeyError, ValueError, IndexError) as error:
            results.append({'case': name, 'result': 'REFUSED', 'reason': str(error)})
        else:
            raise AssertionError('accepted bad input passed: ' + name)
        shutil.rmtree(target)
    target = work / 'unrelated-recipient-public-key'
    shutil.copytree(baseline, target, ignore=shutil.ignore_patterns('private'))
    result_path = target / 'run1/public/result.json'
    scenario = json.loads(result_path.read_text())
    state = scenario['cohorts'][0]['recipient_state']
    first = state['outputs'][0]
    original_key = first['pubkey']
    first['pubkey'] = '0' * 64
    state['outputs'].sort(key=lambda o: (o['tx_hash'], o['pubkey']))
    raw_path = target / 'run1/public/rpc.jsonl'
    raw = [json.loads(line) for line in raw_path.read_text().splitlines()]
    transfers = raw[state['rpc_ids'][2]]['response']['result']['transfers']
    for row in transfers:
        if row['pubkey'] == original_key:
            row['pubkey'] = '0' * 64
    result_path.write_text(json.dumps(scenario, indent=2) + '\n')
    raw_path.write_text(''.join(json.dumps(row) + '\n' for row in raw))
    rehash(target)
    try:
        verifier.verify(target)
    except AssertionError as error:
        assert 'CARROT output key/amount/height binding' in str(error)
        results.append({'case': 'unrelated-recipient-public-key', 'result': 'REFUSED', 'reason': str(error)})
    else:
        raise AssertionError('wallet public key unrelated to native outputs was accepted')
    shutil.rmtree(target)
    for name, relative, replacement in (
        ('oom-counter', 'run1/final.memory-events', 'low 0\nhigh 0\nmax 0\noom 1\noom_kill 1\n'),
        ('missing-final-peak', 'run1/final.memory', None)):
        target = work / name
        shutil.copytree(baseline, target, ignore=shutil.ignore_patterns('private'))
        path = target / relative
        if replacement is None:
            path.unlink()
        else:
            path.write_text(replacement)
        rehash(target)
        try:
            verifier.verify(target)
        except (AssertionError, KeyError, ValueError, FileNotFoundError) as error:
            results.append({'case': name, 'result': 'REFUSED', 'reason': str(error)})
        else:
            raise AssertionError('bad resources passed: ' + name)
        shutil.rmtree(target)
    result = {'baseline': 'PASS_SOAK_RECEIPT_RECONCILIATION', 'controls': results,
              'scope': 'Distinct contradiction families; overlapping mutations are not credited separately.'}
    (work / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
