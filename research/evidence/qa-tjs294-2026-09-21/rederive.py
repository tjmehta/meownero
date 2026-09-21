#!/usr/bin/env python3
"""TJS-294 independent re-derivation from recover.py public receipts (QA-authored, not the candidate verifier).

Usage: rederive.py <work-or-receipt-dir> <out.json>
Reads only result.json, headers.json, rpc-final.json, wallet-restart.json, cold-restore.json, rpc-methods.json,
process-commands.json, resources.json, peers-after.json, profile-readback.json and the three peer1 stdout logs.
"""
import json, re, sys
from pathlib import Path

W = Path(sys.argv[1]); COIN = 10**12; REWARD = 9 * COIN
GENESIS = '20ce111b9a74c7ce79fbaafd053afb71b2f2335e208fa7e993fb46c8c91964d8'
FIXTURE = 'M9Lds8CcBgCJbqSiUvYfS3BfhEdxZmv8pDt25oW1LzxrZv9Uq6ARagiFViMGUE3gJk5VPWingCXVf1p2tyAy6SUeSLMMvfc'
rd = lambda n: json.loads((W / n).read_text())
r, H, F, wr, cr, rm, pc, res, pa, rb = (rd(n) for n in ('result.json', 'headers.json', 'rpc-final.json', 'wallet-restart.json',
                                                            'cold-restore.json', 'rpc-methods.json', 'process-commands.json',
                                                            'resources.json', 'peers-after.json', 'profile-readback.json'))
out = {}


def chk(name, cond, detail=None):
    out[name] = {'ok': bool(cond), 'detail': detail}
    print(('OK  ' if cond else 'FAIL'), name, '' if detail is None else detail)


c0, c1 = H
top = len(c0) - 1
chk('journey result PASS', r['result'] == 'PASS')
# --- chain shape, identical on both peers, re-derived from headers not from result.json
chk('both peers identical header sets (full dict equality)', c0 == c1, {'headers': len(c0)})
chk('header chain linked with heights 0..top', all(c0[i]['prev_hash'] == c0[i - 1]['hash'] and c0[i]['height'] == i for i in range(1, len(c0))) and c0[0]['height'] == 0)
chk('genesis pinned, reward 0, v1', c0[0]['hash'] == GENESIS and c0[0]['reward'] == 0 and c0[0]['major_version'] == 1)
chk('every mined block v16, reward 9 MEOW, 0 txes, not orphan', all(h['major_version'] == 16 and h['reward'] == REWARD and h['num_txes'] == 0 and not h['orphan_status'] for h in c0[1:]))
diffs = [h['difficulty'] for h in c0]
cum = [sum(diffs[:i + 1]) for i in range(len(diffs))]
chk('cumulative work = running sum of difficulty (wide and plain) at every height', all(h['cumulative_difficulty'] == cum[i] == int(h['wide_cumulative_difficulty'], 16) and h['difficulty'] == int(h['wide_difficulty'], 16) for i, h in enumerate(c0)), {'difficulties': diffs, 'total': cum[-1], 'hex': hex(cum[-1])})
chk('distinct nonces on mined blocks (native PoW signature)', len({h['nonce'] for h in c0[1:]}) == top, {'distinct': len({h['nonce'] for h in c0[1:]})})
ts = [h['timestamp'] for h in c0]
chk('timestamps non-decreasing after genesis', all(ts[i] >= ts[i - 1] for i in range(2, len(ts))), {'offsets_from_block1': [t - ts[1] for t in ts[1:]]})
for n in (0, 1):
    info, tip, s = F[n]['info'], F[n]['tip']['block_header'], F[n]['sum']
    chk(f'peer{n} final get_info height/top/target/alt/pool match headers', info['height'] == top + 1 and info['top_block_hash'] == c0[-1]['hash'] and info['target'] == 90 and info['alt_blocks_count'] == 0 and info['tx_pool_size'] == 0 and info['tx_count'] == 0, {'height': info['height']})
    chk(f'peer{n} final tip header == headers[top]', tip == c0[-1])
    chk(f'peer{n} emission = top x 9 MEOW = sum(header reward); fees 0', s['emission_amount'] == top * REWARD == sum(h['reward'] for h in c0) and s['fee_amount'] == 0, s['emission_amount'])
    chk(f'peer{n} cumulative_difficulty == sum(difficulty)', info['cumulative_difficulty'] == cum[-1] == int(info['wide_cumulative_difficulty'], 16))
    chk(f'peer{n} result.peers[{n}] re-derived equal', r['peers'][n] == {'height': top, 'hash': c0[-1]['hash'], 'cumulative_work': hex(cum[-1]), 'emission_atomic': top * REWARD, 'fees_atomic': 0})
    chk(f'peer{n} fresh start readback: height 1, mainnet mode, fork v16 at 1, template reward 9 MEOW', rb[str(n)]['info']['height'] == 1 and rb[str(n)]['info']['nettype'] == 'mainnet' and rb[str(n)]['fork']['version'] == 16 and rb[str(n)]['fork']['earliest_height'] == 1 and rb[str(n)]['template']['expected_reward'] == REWARD and rb[str(n)]['genesis']['hash'] == GENESIS)
