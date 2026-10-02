#!/usr/bin/env python3
"""Independent semantic comparison of TJS-1010 and TJS-1032 public receipts."""
import collections
import hashlib
import json
from pathlib import Path
import sys

FILES = ('result.json', 'events.jsonl', 'wire.jsonl',
         'containment.json', 'network-live.json')
COIN = 10**12


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summarize(root, run):
    public = root / run / 'public'
    result = json.loads((public / 'result.json').read_text())
    events = [json.loads(row) for row in (public / 'events.jsonl').read_text().splitlines()]
    wire = [json.loads(row) for row in (public / 'wire.jsonl').read_text().splitlines()]
    live = json.loads((public / 'network-live.json').read_text())
    containment = json.loads((public / 'containment.json').read_text())
    named = {event['event']: event for event in events}
    original = result['initial']
    stable = original['outputs'][0]
    assert result['result'] == 'PASS'
    assert result['initial'] == result['rescanned'] == result['after_reorg']
    assert len(original['outputs']) == 1 and stable['amount'] == 5 * COIN
    assert stable['tx_hash'] == result['stable_txid']
    assert stable['key_image'] == result['stable_key_image'] and not stable['spent']
    assert original['balance'] == {'balance': 5 * COIN, 'unlocked_balance': 5 * COIN}
    assert len(result['old_branch']['outputs']) == 2
    assert result['old_branch']['balance']['balance'] == 7 * COIN
    assert result['final_original'] == result['final_restored']
    assert any(row['tx_hash'] == stable['tx_hash'] and row['key_image'] == stable['key_image']
               and row['spent'] for row in result['final_original']['outputs'])
    for name, state in (('original', result['original_reorg_pool_credit']),
                        ('restored', result['reorg_pool_credit'])):
        pending = named['reorg_wallet_observed']['pool_incoming'][name]
        assert pending in ([], [[result['orphan_txid'], 2 * COIN]])
        assert state['outputs'] == original['outputs']
        assert state['balance'] == {'balance': 5 * COIN + sum(row[1] for row in pending),
                                    'unlocked_balance': 5 * COIN}
    assert result['pooled']['tips'][0] == result['pooled']['tips'][1]
    assert result['confirmed']['tips'][0] == result['confirmed']['tips'][1]
    assert result['final_tip'] == result['confirmed']['tips'][0]
    assert result['pooled']['key_images'][0] in (0, 2)
    assert result['pooled']['key_images'][1] == 2
    assert all(result['restored_spend_txid'] in pool for pool in result['pooled']['pools'])
    assert result['confirmed']['key_images'] == [1, 1]
    assert all(result['restored_spend_txid'] not in pool for pool in result['confirmed']['pools'])
    assert result['same_key_image_alternative_txid'] != result['restored_spend_txid']
    assert all(row['status'] != 'OK' and row['invalid_input']
               for row in result['orphan_rejections'])
    assert all(row['status'] != 'OK' and row['double_spend'] and row['invalid_input']
               for row in result['replay_rejections'])
    assert {row['node'] for row in result['orphan_rejections']} == {0, 1}
    assert {row['node'] for row in result['replay_rejections']} == {0, 1}
    for name in ('carrot_received', 'restored_spend_pooled'):
        assert named[name]['rct_type'] == 7
        assert named[name]['output_types']
        assert all(target == ['carrot_v1'] for target in named[name]['output_types'])
    assert named['restored_and_rescanned']['restore_height'] < stable['block_height']
    assert named['partition_and_branch']['old_tip'] != named['partition_and_branch']['competing_tip']
    assert named['restored_reorg_rollback']['orphan'] in named['partition_and_branch']['old_blocks']
    assert len([row for row in events if row['event'] == 'process_exit']) == 7
    assert not any(row['returncode'] for row in events if row['event'] == 'process_exit')
    histogram = collections.Counter((row['direction'], row['command']) for row in wire)
    assert histogram['a_to_b', 2002] >= 2
    assert any(direction == 'b_to_a' for direction, _ in histogram)
    assert any(command in (2001, 2008) for _, command in histogram)
    assert live['interfaces'] == containment['interfaces'] == ['lo']
    assert live['routes'] == containment['routes'] == []
    assert live['socket_mode'] == '0o600'
    assert len(live['listeners']) >= 5 and len(containment['listeners_before_shutdown']) >= 10
    return {
        'sha256': {name: digest(public / name) for name in FILES},
        'event_sequence': [row['event'] for row in events],
        'wire_histogram': {f'{direction}:{command}': count
                           for (direction, command), count in sorted(histogram.items())},
        'wire_count': len(wire),
        'stable_txid': result['stable_txid'],
        'stable_key_image': result['stable_key_image'],
        'orphan_txid': result['orphan_txid'],
        'restored_spend_txid': result['restored_spend_txid'],
        'alternate_spend_txid': result['same_key_image_alternative_txid'],
        'original_reorg_pool': named['reorg_wallet_observed']['pool_incoming']['original'],
        'restored_reorg_pool': named['reorg_wallet_observed']['pool_incoming']['restored'],
        'pooled_key_image_status': result['pooled']['key_images'],
        'confirmed_key_image_status': result['confirmed']['key_images'],
        'pooled_height': result['pooled']['tips'][0][0],
        'confirmed_height': result['confirmed']['tips'][0][0],
        'orphan_rejections': result['orphan_rejections'],
        'replay_rejections': result['replay_rejections'],
        'network': {'interfaces': live['interfaces'], 'routes': live['routes'],
                    'socket_mode': live['socket_mode'], 'live_listeners': len(live['listeners']),
                    'shutdown_listeners': len(containment['listeners_before_shutdown'])},
    }


