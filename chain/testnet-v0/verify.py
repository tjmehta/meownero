#!/usr/bin/env python3
"""Reconcile retained headers/RPC/process receipts independently of launch control flow."""
import hashlib
import json
from pathlib import Path
import sys


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
    require(resources['daemon_exit_codes'] == {'0': 0, '1': 0}, 'daemon exits')
    require(int(resources['memory.max']) == 4 * 1024**3 and int(resources['memory.swap.max']) == 0,
            'memory/swap cap')
    require(resources['cpu.max'].strip() == '200000 100000', 'CPU cap')
    events = dict(line.split() for line in resources['memory.events'].splitlines())
    require(int(events['oom']) == int(events['oom_kill']) == 0, 'OOM event')
    cmd = read('container-command.json')
    require(cmd[cmd.index('--network')+1] == 'none' and not any(x in cmd for x in ['-p', '--publish', '-P']),
            'container network isolation')
    require('sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e' in cmd, 'builder pin')
    commands = read('daemon-commands.json')
    require(len(commands) == 2, 'two daemon commands required')
    for n in (0, 1):
        cmd = commands[f'peer{n}']
        require(all(x not in cmd for x in ['--offline', '--regtest', '--testnet', '--stagenet', '--fixed-difficulty']),
                'wrong network or difficulty mode')
        require(cmd[cmd.index('--add-exclusive-node')+1] == f'127.0.0.1:{28080+(1-n)*100}', 'exclusive peer')
        require(cmd[cmd.index('--rpc-bind-ip')+1] == cmd[cmd.index('--p2p-bind-ip')+1] == '127.0.0.1',
                'loopback bindings')
    headers = read('headers.json')
    final = read('rpc-final.json')
    result = read('result.json')
    readback = read('profile-readback.json')
    states = []
    for n in (0, 1):
        chain = headers[n]
        require(len(chain) >= 4, 'at least three mined blocks required')
        require(chain[0]['hash'] == '20ce111b9a74c7ce79fbaafd053afb71b2f2335e208fa7e993fb46c8c91964d8',
                'genesis hash')
        require(chain[0]['reward'] == 0 and chain[0]['major_version'] == 1, 'genesis reward/version')
        work_sum = 0
        for height, h in enumerate(chain):
            require(h['height'] == height and not h['orphan_status'], 'canonical header sequence')
            require(h['num_txes'] == 0, 'empty-block scope')
            work_sum += int(h['wide_difficulty'], 16)
            require(int(h['wide_cumulative_difficulty'], 16) == work_sum, 'cumulative work sum')
            if height:
                require(h['prev_hash'] == chain[height-1]['hash'], 'header link')
                require(h['reward'] == 9000000000000 and h['major_version'] == 16, 'reward/fork')
        tip = chain[-1]
        emission = sum(h['reward'] for h in chain)
        require(final[n]['sum']['emission_amount'] == emission and final[n]['sum']['fee_amount'] == 0,
                'RPC emission/fee accounting')
        require(final[n]['info']['height'] == len(chain) and final[n]['info']['target'] == 90, 'height/target')
        require(final[n]['tip']['block_header']['hash'] == tip['hash'], 'RPC tip')
        require(readback[str(n)]['info']['height'] == 1 and readback[str(n)]['fork']['earliest_height'] == 1,
                'fresh genesis and fork activation readback')
        states.append({'height': tip['height'], 'hash': tip['hash'], 'cumulative_work': tip['wide_cumulative_difficulty'],
                       'emission_atomic': emission, 'fees_atomic': 0})
    require(states[0] == states[1] and states == result['peers'], 'peer convergence')
    peers = read('peers-after.json')
    for n in (0, 1):
        connections = peers[n]['connections']
        require(connections and all(c['ip'] == '127.0.0.1' for c in connections), 'local P2P witnesses')
        require(any(c['recv_count'] > 0 and c['send_count'] > 0 for c in connections), 'P2P traffic')
    print(json.dumps({'result': 'PASS_RECEIPT_RECONCILIATION', 'peers': states,
                      'memory_peak_bytes': int(resources['memory.peak']),
                      'scope': 'saved receipt consistency; not independent operator or toolchain reproduction'}, indent=2))


if __name__ == '__main__':
    main()
