#!/usr/bin/env python3
"""Reconcile pool-restart receipts independently of pool-restart.py control flow."""
import hashlib
import json
from pathlib import Path
import sys

GENESIS = '20ce111b9a74c7ce79fbaafd053afb71b2f2335e208fa7e993fb46c8c91964d8'
IMAGE = 'sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e'
POOL_SHA = 'bbc3240607bf40bd3db7e13f011ccf9eda431dddd751918a3ebf4e3aaf129fad'
ADDRESS = 'M9Lds8CcBgCJbqSiUvYfS3BfhEdxZmv8pDt25oW1LzxrZv9Uq6ARagiFViMGUE3gJk5VPWingCXVf1p2tyAy6SUeSLMMvfc'
REWARD = 9000000000000
WRITE_METHODS = {'submit_block', 'generateblocks', 'start_mining', 'stop_mining', 'pop_blocks', 'flush_txpool',
                 'send_raw_transaction', 'relay_tx', 'set_bans', 'set_log_level', 'update', 'out_peers', 'in_peers'}
PROCESSES = ['peer0', 'peer1', 'pool', 'pool-restart']


def require(ok, message):
    if not ok:
        raise ValueError(message)


def daemon_command(n):
    """The accepted recipe v1 command; peer 1 replaces --no-zmq with a loopback ZMQ publisher for the pool."""
    zmq = (['--no-zmq'] if n == 0 else
           ['--zmq-rpc-bind-ip', '127.0.0.1', '--zmq-rpc-bind-port', '28182', '--zmq-pub', 'tcp://127.0.0.1:28183'])
    return ['/binary/monerod', '--config-file', f'/work/peer{n}.conf', '--data-dir', f'/work/data/peer{n}',
            '--non-interactive', '--no-igd', '--disable-dns-checkpoints', '--check-updates', 'disabled',
            '--max-concurrency', '1', '--allow-local-ip', '--hide-my-port',
            '--add-exclusive-node', f'127.0.0.1:{28080 + (1 - n) * 100}',
            '--p2p-bind-ip', '127.0.0.1', '--p2p-bind-port', str(28080 + n * 100),
            '--rpc-bind-ip', '127.0.0.1', '--rpc-bind-port', str(28081 + n * 100),
            '--rpc-ssl', 'disabled', *zmq, '--log-level', '1', '--log-file', f'/work/peer{n}.log']