# peer1's final get_info comes from the restored daemon (third life), so only peer0's start_time bounds block 1; the restored peer1 must have started after peer0 and after the tip block.
chk('block 1 >= peer0 start_time; tip <= adjusted_time on both; restored peer1 start_time >= tip timestamp', ts[1] >= F[0]['info']['start_time'] and all(ts[-1] <= F[n]['info']['adjusted_time'] for n in (0, 1)) and F[1]['info']['start_time'] > F[0]['info']['start_time'] and F[1]['info']['start_time'] >= ts[-1], {'start_time': [F[n]['info']['start_time'] for n in (0, 1)], 'b1': ts[1], 'tip': ts[-1]})

# --- payout wallet W: history bound to canonical coinbase hashes; equality across both reopenings
before, after, after_cold = wr['wallet_before'], wr['wallet_after'], wr['wallet_after_cold_restore']
P = r['payout_tip']['height']
chk('payout tip is on the final chain and >= phase minimum', c0[P]['hash'] == r['payout_tip']['hash'] and P >= r['phases']['payout_min_top'] and r['payout_tip']['cumulative_work'] == hex(cum[P]) and r['payout_tip']['emission_atomic'] == P * REWARD, P)
chk('W address matches on every snapshot; no outgoing; no pending/pool/failed', all(s['address_matches'] and s['outgoing'] == [] and s['other'] == 0 for s in (before, after, after_cold)))
chk('W history = exactly one coinbase per payout height 1..P', sorted(t[2] for t in before['incoming']) == list(range(1, P + 1)) and len(before['incoming']) == P)
chk('every W history txid == canonical header miner_tx_hash at that height, amount 9 MEOW, type block', all(t[0] == c0[t[2]]['miner_tx_hash'] and t[1] == REWARD and t[3] == 'block' for t in before['incoming']))
chk('W balance = P x 9 MEOW, unlocked 0 (coinbase immature, top < 60)', before['balance'] == {'balance': P * REWARD, 'unlocked_balance': 0} and top < 60, before['balance'])
chk('W after plain restart == before (address, balance, incoming, outgoing, other)', after == before)
chk('W after cold restore == before', after_cold == before)
chk('W scanned height: P+1 before, P+1 after restart, top+1 after restore', wr['wallet_height_before'] == P + 1 == wr['wallet_height_after'] and wr['wallet_height_after_cold_restore'] == top + 1, (wr['wallet_height_before'], wr['wallet_height_after'], wr['wallet_height_after_cold_restore']))
chk('offline blocks P+1..top were paid to the public fixture, not W (W history unchanged)', json.loads((W / 'mining-command.json').read_text())['offline']['miner_address'] == FIXTURE and all(t[2] <= P for t in after_cold['incoming']))

