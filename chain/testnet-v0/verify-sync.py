#!/usr/bin/env python3
"""Reconcile late-peer sync and restart receipts independently of sync.py control flow."""
import hashlib
import json
from pathlib import Path
import sys

GENESIS = '20ce111b9a74c7ce79fbaafd053afb71b2f2335e208fa7e993fb46c8c91964d8'
IMAGE = 'sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e'
REWARD = 9000000000000
WRITE_METHODS = {'submit_block', 'generateblocks', 'start_mining', 'stop_mining', 'pop_blocks', 'flush_txpool',
                 'send_raw_transaction', 'relay_tx', 'set_bans', 'set_log_level', 'update', 'out_peers', 'in_peers'}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def main():
    work = Path(sys.argv[1])
    read = lambda name: json.loads((work / name).read_text())
    for line in (work / 'EVIDENCE.sha256').read_text().splitlines():
        sha, name = line.split('  ', 1)
        require(hashlib.sha256((work / name).read_bytes()).hexdigest() == sha, f'changed receipt: {name}')
    require((work / 'launcher.exit').read_text().strip() == '0', 'launcher exit')
    require((work / 'container.exit').read_text().strip() == '0', 'container exit')
    resources = read('resources.json')
    require(resources['daemon_exit_codes'] == {'peer0': 0, 'peer1': 0, 'peer1-restart': 0, 'peer2': 0}, 'daemon exits')
    require(int(resources['memory.max']) == 4 * 1024**3 and int(resources['memory.swap.max']) == 0, 'memory/swap cap')
    require(resources['cpu.max'].strip() == '200000 100000', 'CPU cap')
    events = dict(line.split() for line in resources['memory.events'].splitlines())
    require(int(events['oom']) == int(events['oom_kill']) == 0, 'OOM event')
    cmd = read('container-command.json')
    require(cmd[cmd.index('--network') + 1] == 'none' and not any(x in cmd for x in ['-p', '--publish', '-P']),
            'container network isolation')
    require(IMAGE in cmd, 'builder pin')
    commands = read('daemon-commands.json')
    require(sorted(commands) == ['peer0', 'peer1', 'peer1-restart', 'peer2'], 'four daemon commands required')
    require(commands['peer1-restart'] == commands['peer1'], 'restart must reuse the exact peer1 command')
    exclusive = {'peer0': ['127.0.0.1:28180'], 'peer1': ['127.0.0.1:28080'], 'peer2': ['127.0.0.1:28080', '127.0.0.1:28180']}
    for name, wanted in exclusive.items():
        c = commands[name]
        require(all(x not in c for x in ['--offline', '--regtest', '--testnet', '--stagenet', '--fixed-difficulty']),
                'wrong network or difficulty mode')
        require([c[i + 1] for i, x in enumerate(c) if x == '--add-exclusive-node'] == wanted, f'{name} exclusive peers')
        require(c[c.index('--rpc-bind-ip') + 1] == c[c.index('--p2p-bind-ip') + 1] == '127.0.0.1', 'loopback bindings')
        require(c[c.index('--max-connections-per-ip') + 1] == '3' and '--hide-my-port' in c and '--allow-local-ip' in c,
                'loopback admission flags')
        require(c[c.index('--data-dir') + 1].endswith(f'/data/{name[:5]}'), 'owned data directory')
    methods = read('rpc-methods.json')
    for name in ('peer1', 'peer2'):
        require(not WRITE_METHODS & set(methods[name]), f'{name} received a block-injecting or mining RPC')
    require(WRITE_METHODS & set(methods['peer0']) == {'start_mining', 'stop_mining'}, 'peer0 write RPC beyond native mining')
    headers = read('headers.json')
    final = read('rpc-final.json')
    result = read('result.json')
    readback = read('profile-readback.json')
    late = read('late-peer-sync.json')
    restart = read('restart-catchup.json')
    require(len(headers) == len(final) == 3 and headers[1] == headers[0] and headers[2] == headers[0], 'three identical header sets')
    chain = headers[0]
    require(len(chain) >= 10, 'at least nine mined blocks required')
    require(chain[0]['hash'] == GENESIS and chain[0]['reward'] == 0 and chain[0]['major_version'] == 1, 'genesis')
    work_sum = 0
    for height, h in enumerate(chain):
        require(h['height'] == height and not h['orphan_status'] and h['num_txes'] == 0, 'canonical empty-block sequence')
        work_sum += int(h['wide_difficulty'], 16)
        require(int(h['wide_cumulative_difficulty'], 16) == work_sum, 'cumulative work sum')
        if height:
            require(h['prev_hash'] == chain[height - 1]['hash'], 'header link')
            require(h['reward'] == REWARD and h['major_version'] == 16, 'reward/fork')
    tip = chain[-1]
    emission = sum(h['reward'] for h in chain)
    states = []
    for n in (0, 1, 2):
        require(final[n]['sum']['emission_amount'] == emission and final[n]['sum']['fee_amount'] == 0, 'RPC emission/fee accounting')
        require(final[n]['info']['height'] == len(chain) and final[n]['info']['target'] == 90, 'height/target')
        require(final[n]['tip']['block_header']['hash'] == tip['hash'], 'RPC tip')
        states.append({'height': tip['height'], 'hash': tip['hash'], 'cumulative_work': tip['wide_cumulative_difficulty'],
                       'emission_atomic': emission, 'fees_atomic': 0})
    for n in (0, 1):
        require(readback[str(n)]['info']['height'] == 1 and readback[str(n)]['fork']['earliest_height'] == 1,
                'fresh genesis and fork activation readback')
    require(states == result['peers'] and len({json.dumps(s, sort_keys=True) for s in states}) == 1, 'peer convergence')
    # Late peer: fresh start, target reached through P2P, bytes received on local connections.
    target = late['target_state']
    require(target['height'] >= result['phases']['two_peer_min_top'] and late['peer2_state'] == target, 'late peer state')
    require(chain[target['height']]['hash'] == target['hash'], 'late peer target is on the final chain')
    require(late['first_rpc_info']['height'] <= target['height'], 'late peer first readback')
    require(late['p2p_bytes_received'] > 0 and late['sync_seconds_from_start'] > 0, 'late peer P2P sync measurement')
    require(all(c['ip'] == '127.0.0.1' for c in late['connections']['connections']), 'late peer local connections')
    # Restart: clean exit, stored tip preserved, missed blocks recovered.
    before = restart['tip_before_shutdown']
    require(restart['shutdown_exit_code'] == 0, 'clean shutdown exit')
    require(chain[before['height']]['hash'] == before['hash'], 'pre-shutdown tip is on the final chain')
    require(restart['blocks_missed'] >= result['phases']['offline_blocks'], 'blocks mined while offline')
    require(restart['first_rpc_info_after_restart']['height'] >= before['height'] + 1, 'stored blocks survived restart')
    require(restart['peer1_state_after_catch_up'] == states[1] and restart['catch_up_seconds_from_restart'] > 0, 'restart catch-up')
    peers = read('peers-after.json')
    for n in (0, 1, 2):
        connections = peers[n]['connections']
        require(connections and all(c['ip'] == '127.0.0.1' for c in connections), 'local P2P witnesses')
        require(any(c['recv_count'] > 0 and c['send_count'] > 0 for c in connections), 'P2P traffic')
    usage = read('process-usage.json')
    require(all(k in usage for k in ('peer0', 'peer1', 'peer1-restart', 'peer2')), 'per-process usage samples')
    print(json.dumps({'result': 'PASS_RECEIPT_RECONCILIATION', 'peers': states,
                      'late_peer_sync_s': late['sync_seconds_from_start'], 'restart_catch_up_s': restart['catch_up_seconds_from_restart'],
                      'blocks_missed_while_offline': restart['blocks_missed'], 'memory_peak_bytes': int(resources['memory.peak']),
                      'scope': 'saved receipt consistency; not independent operator or toolchain reproduction'}, indent=2))


if __name__ == '__main__':
    main()