def main():
    work = Path(sys.argv[1])
    read = lambda name: json.loads((work / name).read_text())
    for line in (work / 'EVIDENCE.sha256').read_text().splitlines():
        sha, name = line.split('  ', 1)
        require(Path(name).name == name, 'public manifest must contain only top-level files')
        require(hashlib.sha256((work / name).read_bytes()).hexdigest() == sha, f'changed receipt: {name}')
    require((work / 'launcher.exit').read_text().strip() == '0', 'launcher exit')
    require((work / 'container.exit').read_text().strip() == '0', 'container exit')
    resources = read('resources.json')
    require(sorted(resources['daemon_exit_codes']) == PROCESSES and not any(resources['daemon_exit_codes'].values()), 'owned exits')
    require(int(resources['memory.max']) == 4 * 1024**3 and int(resources['memory.swap.max']) == 0, 'memory/swap cap')
    require(resources['cpu.max'].strip() == '200000 100000', 'CPU cap')
    events = dict(line.split() for line in resources['memory.events'].splitlines())
    require(int(events['oom']) == int(events['oom_kill']) == 0, 'OOM event')
    cmd = read('container-command.json')
    require(cmd[cmd.index('--network') + 1] == 'none' and not any(x in cmd for x in ['-p', '--publish', '-P', '--privileged']),
            'container network isolation')
    require(IMAGE in cmd and '--read-only' in cmd and '--cap-drop=ALL' in cmd, 'builder pin and container hardening')
    binaries = dict(line.split('  ', 1)[::-1] for line in (work / 'BINARY.sha256').read_text().splitlines())
    require(any(p.endswith('/p2pool') and sha == POOL_SHA for p, sha in binaries.items()), 'pool binary pin')
    commands = read('process-commands.json')
    require(sorted(commands) == PROCESSES, 'four owned process commands required')
    require(commands['peer0'] == daemon_command(0) and commands['peer1'] == daemon_command(1), 'daemons must run the exact recipe commands')
    require(commands['pool-restart'] == commands['pool'], 'restart must reuse the exact pool command')
    p = commands['pool']
    require(p[0] == '/pool/p2pool' and p[p.index('--wallet') + 1] == ADDRESS, 'pool pays the public fixture address')
    require(p[p.index('--host') + 1] == '127.0.0.1' and p[p.index('--rpc-port') + 1] == '28181'
            and p[p.index('--zmq-port') + 1] == '28183', 'pool bound to peer 1 RPC and ZMQ on loopback')
    require(p[p.index('--stratum') + 1].startswith('127.0.0.1:') and p[p.index('--p2p') + 1].startswith('127.0.0.1:')
            and '--no-dns' in p and '--light-mode' in p and '--full-validation' in p, 'pool loopback listeners and mode')
    require(not any(x in p for x in ['--start-mining', '--mini', '--nano', '--merge-mine', '--socks5', '--rpc-login']),
            'pool must not mine, merge-mine, proxy or carry credentials')
    require(p[p.index('--data-dir') + 1] == '/work/data/pool', 'owned pool data directory')
    methods = read('rpc-methods.json')
    require(not WRITE_METHODS & set(methods['peer1']), 'peer1 received a block-injecting or mining RPC')
    require(WRITE_METHODS & set(methods['peer0']) == {'start_mining', 'stop_mining'}, 'peer0 write RPC beyond native mining')
    pool_log = (work / 'pool.log').read_text(errors='replace')
    require('BLOCK FOUND' not in pool_log and 'submit_block' not in pool_log, 'the pool submitted or found a block')
    headers = read('headers.json')
    final = read('rpc-final.json')
    result = read('result.json')
    readback = read('profile-readback.json')
    witness = read('pool-restart.json')
    require(result['result'] == 'PASS' and result['pool_sha256'] == POOL_SHA, 'journey did not pass on the pinned pool')
    require(len(headers) == len(final) == 2 and headers[1] == headers[0], 'two identical header sets')
    chain = headers[0]
    require(len(chain) - 1 >= sum(result['phases'].values()) >= 7, 'at least seven mined blocks required')
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
    for n in (0, 1):
        require(final[n]['sum']['emission_amount'] == emission and final[n]['sum']['fee_amount'] == 0, 'RPC emission/fee accounting')
        require(final[n]['info']['height'] == len(chain) and final[n]['info']['target'] == 90, 'height/target')
        require(final[n]['tip']['block_header']['hash'] == tip['hash'], 'RPC tip')
        require(readback[str(n)]['info']['height'] == 1 and readback[str(n)]['fork']['earliest_height'] == 1,
                'fresh genesis and fork activation readback')
        states.append({'height': tip['height'], 'hash': tip['hash'], 'cumulative_work': tip['wide_cumulative_difficulty'],
                       'emission_atomic': emission, 'fees_atomic': 0})
    require(states == result['peers'] and states[0] == states[1], 'peer convergence')

    def on_chain(t):
        require(t['height'] < len(chain) and chain[t['height']]['hash'] == t['hash'], 'tip is not on the final chain')

    def bound(snapshot, t, label):
        """A stratum job and pool API snapshot must build on exactly tip t."""
        job, api = snapshot['job'], snapshot['api']
        require(job['height'] == t['height'] + 1 and job['prev_hash'] == t['hash'], f'{label}: job is not on the common tip')
        require(job['algo'] == 'rx/0' and job['major_version'] == 16 and job['blob_bytes'] >= 76, f'{label}: job algorithm/fork/blob')
        require(api['network']['hash'] == t['hash'] and api['network']['height'] == t['height']
                and api['network']['difficulty'] == chain[t['height']]['difficulty'], f'{label}: pool API tip')
        require(api['pool']['pool_statistics']['totalBlocksFound'] == 0, f'{label}: pool found blocks')

    phases = result['phases']
    attach, live, stop_tip, down, restart = (witness['tip_at_attach'], witness['tip_after_live'], witness['tip_at_stop'],
                                             witness['tip_mined_while_down'], witness['state_after_restart'])
    for t in (attach, live, stop_tip, down):
        on_chain(t)
    require(attach['height'] >= phases['initial_blocks'], 'chain existed before the pool attached')
    bound(witness['attach'], attach, 'attach')
    require(live['height'] - attach['height'] >= phases['live_blocks'] == witness['live_blocks'], 'live blocks while the pool ran')
    bound(witness['live'], live, 'live')
    require(stop_tip == live and witness['pool_exit_code'] == 0, 'pool stopped cleanly at the live tip')
    require(down['height'] - stop_tip['height'] >= phases['down_blocks'] == witness['blocks_missed'], 'blocks mined while the pool was down')
    bound(witness['resumed'], down, 'resumed')
    require(restart == states[1] == down, 'restart readback equals the final common tip')
    require(witness['final_api']['network']['hash'] == tip['hash'], 'final pool view')
    seeds = {witness[k]['job']['seed_hash'] for k in ('attach', 'live', 'resumed')}
    require(len(seeds) == 1, 'RandomX seed epoch changed within the witness')
    require(witness['pool_started_elapsed_s'] < witness['attach']['elapsed_s'] < witness['live']['elapsed_s']
            < witness['stopped_elapsed_s'] < witness['restarted_elapsed_s'] < witness['resumed']['elapsed_s'], 'pool restart timeline')
    require(witness['resume_seconds_from_restart'] > 0 and witness['attach_seconds_from_start'] > 0, 'attach/resume durations')
    require(all(c['ip'] == '127.0.0.1' for c in witness['connections']['connections']), 'peer 1 local connections at restart')
    peers = read('peers-after.json')
    for n in (0, 1):
        connections = peers[n]['connections']
        require(connections and all(c['ip'] == '127.0.0.1' for c in connections), 'local P2P witnesses')
        require(any(c['recv_count'] > 0 and c['send_count'] > 0 for c in connections), 'P2P traffic')
    usage = read('process-usage.json')
    require(all(k in usage for k in PROCESSES), 'per-process usage samples')
    print(json.dumps({'result': 'PASS_RECEIPT_RECONCILIATION', 'peers': states, 'tip_at_attach': attach['height'],
                      'tip_at_stop': stop_tip['height'], 'blocks_missed_while_down': witness['blocks_missed'],
                      'resume_seconds_from_restart': witness['resume_seconds_from_restart'],
                      'attach_seconds_from_start': witness['attach_seconds_from_start'], 'pool_sha256': POOL_SHA,
                      'memory_peak_bytes': int(resources['memory.peak']),
                      'scope': 'saved receipt consistency; not independent operator or toolchain reproduction'}, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, IndexError, TypeError) as error:
        print(f'FAIL: {error}', file=sys.stderr)
        sys.exit(1)