def main():
    writer, qa, destination = map(Path, sys.argv[1:4])
    bundles = {'writer': writer, 'qa': qa}
    receipts = {label: json.loads((root / 'receipt.json').read_text())
                for label, root in bundles.items()}
    assert receipts['writer']['candidate_commit'] == '9057e7bc220b5b690e978b69f3dcb583402807ce'
    assert receipts['qa']['candidate_commit'] == '40be047b6ed89745c94d22b3a36537b138bc91ee'
    assert receipts['writer']['source_sha256'] == receipts['qa']['source_sha256']
    assert receipts['writer']['binary'] == receipts['qa']['binary']
    assert (writer / 'source-lock.json').read_bytes() == (qa / 'source-lock.json').read_bytes()
    required_flags = ('--pull=never', '--network=none', '--cap-drop=ALL',
                      '--security-opt=no-new-privileges', '--cpus=2', '--memory=4g',
                      '--memory-swap=4g', '--pids-limit=256', '--ulimit', 'core=0')
    for label, root in bundles.items():
        receipt = receipts[label]
        assert len(receipt['commands']) == 3
        assert all(all(flag in command for flag in required_flags)
                   for command in receipt['commands'])
        assert all(receipt['builder_image'] in command for command in receipt['commands'])
        assert set(receipt['metrics']) == {'build', 'run1', 'run2'}
        assert all(stage['exit'] == 0 for stage in receipt['metrics'].values())
        for stage in receipt['metrics']:
            path = root if stage == 'build' else root / stage
            counts = dict(row.split() for row in (path / f'{stage}.memory-events').read_text().splitlines())
            assert int(counts['oom']) == int(counts['oom_kill']) == 0
    runs = {f'{label}_{run}': summarize(root, run)
            for label, root in bundles.items() for run in ('run1', 'run2')}
    sequences = [row['event_sequence'] for row in runs.values()]
    result = {
        'writer_candidate': receipts['writer']['candidate_commit'],
        'qa_checkout': receipts['qa']['candidate_commit'],
        'source_hashes_equal': True,
        'binary_receipts_equal': True,
        'binary': receipts['qa']['binary'],
        'source_lock_equal': True,
        'source_lock_sha256': digest(writer / 'source-lock.json'),
        'event_sequences_equal': all(row == sequences[0] for row in sequences),
        'runs': runs,
        'comparison': 'All four runs satisfy the same semantic assertions. Transaction IDs, frame hashes, wire counts, and timing are intentionally variable.',
    }
    destination.write_text(json.dumps(result, indent=2) + '\n')
    print('PASS_TJS1032_FOUR_RUN_SEMANTIC_COMPARISON')


if __name__ == '__main__':
    main()
