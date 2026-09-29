#!/usr/bin/env python3
"""Reconcile the native two-daemon CARROT restore/reorg/spend receipt."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent
EVENTS = ('network_containment', 'bridge_ready', 'p2p_ready', 'carrot_received',
          'restored_and_rescanned', 'bridge_partitioned', 'partition_and_branch',
          'bridge_rejoined', 'reorg_wallet_observed', 'restored_reorg_rollback',
          'orphan_spend_refused', 'same_key_image_alternative_built',
          'restored_spend_pool_observed', 'restored_spend_pooled',
          'restored_spend_confirmed',
          'spent_key_image_replay_refused')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(ok, label):
    if not ok:
        raise AssertionError(label)


def verify(out):
    receipt = json.loads((out / 'receipt.json').read_text())
    require(receipt['schema'] == 'meownero-vanguard-daemon-restore/1', 'receipt schema')
    commit = receipt['candidate_commit']
    subprocess.run(['git', '-C', str(ROOT), 'merge-base', '--is-ancestor', commit, 'HEAD'], check=True)
    for source, expected in receipt['source_sha256'].items():
        blob = subprocess.check_output(['git', '-C', str(ROOT), 'show', f'{commit}:{source}'])
        require(hashlib.sha256(blob).hexdigest() == expected,
                f'exact-commit source mismatch: {source}')
    listed = set()
    for line in (out / 'MANIFEST.sha256').read_text().splitlines():
        expected, relative = line.split('  ', 1)
        path = out / relative
        listed.add(path.resolve())
        require(path.is_file() and sha(path) == expected, f'manifest mismatch: {relative}')
        require('private' not in path.parts, 'private data in manifest')
    actual = {path.resolve() for path in out.rglob('*') if path.is_file()
              and 'private' not in path.parts and path.name != 'MANIFEST.sha256'}
    require(actual == listed, 'manifest file set mismatch')
    commands = receipt['commands']
    require(len(commands) in (2, 3), 'expected build and one or two trials')
    for command in commands:
        required = ('--pull=never', '--network=none', '--cap-drop=ALL',
                    '--security-opt=no-new-privileges', '--cpus=2', '--memory=4g',
                    '--memory-swap=4g', '--pids-limit=256', '--ulimit', 'core=0')
        require(all(flag in command for flag in required), 'container containment flag absent')
        require(receipt['builder_image'] in command, 'builder image mismatch')
    require(not any(metric['exit'] for metric in receipt['metrics'].values()), 'nonzero container exit')
    require(set(receipt['binary']) == {'monerod', 'monero-wallet-rpc'}, 'binary pins absent')
    for stage in receipt['metrics']:
        work = out if stage == 'build' else out / stage
        counts = dict(row.split() for row in (work / f'{stage}.memory-events').read_text().splitlines())
        require(not int(counts.get('oom', 0)) and not int(counts.get('oom_kill', 0)),
                'container OOM')

    for number in range(1, len(commands)):
        work = out / f'run{number}' / 'public'
        result = json.loads((work / 'result.json').read_text())
        require(result['result'] == 'PASS' and result['bridge_connections'] >= 2 and
                result['bridge_bytes'] > 0, 'witness result or reconnect')
        initial = result['initial']
        rows = initial['outputs']
        require(initial == result['rescanned'] == result['after_reorg'] and len(rows) == 1 and
                initial['balance']['balance'] == 5 * 10**12 and
                rows[0]['tx_hash'] == result['stable_txid'] and
                rows[0]['key_image'] == result['stable_key_image'] and
                rows[0]['amount'] == 5 * 10**12 and not rows[0]['spent'],
                'restore, rescan or rollback output/balance mismatch')
        require(len(result['old_branch']['outputs']) == 2 and
                result['old_branch']['balance']['balance'] == 7 * 10**12 and
                sorted(row['tx_hash'] for row in result['old_branch']['outputs']) ==
                sorted([result['stable_txid'], result['orphan_txid']]),
                'orphan branch recipient view')
        credit = result['reorg_pool_credit']
        require(credit['outputs'] == rows and
                credit['balance'] == {'balance': 7 * 10**12, 'unlocked_balance': 5 * 10**12},
                'reorg pool credit counted incorrectly')
        require(0 < result['restore_seconds'] < 1100 and
                0 < result['rescan_seconds'] < 1100, 'restore/rescan time absent')
        pooled, confirmed = result['pooled'], result['confirmed']
        require(pooled['key_images'][0] in (0, 2) and pooled['key_images'][1] == 2 and
                all(result['restored_spend_txid'] in entries for entries in pooled['pools']) and
                confirmed['key_images'] == [1, 1] and
                all(result['restored_spend_txid'] not in entries for entries in confirmed['pools']),
                'restored spend pool/chain transition')
        require(result['final_original'] == result['final_restored'] and
                any(row['tx_hash'] == result['stable_txid'] and row['spent'] and
                    row['key_image'] == result['stable_key_image']
                    for row in result['final_original']['outputs']),
                'original wallet missed restored spend')
        for name in ('orphan_rejections', 'replay_rejections'):
            require({row['node'] for row in result[name]} == {0, 1} and
                    all(row['status'] != 'OK' for row in result[name]),
                    f'{name} not refused on both daemons')
        require(result['same_key_image_alternative_txid'] != result['restored_spend_txid'] and
                all(row['double_spend'] for row in result['replay_rejections']),
                'distinct same-key-image double spend not refused')

        events = [json.loads(line) for line in (work / 'events.jsonl').read_text().splitlines()]
        names = [event['event'] for event in events]
        require(all(name in names for name in EVENTS), 'required event absent')
        require(all(names.index(EVENTS[i]) < names.index(EVENTS[i + 1])
                    for i in range(len(EVENTS) - 1)), 'event order')
        def event(name):
            return next(row for row in events if row['event'] == name)
        require(event('restored_and_rescanned')['original'] == initial and
                event('restored_and_rescanned')['restored'] == initial and
                event('restored_and_rescanned')['restore_height'] <
                event('restored_and_rescanned')['output_height'] and
                event('partition_and_branch')['old_wallet'] == result['old_branch'] and
                event('reorg_wallet_observed')['restored_after'] == credit and
                event('reorg_wallet_observed')['original_after'] == credit and
                event('reorg_wallet_observed')['pool_incoming'] ==
                {'original': [[result['orphan_txid'], 2 * 10**12]],
                 'restored': [[result['orphan_txid'], 2 * 10**12]]} and
                event('restored_reorg_rollback')['state'] == result['after_reorg'] and
                event('restored_spend_pooled')['state'] == pooled and
                event('restored_spend_confirmed')['state'] == confirmed and
                event('restored_spend_confirmed')['original'] == result['final_original'] and
                event('orphan_spend_refused')['rejections'] == result['orphan_rejections'] and
                event('same_key_image_alternative_built')['key_image'] ==
                result['stable_key_image'] and
                event('same_key_image_alternative_built')['txid'] ==
                result['same_key_image_alternative_txid'] and
                event('spent_key_image_replay_refused')['txid'] ==
                result['same_key_image_alternative_txid'] and
                event('spent_key_image_replay_refused')['rejections'] == result['replay_rejections'],
                'event/result state mismatch')
        require(event('p2p_ready')['daemon_peer_counts'][0] >= 1 and
                event('p2p_ready')['daemon_peer_counts'][1] >= 1 and
                event('restored_reorg_rollback')['orphan'] in
                event('partition_and_branch')['old_blocks'],
                'native peer or orphan evidence absent')
        for name in ('carrot_received', 'restored_spend_pooled'):
            row = event(name)
            require(row['rct_type'] == 7 and row['output_types'] and
                    all(types == ['carrot_v1'] for types in row['output_types']),
                    f'{name} FCMP++/CARROT receipt')
        wire = [json.loads(line) for line in (work / 'wire.jsonl').read_text().splitlines()]
        require(sum(row['direction'] == 'a_to_b' and row['command'] == 2002 for row in wire) >= 2 and
                any(row['direction'] == 'b_to_a' for row in wire) and
                any(row['command'] in (2001, 2008) for row in wire),
                'native transaction/block P2P direction absent')
        live = json.loads((work / 'network-live.json').read_text())
        containment = json.loads((work / 'containment.json').read_text())
        require(live['interfaces'] == containment['interfaces'] == ['lo'] and
                not live['routes'] and not containment['routes'] and
                live['socket_mode'] == '0o600' and len(live['listeners']) >= 5 and
                len(containment['listeners_before_shutdown']) >= 10,
                'live network containment')
        exits = [row for row in events if row['event'] == 'process_exit']
        require(len(exits) == 7 and not any(row['returncode'] for row in exits),
                'owned process exit status')
    print('PASS_DAEMON_RESTORE_RECEIPT_RECONCILIATION')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('out', type=Path)
    verify(parser.parse_args().out.resolve())
