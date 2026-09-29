#!/usr/bin/env python3
"""Reconcile TJS-996 native-daemon P2P receipts with the exact candidate source."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent
REQUIRED_EVENTS = ('network_containment', 'bridge_ready', 'p2p_ready',
    'funded_and_synced', 'fcmp_transaction_relayed',
    'transaction_adversarial_unchanged', 'confirmed_on_both',
    'native_header_block_delivered', 'block_adversarial_unchanged', 'partition_and_branch',
    'bridge_rejoined', 'reorg_key_image_rollback', 'healthy_subsequent_exchange')
INJECTIONS = ('duplicate-transaction', 'malformed-transaction',
              'duplicate-block', 'malformed-header', 'malformed-block')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def verify(out):
    receipt = json.loads((out / 'receipt.json').read_text())
    if receipt['schema'] != 'meownero-vanguard-daemon-p2p/1':
        raise AssertionError('receipt schema')
    commit = receipt['candidate_commit']
    subprocess.run(['git', '-C', str(ROOT), 'merge-base', '--is-ancestor', commit, 'HEAD'], check=True)
    for source, expected in receipt['source_sha256'].items():
        blob = subprocess.check_output(['git', '-C', str(ROOT), 'show', f'{commit}:{source}'])
        if sha(blob) != expected:
            raise AssertionError(f'exact-commit source mismatch: {source}')
    listed = set()
    for line in (out / 'MANIFEST.sha256').read_text().splitlines():
        expected, relative = line.split('  ', 1)
        path = out / relative
        listed.add(path.resolve())
        if not path.is_file() or sha(path.read_bytes()) != expected:
            raise AssertionError(f'manifest mismatch: {relative}')
        if 'private' in path.parts:
            raise AssertionError('private data in manifest')
    actual = {path.resolve() for path in out.rglob('*') if path.is_file()
              and 'private' not in path.parts and path.name != 'MANIFEST.sha256'}
    if actual != listed:
        raise AssertionError('manifest file set mismatch')
    commands = receipt['commands']
    if len(commands) not in (2, 3):
        raise AssertionError('expected build and one or two daemon trials')
    for command in commands:
        required = ('--pull=never', '--network=none', '--cap-drop=ALL',
                    '--security-opt=no-new-privileges', '--cpus=2', '--memory=4g',
                    '--memory-swap=4g', '--pids-limit=256', '--ulimit', 'core=0')
        if not all(flag in command for flag in required):
            raise AssertionError('container containment flag absent')
        if receipt['builder_image'] not in command:
            raise AssertionError('builder image mismatch')
    if any(metric['exit'] for metric in receipt['metrics'].values()):
        raise AssertionError('nonzero container exit')
    for stage in receipt['metrics']:
        events_memory = dict(line.split() for line in (out if stage == 'build' else out / stage).joinpath(
            f'{stage}.memory-events').read_text().splitlines())
        if int(events_memory.get('oom', '0')) or int(events_memory.get('oom_kill', '0')):
            raise AssertionError('memory cap exceeded')
    for number in range(1, len(commands)):
        work = out / f'run{number}'
        result = json.loads((work / 'public/result.json').read_text())
        if result['result'] != 'PASS' or result['bridge_connections'] < 2 or result['bridge_bytes'] <= 0:
            raise AssertionError('witness result or reconnect')
        if result['confirmed']['key_images'] != [1, 1] or 1 in result['rolled_back']['key_images']:
            raise AssertionError('key image chain-state transition')
        if result['confirmed']['tips'][0] != result['confirmed']['tips'][1] or \
           result['rolled_back']['tips'][0] != result['rolled_back']['tips'][1]:
            raise AssertionError('cross-daemon convergence')
        events = [json.loads(line) for line in (work / 'public/events.jsonl').read_text().splitlines()]
        names = [event['event'] for event in events]
        if not all(name in names for name in REQUIRED_EVENTS):
            raise AssertionError('required event absent')
        ready = next(event for event in events if event['event'] == 'p2p_ready')
        if ready['daemon_peer_counts'][0] < 1 or ready['daemon_peer_counts'][1] < 1:
            raise AssertionError('native daemon handshake absent')
        if not all(names.index(REQUIRED_EVENTS[i]) < names.index(REQUIRED_EVENTS[i + 1])
                   for i in range(len(REQUIRED_EVENTS) - 1)):
            raise AssertionError('event order')
        injected = {event['name'] for event in events if event['event'] == 'frame_injected'}
        if injected != set(INJECTIONS):
            raise AssertionError('native P2P adversarial case missing')
        for name in INJECTIONS:
            packet = (work / 'public/frames' / f'{name}.bin').read_bytes()
            event = next(e for e in events if e['event'] == 'frame_injected' and e['name'] == name)
            if sha(packet) != event['sha256'] or event['direction'] != 'a_to_b':
                raise AssertionError(f'injected frame receipt mismatch: {name}')
        wire = [json.loads(line) for line in (work / 'public/wire.jsonl').read_text().splitlines()]
        crossed = {row['sha256'] for row in wire if row['direction'] == 'a_to_b'}
        if any(event['sha256'] not in crossed for event in events if event['event'] == 'frame_injected'):
            raise AssertionError('injected frame did not cross Unix transport')
        if not any(row['direction'] == 'a_to_b' and row['command'] == 2002 for row in wire) or \
           not any(row['direction'] == 'a_to_b' and row['command'] in (2001, 2008) for row in wire) or \
           not any(row['direction'] == 'b_to_a' for row in wire):
            raise AssertionError('native P2P command/direction evidence')
        containment = json.loads((work / 'public/containment.json').read_text())
        live = json.loads((work / 'public/network-live.json').read_text())
        if live['interfaces'] != ['lo'] or live['routes'] or live['socket_mode'] != '0o600' or \
           len(live['listeners']) < 5:
            raise AssertionError('live network/socket containment')
        if containment['interfaces'] != ['lo'] or containment['routes']:
            raise AssertionError('outside network route or interface')
        if len(containment['listeners_before_shutdown']) < 6:
            raise AssertionError('live daemon/wallet listeners not captured')
        peer_log = (work / 'public/daemon1.log').read_text()
        if 'Failed to parse transaction from blob' not in peer_log or \
           peer_log.count('Failed to parse block from blob') < 2:
            raise AssertionError('daemon parser rejection logs absent')
        exits = [event for event in events if event['event'] == 'process_exit']
        if len(exits) != 3 or any(event['returncode'] for event in exits):
            raise AssertionError('owned process exit status')
        tcp = containment['tcp'].splitlines()[1:] + containment['tcp6'].splitlines()[1:]
        if any(row.split()[3] == '0A' and not row.split()[1].startswith(('0100007F:', '00000000000000000000000001000000:'))
               for row in tcp):
            raise AssertionError('non-loopback TCP listener')
    print('PASS_DAEMON_P2P_RECEIPT_RECONCILIATION')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('out', type=Path)
    verify(parser.parse_args().out.resolve())
