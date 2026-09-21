#!/usr/bin/env python3
"""Reconcile cold backup/restore and payout-wallet restart receipts independently of recover.py control flow."""
import hashlib
import json
from pathlib import Path
import sys

GENESIS = '20ce111b9a74c7ce79fbaafd053afb71b2f2335e208fa7e993fb46c8c91964d8'
IMAGE = 'sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e'
REWARD = 9000000000000
UNLOCK_WINDOW = 60
WRITE_METHODS = {'submit_block', 'generateblocks', 'start_mining', 'stop_mining', 'pop_blocks', 'flush_txpool',
                 'send_raw_transaction', 'relay_tx', 'set_bans', 'set_log_level', 'update', 'out_peers', 'in_peers'}
PROCESSES = ['W', 'peer0', 'peer1', 'peer1-restart', 'peer1-restore']


def require(ok, message):
    if not ok:
        raise ValueError(message)


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
    commands = read('process-commands.json')
    require(sorted(commands) == PROCESSES, 'five owned process commands required')
    require(commands['peer1-restart'] == commands['peer1'] == commands['peer1-restore'], 'restarts must reuse the exact peer1 command')
    for name, wanted in {'peer0': ['127.0.0.1:28180'], 'peer1': ['127.0.0.1:28080']}.items():
        c = commands[name]
        require(all(x not in c for x in ['--offline', '--regtest', '--testnet', '--stagenet', '--fixed-difficulty']),
                'wrong network or difficulty mode')
        require([c[i + 1] for i, x in enumerate(c) if x == '--add-exclusive-node'] == wanted, f'{name} exclusive peers')
        require(c[c.index('--rpc-bind-ip') + 1] == c[c.index('--p2p-bind-ip') + 1] == '127.0.0.1', 'loopback bindings')
        require(c[c.index('--data-dir') + 1].endswith(f'/data/{name}'), 'owned data directory')
    w = commands['W']
    require(w[0].endswith('monero-wallet-rpc') and w[w.index('--daemon-address') + 1] == 'http://127.0.0.1:28181'
            and w[w.index('--rpc-bind-ip') + 1] == '127.0.0.1' and '--trusted-daemon' in w, 'payout wallet bound to peer 1 on loopback')
    require(not any(x in w for x in ['--password', '--restore-deterministic-wallet', '--electrum-seed', '--generate-from-keys',
                                     '--wallet-file']), 'wallet secrets must not be on the command line')
    methods = read('rpc-methods.json')
    require(not WRITE_METHODS & set(methods['peer1']), 'peer1 received a block-injecting or mining RPC')
    require(WRITE_METHODS & set(methods['peer0']) == {'start_mining', 'stop_mining'}, 'peer0 write RPC beyond native mining')
    headers = read('headers.json')
    final = read('rpc-final.json')
    result = read('result.json')
    readback = read('profile-readback.json')
    restart = read('wallet-restart.json')
    backup = read('cold-restore.json')
    require(result['result'] == 'PASS', 'journey did not pass')
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

    # Payout wallet: every coinbase of the payout phase, bound to the canonical headers, equal across both reopenings.
    payout = result['payout_tip']
    require(payout['height'] >= result['phases']['payout_min_top'] and chain[payout['height']]['hash'] == payout['hash'],
            'payout tip is on the final chain')
    before = restart['wallet_before']
    require(before['address_matches'] and not before['outgoing'] and before['other'] == 0, 'payout wallet baseline')
    require(sorted(t[2] for t in before['incoming']) == list(range(1, payout['height'] + 1)), 'one coinbase entry per payout block')
    for txid, amount, height, kind in before['incoming']:
        require(kind == 'block' and amount == REWARD == chain[height]['reward'], 'coinbase entry amount/type')
        require(txid == chain[height]['miner_tx_hash'], 'wallet history txid is not the canonical coinbase hash')
    require(before['balance']['balance'] == payout['height'] * REWARD, 'balance equals payout rewards')
    require(before['balance']['unlocked_balance'] == 0 and tip['height'] - 1 < UNLOCK_WINDOW, 'immature coinbase stays locked')
    require(restart['wallet_after'] == before and restart['wallet_after_cold_restore'] == before,
            'payout wallet state differs after a reopen')
    require(restart['wallet_height_before'] <= restart['wallet_height_after'] <= restart['wallet_height_after_cold_restore'],
            'wallet height must not go backwards')
    # Plain restart: clean exit, opened at the stored tip, no blocks missed, same chain.
    tb = restart['tip_before_shutdown']
    require(restart['shutdown_exit_code'] == 0 and tb == payout, 'plain restart shutdown state')
    require(restart['stored_tip_at_open'] == tb['height'], 'daemon log stored tip at plain restart')
    first = restart['first_rpc_info_after_restart']
    require(first['height'] == tb['height'] + 1 and first['top_block_hash'] == tb['hash'], 'plain restart first readback')
    require(restart['state_after_restart'] == tb and restart['blocks_missed'] == 0, 'plain restart state')
    # Cold backup: taken with the daemon stopped, destroyed, restored byte-identical, reopened at the backup tip, rejoined.
    tbk = backup['tip_at_backup']
    require(backup['shutdown_exit_code'] == 0 and tbk == tb, 'cold backup taken from the cleanly stopped restarted peer')
    require(chain[tbk['height']]['hash'] == tbk['hash'], 'backup tip is on the final chain')
    source = backup['source_manifest']
    require(source and 'lmdb/data.mdb' in source and all(len(v['sha256']) == 64 and v['bytes'] >= 0 for v in source.values()),
            'backup file manifest')
    require(backup['restored_manifest_equal'] is True and backup['data_dir_absent_after_destroy'] is True, 'destroy and restore witness')
    require(len(backup['archive']['sha256']) == 64 == len(result['backup_archive_sha256'])
            and backup['archive']['sha256'] == result['backup_archive_sha256'] and backup['archive']['bytes'] > 0, 'archive receipt')
    require(backup['archive']['path_relative_to_work'].startswith('data/'), 'archive stays in private data')
    offline = backup['tip_mined_while_destroyed']
    require(offline['height'] - tbk['height'] >= result['phases']['offline_blocks'] == backup['blocks_missed'], 'blocks mined while destroyed')
    require(chain[offline['height']]['hash'] == offline['hash'], 'offline tip is on the final chain')
    require(backup['stored_tip_at_open'] == tbk['height'], 'restored database opened at the backup tip')
    first = backup['first_rpc_info_after_restore']
    require(tbk['height'] + 1 <= first['height'] <= len(chain), 'restored first readback')
    require(backup['state_after_rejoin'] == states[1] and backup['rejoin_seconds_from_restart'] > 0, 'restore rejoin')
    require(backup['backed_up_elapsed_s'] < backup['restored_elapsed_s'] < backup['restarted_elapsed_s'] < backup['caught_up_elapsed_s'],
            'cold restore timeline')
    require(all(c['ip'] == '127.0.0.1' for c in backup['connections']['connections']), 'restored peer local connections')
    peers = read('peers-after.json')
    for n in (0, 1):
        connections = peers[n]['connections']
        require(connections and all(c['ip'] == '127.0.0.1' for c in connections), 'local P2P witnesses')
        require(any(c['recv_count'] > 0 and c['send_count'] > 0 for c in connections), 'P2P traffic')
    usage = read('process-usage.json')
    require(all(k in usage for k in ('peer0', 'peer1', 'peer1-restart', 'peer1-restore')), 'per-process usage samples')
    print(json.dumps({'result': 'PASS_RECEIPT_RECONCILIATION', 'peers': states, 'payout_blocks': payout['height'],
                      'payout_balance_atomic': before['balance']['balance'], 'restore_rejoin_s': backup['rejoin_seconds_from_restart'],
                      'blocks_missed_while_destroyed': backup['blocks_missed'], 'backup_files': len(source),
                      'backup_archive_sha256': backup['archive']['sha256'], 'memory_peak_bytes': int(resources['memory.peak']),
                      'scope': 'saved receipt consistency; not independent operator or toolchain reproduction'}, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, IndexError, TypeError) as error:
        print(f'FAIL: {error}', file=sys.stderr)
        sys.exit(1)
