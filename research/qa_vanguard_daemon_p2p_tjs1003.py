#!/usr/bin/env python3
"""Independent state assertions for exact TJS-996 daemon P2P receipts."""

import argparse
import hashlib
import json
from pathlib import Path
import struct


HEADER = struct.Struct('<QQBIiII')
SIGNATURE = 0x0101010101012101
CODE = '6ba799b909d005be57232e4566ee3617a63574ac'


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def frame(path, command):
    packet = path.read_bytes()
    signature, size, _, actual, _, _, version = HEADER.unpack(packet[:HEADER.size])
    assert signature == SIGNATURE and version == 1 and actual == command
    assert size == len(packet) - HEADER.size
    return packet


def check(root):
    receipt = json.loads((root / 'receipt.json').read_text())
    assert receipt['candidate_commit'] == CODE
    trials = sorted(path for path in root.glob('run[12]') if path.is_dir())
    assert trials
    summary = []
    for trial in trials:
        public = trial / 'public'
        result = json.loads((public / 'result.json').read_text())
        events = rows(public / 'events.jsonl')
        event = {row['event']: row for row in events if row['event'] != 'frame_injected'}
        txid = result['txid']
        pooled = [[txid], [txid]]
        funded = event['funded_and_synced']['tip']
        relayed = event['fcmp_transaction_relayed']
        tx_after = event['transaction_adversarial_unchanged']['state']
        confirmed = event['confirmed_on_both']['state']
        block_after = event['block_adversarial_unchanged']['state']
        rolled = event['reorg_key_image_rollback']['state']
        partition = event['partition_and_branch']
        assert relayed['txid'] == txid and relayed['key_image'] == result['key_image']
        assert relayed['pools'] == pooled
        assert tx_after == {'tips': [funded, funded], 'pools': pooled, 'key_images': [2, 2]}
        assert confirmed == result['confirmed'] == block_after
        assert confirmed['key_images'] == [1, 1] and confirmed['pools'] == [[], []]
        assert confirmed['tips'][0] == confirmed['tips'][1]
        assert partition['old_tip'] == confirmed['tips'][0]
        assert partition['peer_tip'][0] > partition['old_tip'][0]
        assert rolled == result['rolled_back']
        assert rolled['key_images'] == [2, 2] and rolled['pools'] == pooled
        assert rolled['tips'][0] == rolled['tips'][1] == partition['peer_tip']
        assert event['healthy_subsequent_exchange']['tip'] == result['final_tip']
        assert result['final_tip'][0] == rolled['tips'][0][0] + 1
        assert event['reorg_key_image_rollback']['reconnects'] > partition.get('connections', 0)

        injections = {row['name']: row for row in events if row['event'] == 'frame_injected'}
        expected = {'duplicate-transaction': 2002, 'malformed-transaction': 2002,
                    'duplicate-block': 2008, 'malformed-header': 2008, 'malformed-block': 2008}
        assert set(injections) == set(expected)
        packets = {}
        for name, command in expected.items():
            packet = frame(public / 'frames' / (name + '.bin'), command)
            assert hashlib.sha256(packet).hexdigest() == injections[name]['sha256']
            packets[name] = packet
        assert hashlib.sha256(packets['duplicate-transaction']).hexdigest() == relayed['packet_sha256']
        assert hashlib.sha256(packets['duplicate-block']).hexdigest() == event['native_header_block_delivered']['packet_sha256']
        for bad, good in [('malformed-transaction', 'duplicate-transaction'),
                          ('malformed-header', 'duplicate-block'), ('malformed-block', 'duplicate-block')]:
            assert len(packets[bad]) == len(packets[good]) and packets[bad] != packets[good]
        wire = rows(public / 'wire.jsonl')
        assert {(row['direction'], row['command']) for row in wire} >= {
            ('a_to_b', 2002), ('a_to_b', 2008), ('b_to_a', 2006), ('a_to_b', 2007)}
        assert all(any(row['sha256'] == injected['sha256'] and row['direction'] == 'a_to_b'
                       for row in wire) for injected in injections.values())
        log = (public / 'daemon1.log').read_text()
        assert log.count('Failed to parse transaction from blob') >= 1
        assert log.count('Failed to parse block from blob') >= 2
        started = [row for row in events if row['event'] == 'process_started']
        assert {row['name'] for row in started} == {'daemon0', 'daemon1', 'wallet'}
        daemons = [row for row in started if row['name'].startswith('daemon')]
        assert len({row['pid'] for row in daemons}) == 2
        assert all(Path(row['command'][0]).name == 'monerod' for row in daemons)
        assert result['bridge_connections'] >= 2
        summary.append({'trial': trial.name, 'txid': txid, 'confirmed_height': confirmed['tips'][0][0],
                        'rolled_height': rolled['tips'][0][0], 'final_height': result['final_tip'][0],
                        'rollback_key_images': rolled['key_images'], 'rollback_pools': rolled['pools'],
                        'bridge_connections': result['bridge_connections']})
    print(json.dumps({'result': 'PASS_TJS1003_QA_ORACLE', 'candidate_commit': CODE,
                      'trials': summary}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle', type=Path)
    check(parser.parse_args().bundle.resolve())