# --- plain restart of peer 1
tb = wr['tip_before_shutdown']
chk('plain restart: clean exit 0; shutdown tip == payout tip', wr['shutdown_exit_code'] == 0 and tb == r['payout_tip'])
chk('plain restart: first RPC readback height P+1 and top hash == stored tip; not yet synchronized', wr['first_rpc_info_after_restart']['height'] == P + 1 and wr['first_rpc_info_after_restart']['top_block_hash'] == tb['hash'])
chk('plain restart: stored tip at DB open (receipt) == P; blocks_missed 0; state after == before', wr['stored_tip_at_open'] == P and wr['blocks_missed'] == 0 and wr['state_after_restart'] == tb)

# --- cold backup / destroy / restore / rejoin
tbk = cr['tip_at_backup']
chk('cold backup taken from cleanly stopped restarted peer at the payout tip', cr['shutdown_exit_code'] == 0 and tbk == tb == r['payout_tip'])
src = cr['source_manifest']
chk('backup manifest: lmdb/data.mdb + lmdb/lock.mdb + p2pstate.bin with 64-hex sha256', set(src) == {'lmdb/data.mdb', 'lmdb/lock.mdb', '28180/p2pstate.bin'} and all(re.fullmatch('[0-9a-f]{64}', v['sha256']) and v['bytes'] > 0 for v in src.values()), {k: v['bytes'] for k, v in src.items()})
chk('archive sha256 == result.backup_archive_sha256; bytes > sum(file bytes); kept under data/', cr['archive']['sha256'] == r['backup_archive_sha256'] and cr['archive']['bytes'] > sum(v['bytes'] for v in src.values()) and cr['archive']['path_relative_to_work'].startswith('data/'), cr['archive'])
chk('data dir absent after destroy; restored manifest equal', cr['data_dir_absent_after_destroy'] is True and cr['restored_manifest_equal'] is True)
off = cr['tip_mined_while_destroyed']
chk('blocks mined while destroyed: off.height - P == blocks_missed == phases.offline_blocks; offline tip on final chain', off['height'] - P == cr['blocks_missed'] == r['phases']['offline_blocks'] == r['blocks_missed_while_destroyed'] and c0[off['height']]['hash'] == off['hash'] and off['cumulative_work'] == hex(cum[off['height']]), off['height'])
chk('restore: stored tip at DB open == backup height; first readback top hash == backup tip hash, height P+1', cr['stored_tip_at_open'] == tbk['height'] and cr['first_rpc_info_after_restore']['top_block_hash'] == tbk['hash'] and cr['first_rpc_info_after_restore']['height'] == P + 1)
chk('rejoin: state_after_rejoin == peer0 final state == result.peers[0]; rejoin seconds > 0', cr['state_after_rejoin'] == r['peers'][0] == r['peers'][1] and cr['rejoin_seconds_from_restart'] == cr['caught_up_elapsed_s'] - cr['restarted_elapsed_s'] > 0, round(cr['rejoin_seconds_from_restart'], 3))
chk('timeline: backed_up < restored < restarted < caught_up; plain restart before backup', cr['backed_up_elapsed_s'] < cr['restored_elapsed_s'] <= cr['restarted_elapsed_s'] < cr['caught_up_elapsed_s'] and wr['restarted_elapsed_s'] < cr['backed_up_elapsed_s'])
chk('restored peer: only loopback connections; sync_info height == top+1', all(c['ip'] == '127.0.0.1' for c in cr['connections']['connections']) and cr['sync_info']['height'] == top + 1)
chk('final peers-after: both peers have loopback connections with traffic both ways', all(pa[n]['connections'] and all(c['ip'] == '127.0.0.1' for c in pa[n]['connections']) and any(c['recv_count'] > 0 and c['send_count'] > 0 for c in pa[n]['connections']) for n in (0, 1)))

