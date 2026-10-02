#!/usr/bin/env python3
"""Check load receipts, local executable bytes, and state-claim consistency.

The daemons are stopped before this post-run verifier starts. Its tip checks
therefore reconcile recorded claims; they do not authenticate live RPC tips.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent
BINARIES = {
    'monerod': ('5ba64f2e04e21550575b396b250bcebba01471c4246d74d88e679f06cee86509', 29872608),
    'monero-wallet-rpc': ('cf2ea70c353c5124e86f2bfac46da28fad2993af28636ab28ca7ea9db81678f2', 33545392),
}
REQUIRED = ('--pull=never', '--network=none', '--cap-drop=ALL',
            '--security-opt=no-new-privileges', '--cpus=2', '--memory=4g',
            '--memory-swap=4g', '--pids-limit=256', '--ulimit', 'core=0')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(ok, label):
    if not ok:
        raise AssertionError(label)


def metric(value, label):
    require(math.isfinite(value) and 0 < value < 180, label)


def verify(out, src):
    receipt = json.loads((out / 'receipt.json').read_text())
    require(receipt['schema'] == 'meownero-vanguard-daemon-load/1', 'receipt schema')
    commit = receipt['candidate_commit']
    require(len(commit) == 40 and all(c in '0123456789abcdef' for c in commit), 'commit format')
    subprocess.run(['git', '-C', str(ROOT), 'merge-base', '--is-ancestor', commit, 'HEAD'], check=True)
    expected_sources = {name: sha(ROOT / name) for name in
        ('vanguard/daemon-p2p.py', 'vanguard/run-daemon-p2p.py',
         'vanguard/verify-daemon-p2p.py', 'vanguard/source-lock.json',
         'vanguard/daemon-load.py', 'vanguard/verify-daemon-load.py')}
    require(receipt['source_sha256'] == expected_sources, 'current source hash mismatch')
    for name, expected in expected_sources.items():
        blob = subprocess.check_output(['git', '-C', str(ROOT), 'show', f'{commit}:{name}'])
        require(hashlib.sha256(blob).hexdigest() == expected, f'exact-commit source: {name}')

    manifest = {}
    for line in (out / 'MANIFEST.sha256').read_text().splitlines():
        digest, name = line.split('  ', 1)
        relative = Path(name)
        require(not relative.is_absolute() and '..' not in relative.parts and
                name not in manifest and 'private' not in relative.parts, 'unsafe manifest entry')
        manifest[name] = digest
    actual = {str(p.relative_to(out)): sha(p) for p in out.rglob('*')
              if p.is_file() and 'private' not in p.relative_to(out).parts and
              p.name != 'MANIFEST.sha256'}
    require(actual == manifest, 'manifest mismatch')
    require(json.loads((out / 'source-lock.json').read_text()) ==
            json.loads((ROOT / 'vanguard/source-lock.json').read_text()), 'source lock mismatch')

    require(len(receipt['commands']) == 3, 'two trials required')
    for command in receipt['commands']:
        require(all(flag in command for flag in REQUIRED) and
                receipt['builder_image'] in command, 'container containment')
    require(set(receipt['metrics']) == {'build', 'run1', 'run2'}, 'metric stage set')
    for stage, stage_metric in receipt['metrics'].items():
        require(stage_metric['exit'] == 0 and 0 < stage_metric['wall_seconds'] <
                (1800 if stage == 'build' else 1200), f'{stage} exit/time')
        work = out if stage == 'build' else out / stage
        events = dict(line.split() for line in (work / f'{stage}.memory-events').read_text().splitlines())
        require(events['oom'] == events['oom_kill'] == '0', f'{stage} OOM')
        require(0 < int((work / f'{stage}.memory').read_text()) <= 4 * 1024**3,
                f'{stage} cgroup peak')
        cpu = dict(line.split() for line in (work / f'{stage}.cpu').read_text().splitlines())
        require(int(cpu['usage_usec']) > 0, f'{stage} CPU absent')

    # This inspects executable bytes in the caller's private scratch source,
    # independently of every hash asserted by receipt.json.
    require(set(receipt['binary']) == set(BINARIES), 'binary set')
    for name, (expected_sha, expected_size) in BINARIES.items():
        binary = src / 'monero-fcmp/build/vanguard/bin' / name
        require(binary.is_file() and binary.stat().st_size == expected_size and
                sha(binary) == expected_sha, f'local executable bytes: {name}')
        require(receipt['binary'][name] == {'sha256': expected_sha, 'bytes': expected_size},
                f'binary receipt claim: {name}')

    for number in (1, 2):
        public = out / f'run{number}/public'
        result = json.loads((public / 'result.json').read_text())
        require(result['schema'] == 'vanguard-load/1' and result['result'] == 'PASS_SCENARIO'
                and result['workload_seed'] == 1171 and result['levels'] == [1, 2]
                and result['max_transactions'] == 4 and result['max_blocks'] == 90
                and result['time_limit_seconds'] == 1000 and result['blocks'] <= 90,
                f'run{number} workload bounds')
        baseline = result['baseline']
        require(2.5 <= baseline['wall_seconds'] <= 6 and
                baseline['tips'][0] == baseline['tips'][1] and
                baseline['cpu_seconds'] >= 0, f'run{number} idle baseline')
        all_ids = set()
        for level, count in ((1, 1), (2, 2)):
            row = result['workloads'][level - 1]
            require(row['level'] == level and row['count'] == count and
                    len(row['transactions']) == count and row['tips'][0] == row['tips'][1],
                    f'run{number} level {level}')
            metric(row['block_admission']['wall_seconds'], 'block admission time')
            metric(row['block_convergence']['wall_seconds'], 'block convergence time')
            require(0 < row['confirmed_tps'] < 100 and
                    abs(row['confirmed_tps'] - count / row['duration_seconds']) < 1e-9,
                    'throughput arithmetic')
            for tx in row['transactions']:
                require(tx['txid'] not in all_ids and tx['bytes'] > 1000 and
                        tx['amount'] >= 10**12 and tx['amount'] < 11 * 10**11,
                        'transaction identity/shape')
                all_ids.add(tx['txid'])
                for phase in ('construction', 'origin_admission', 'peer_pool_convergence'):
                    m = tx[phase]
                    metric(m['wall_seconds'], f'{phase} time')
                    require(m['cpu_seconds'] >= 0 and m['memory_peak_bytes'] <= 4 * 1024**3 and
                            all(0 <= rss < 4 * 1024**3 for rss in m['rss_after_bytes'].values()),
                            f'{phase} CPU/RSS')
            require({output['tx_hash'] for output in row['receiver']['outputs']} == all_ids,
                    'receiver confirmation count')
        require(len(all_ids) == 3 and len(result['restore']['original']['outputs']) == 3,
                'three workload outputs')
        require(result['restore']['restore_height'] < min(
                row['block_height'] for row in result['restore']['original']['outputs']),
                'restore height')
        for phase in ('restore', 'rescan'):
            metric(result['restore'][phase]['wall_seconds'], f'wallet {phase} time')
        spend = result['restored_spend']
        require(spend['tips'][0] == spend['tips'][1] and spend['txid'] not in all_ids and
                any(row['key_image'] == spend['key_image'] and row['spent']
                    for row in spend['wallet']['outputs']), 'wallet-visible restored spend')
        for phase in ('construction', 'origin_admission', 'peer_pool_convergence',
                      'block_admission', 'block_convergence'):
            metric(spend[phase]['wall_seconds'], f'restored {phase} time')
        for name in ('invalid_proof', 'duplicate_key_image'):
            control = result['controls'][name]
            require(control['state_unchanged'] and len(control['responses']) == 2 and
                    all(row.get('status') != 'OK' for row in control['responses']),
                    f'{name} refusal')
        require(all(row.get('double_spend') for row in
                    result['controls']['duplicate_key_image']['responses']) and
                result['controls']['duplicate_key_image']['confirmed_txid'] == spend['txid'],
                'duplicate key image classification')
        require(result['controls']['invalid_proof']['source_txid'] == spend['txid'] and
                result['controls']['invalid_proof']['mutation'] == 'last transaction byte xor 01',
                'invalid proof identity')
        require(result['reorg']['recovered_tips'][0] == result['reorg']['recovered_tips'][1] and
                result['reorg']['recovered_tips'][0][1] == result['reorg']['branch1'][-1] and
                result['reorg']['wallet'] == spend['wallet'], 'reorg recovery claim')
        metric(result['reorg']['recovery']['wall_seconds'], 'reorg recovery time')
        require(result['bridge']['connections'] >= 2 and result['bridge']['bytes'] > 0,
                'native bridge activity')
        events = [json.loads(line) for line in (public / 'events.jsonl').read_text().splitlines()]
        names = [event['event'] for event in events]
        for name in ('idle_baseline', 'wallet_restored', 'invalid_proof_refused',
                     'restored_spend_confirmed', 'duplicate_key_image_refused', 'scenario_complete'):
            require(names.count(name) == 1, f'event absent/duplicate: {name}')
        require(names.count('workload_level') == 2 and
                events[names.index('scenario_complete')]['tips'] == result['reorg']['recovered_tips'],
                'event/result tip claim mismatch')
        containment = json.loads((public / 'containment.json').read_text())
        require(containment['interfaces'] == ['lo'] and not containment['routes'] and
                len(containment['listeners_before_shutdown']) >= 7,
                'live network containment claim')
        for name in ('daemon0.log', 'daemon1.log'):
            log = (public / name).read_text()
            require('Failed to verify input FCMP++ signatures' in log,
                    f'{name} invalid-proof verification stage absent')
    print('PASS_LOAD_RECEIPT_STRUCTURE two_runs=2')
    print('PASS_LOCAL_EXECUTABLE_BYTES monerod+wallet_rpc')
    print('UNVERIFIED_LIVE_TIPS post-run tips are reconciled receipt claims')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('out', type=Path)
    parser.add_argument('--src', type=Path, required=True)
    args = parser.parse_args()
    try:
        verify(args.out.resolve(), args.src.resolve())
    except (AssertionError, KeyError, ValueError, OSError, IndexError, TypeError,
            subprocess.CalledProcessError) as error:
        raise SystemExit('FAIL_DAEMON_LOAD: ' + str(error))