# --- delivery: no block injection, exact commands, wallet privacy on the command line
chk('peer1 received only read RPC (+sync_info) from the runner', not ({'submit_block', 'generateblocks', 'start_mining', 'stop_mining', 'pop_blocks', 'flush_txpool', 'send_raw_transaction', 'relay_tx'} & set(rm['peer1'])), sorted(rm['peer1']))
chk('peer0 write RPC exactly start_mining x2 + stop_mining x2', {k: v for k, v in rm['peer0'].items() if not k.startswith(('get_', 'hard_fork'))} == {'start_mining': 2, 'stop_mining': 2})
chk('five owned processes; peer1 restart and restore commands byte-equal to peer1', sorted(pc) == ['W', 'peer0', 'peer1', 'peer1-restart', 'peer1-restore'] and pc['peer1'] == pc['peer1-restart'] == pc['peer1-restore'])
chk('peer commands: mainnet mode inside container (no testnet/stagenet/regtest/offline/fixed-difficulty), loopback binds, exclusive peering', all(not any(x in pc[p] for x in ('--testnet', '--stagenet', '--regtest', '--offline', '--fixed-difficulty')) and pc[p][pc[p].index('--rpc-bind-ip') + 1] == pc[p][pc[p].index('--p2p-bind-ip') + 1] == '127.0.0.1' and '--add-exclusive-node' in pc[p] for p in ('peer0', 'peer1')))
w = pc['W']
chk('wallet RPC bound to peer1 daemon on loopback; no seed/keys/password/wallet-file on the command line', w[w.index('--daemon-address') + 1] == 'http://127.0.0.1:28181' and w[w.index('--rpc-bind-ip') + 1] == '127.0.0.1' and not any(x in w for x in ('--password', '--electrum-seed', '--generate-from-keys', '--restore-deterministic-wallet', '--wallet-file', '--spendkey', '--viewkey')))
chk('all five owned exits 0; container caps 4 GiB/no swap/2 CPU; no OOM; elapsed < 1800 s', all(v == 0 for v in res['daemon_exit_codes'].values()) and len(res['daemon_exit_codes']) == 5 and int(res['memory.max']) == 4 * 1024**3 and int(res['memory.swap.max']) == 0 and res['cpu.max'].split() == ['200000', '100000'] and 'oom_kill 0' in res['memory.events'] and res['elapsed_seconds'] < 1800, {'elapsed_s': round(res['elapsed_seconds'], 1), 'peak_bytes': int(res['memory.peak'])})
chk('container.exit 0, launcher.exit 0', (W / 'container.exit').read_text().strip() == '0' and (W / 'launcher.exit').read_text().strip() == '0')

# --- daemon-log corroboration, read directly (not through the runner's receipts)
init = re.compile(r'Blockchain initialized\. last block: (\d+),')
logs = {n: init.findall((W / f'{n}.stdout.log').read_text(errors='replace')) for n in ('peer1', 'peer1-restart', 'peer1-restore')}
chk('daemon stdout: peer1 opened at 0; restart opened at P; restore opened at P (backup tip)', logs['peer1'] == ['0'] and logs['peer1-restart'] == [str(P)] and logs['peer1-restore'] == [str(tbk['height'])], logs)
p0 = (W / 'peer0.log').read_text(errors='replace')
found = re.findall(r'Found block <([0-9a-f]{64})> at height (\d+) for difficulty: (\d+)', p0)
chk('peer0.log Found block lines: one per mined height, hash and difficulty equal headers', [(h['hash'], str(h['height']), str(h['difficulty'])) for h in c0[1:]] == found, len(found))
p1 = (W / 'peer1.log').read_text(errors='replace')
chk('peer1.log: three DB opens (0, P, P); offline block hashes appear after the restore open; no REORGANIZE/alternative', init.findall(p1) == ['0', str(P), str(P)] and all(p1.rfind(c0[h]['hash']) > p1.rfind('Blockchain initialized. last block: %d' % P) for h in range(P + 1, top + 1)) and 'REORGANIZE' not in p1 and 'alternative' not in p1.lower())
chk('peer1.log: no Found block lines (peer1 never mined)', 'Found block' not in p1)

fails = [k for k, v in out.items() if not v['ok']]
print('SUMMARY', 'PASS' if not fails else 'FAIL', 'checks=%d fails=%s' % (len(out), fails))
json.dump(out, open(sys.argv[2], 'w'), indent=1)
sys.exit(1 if fails else 0)
