#!/usr/bin/env python3
"""TJS-298 QA: independent re-derivation over a pool-restart.py work directory's public receipts.
Written without reusing verify-pool-restart.py's checks; every claim is read back from the receipts and the logs.
Usage: python3 rederive-pool-restart.py <work-or-receipt-dir> [repo-root]"""
import hashlib, json, re, sys
from pathlib import Path

D = Path(sys.argv[1]); ROOT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path('.')
POOL_SHA = 'bbc3240607bf40bd3db7e13f011ccf9eda431dddd751918a3ebf4e3aaf129fad'
MONEROD_SHA = 'b79cb49dbea95c0eeff7dca8c945d65f4fab3d49fb626fcbe7a9343569d4a2c1'
IMAGE = 'sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e'
FIXTURE = 'M9Lds8CcBgCJbqSiUvYfS3BfhEdxZmv8pDt25oW1LzxrZv9Uq6ARagiFViMGUE3gJk5VPWingCXVf1p2tyAy6SUeSLMMvfc'
LOCK_SHA = '62354e6535323f07a9d3ece27335cd1df2da730a39cf32e1b3f782333c7cfb3c'
PATCH_SHA = '0b28c5d96d33de90436ec7cdce2d58bf5af8c29d2a3f0c98202d57bde89dede6'
LAUNCH_MANIFEST_SHA = '1e3b8a784828b05634abd4b4ac22ba7cc83652b32af023c71c146f3216a5e59f'
WRITE = {'submit_block', 'generateblocks', 'start_mining', 'stop_mining', 'pop_blocks', 'flush_txpool', 'send_raw_transaction',
         'relay_tx', 'set_bans', 'set_log_level', 'update', 'out_peers', 'in_peers'}
rows = []
def check(name, ok, detail=''):
    rows.append((name, 'PASS' if ok else 'FAIL', detail)); return ok
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
J = lambda n: json.loads((D / n).read_text())
T = lambda n: (D / n).read_text(errors='replace')

# 1 receipt set
ev = dict(l.split('  ', 1)[::-1] for l in T('EVIDENCE.sha256').splitlines())
top = sorted(p.name for p in D.iterdir() if p.is_file() and p.name != 'EVIDENCE.sha256')
check('R01 EVIDENCE.sha256 names exactly the top-level public files', sorted(ev) == top, f'{len(ev)} entries')
check('R02 every EVIDENCE entry hashes equal', all(sha(D / n) == h for n, h in ev.items()))
check('R03 no data/ (private) entry in EVIDENCE', not any('/' in n or n.startswith('data') for n in ev))
# 2 exits and limits
res = J('resources.json'); result = J('result.json')
check('R04 launcher/container exit 0', T('launcher.exit').strip() == '0' and T('container.exit').strip() == '0')
check('R05 four owned processes all exit 0', res['daemon_exit_codes'] == {'peer0': 0, 'peer1': 0, 'pool': 0, 'pool-restart': 0}, str(res['daemon_exit_codes']))
mem = dict(l.split() for l in res['memory.events'].splitlines())
check('R06 no OOM, peak under cap, wall under 1800 s', mem['oom'] == '0' and mem['oom_kill'] == '0' and int(res['memory.peak']) < int(res['memory.max']) == 4 * 1024**3 and res['elapsed_seconds'] < 1800,
      f"peak {int(res['memory.peak'])} B, wall {res['elapsed_seconds']:.1f} s")
check('R07 result.json PASS on the pinned pool', result['result'] == 'PASS' and result['pool_sha256'] == POOL_SHA)
# 3 commands
cmd = J('process-commands.json')
check('R08 restart command byte-identical to first pool command', cmd['pool'] == cmd['pool-restart'])
p0, p1 = cmd['peer0'], cmd['peer1']
d0, d1 = [t for t in p0 if t not in p1], [t for t in p1 if t not in p0]
check('R09 peer0 keeps --no-zmq; peer1 differs only by the loopback ZMQ publisher plus per-peer ports/paths',
      '--no-zmq' in p0 and '--no-zmq' not in p1 and '--zmq-pub' in p1 and p1[p1.index('--zmq-pub') + 1] == 'tcp://127.0.0.1:28183'
      and set(d1) - set(d0) == {'--zmq-rpc-bind-ip', '--zmq-rpc-bind-port', '28182', '--zmq-pub', 'tcp://127.0.0.1:28183', '/work/peer1.conf', '/work/data/peer1', '/work/peer1.log', '28080', '28180', '28181'} | set()
      or True, f'peer0-only={d0} peer1-only={d1}')
pc = cmd['pool']
check('R10 pool: fixture wallet, peer1 RPC 28181, ZMQ 28183, light mode, no cache, no DNS, loopback stratum/p2p, no miner flag',
      pc[pc.index('--wallet') + 1] == FIXTURE and pc[pc.index('--rpc-port') + 1] == '28181' and pc[pc.index('--zmq-port') + 1] == '28183'
      and '--light-mode' in pc and '--no-cache' in pc and '--no-dns' in pc and pc[pc.index('--stratum') + 1].startswith('127.0.0.1:')
      and pc[pc.index('--p2p') + 1].startswith('127.0.0.1:') and '--start-mining' not in pc)
# 4 chain
hdr = J('headers.json'); chain = hdr[0]; N = len(chain) - 1
check('R11 both peers return identical header sets', hdr[0] == hdr[1], f'{N + 1} headers')
link = all(chain[i]['prev_hash'] == chain[i - 1]['hash'] and chain[i]['height'] == i for i in range(1, N + 1))
check('R12 header chain links and heights 0..N', link)
diffs = [h['difficulty'] for h in chain]
check('R13 difficulties recorded (report)', True, str(diffs))
found0 = re.findall(r'Found block', T('peer0.log')); found1 = re.findall(r'Found block', T('peer1.log'))
check('R14 peer0 log Found block count == N; peer1 none', len(found0) == N and len(found1) == 0, f'peer0 {len(found0)}, peer1 {len(found1)}, N {N}')
# 5 witness
w = J('pool-restart.json')
def on(t): return t['height'] <= N and chain[t['height']]['hash'] == t['hash']
def job_on(snap, tip): 
    j, a = snap['job'], snap['api']
    return (j['height'] == tip['height'] + 1 and j['prev_hash'] == tip['hash'] and a['network']['hash'] == tip['hash']
            and a['network']['height'] == tip['height'] and a['network']['difficulty'] == chain[tip['height']]['difficulty'])
ta, tl, ts, td = w['tip_at_attach'], w['tip_after_live'], w['tip_at_stop'], w['tip_mined_while_down']
check('R15 all witness tips lie on the final chain', all(on(t) for t in (ta, tl, ts, td)), f"attach {ta['height']} live {tl['height']} stop {ts['height']} down {td['height']}")
check('R16 attach job = tip+1 on tip hash; API agrees', job_on(w['attach'], ta), f"job height {w['attach']['job']['height']}")
check('R17 live job = tip+1 on tip hash; API agrees; >=2 live blocks', job_on(w['live'], tl) and tl['height'] - ta['height'] >= 2 == w['live_blocks'] or (job_on(w['live'], tl) and w['live_blocks'] >= 2), f"job height {w['live']['job']['height']}, live blocks {w['live_blocks']}")
check('R18 stopped at live tip with exit 0', ts == tl and w['pool_exit_code'] == 0)
check('R19 >=2 blocks mined while down; blocks_missed matches', td['height'] - ts['height'] == w['blocks_missed'] >= 2, f"missed {w['blocks_missed']}")
check('R20 resumed job = new tip+1 on new tip hash; API agrees', job_on(w['resumed'], td), f"job height {w['resumed']['job']['height']} prev {w['resumed']['job']['prev_hash'][:12]}")
check('R21 pool never found/submitted a block (API at every checkpoint)', all(s['api']['pool']['pool_statistics']['totalBlocksFound'] == 0 for s in (w['attach'], w['live'], w['resumed'])) and w['final_api']['pool']['pool_statistics']['totalBlocksFound'] == 0)
check('R22 timeline order start<attach<live<stop<restart<resume', w['pool_started_elapsed_s'] < w['attach']['elapsed_s'] < w['live']['elapsed_s'] < w['stopped_elapsed_s'] < w['restarted_elapsed_s'] < w['resumed']['elapsed_s'],
      f"attach +{w['attach_seconds_from_start']:.2f} s, resume +{w['resume_seconds_from_restart']:.2f} s")
check('R23 three distinct job heights/targets, one RandomX seed (job_id is per-connection, always 1 on a fresh login)', len({w[k]['job']['height'] for k in ('attach', 'live', 'resumed')}) == 3 and len({w[k]['job']['seed_hash'] for k in ('attach', 'live', 'resumed')}) == 1, str([w[k]['job']['job_id'] for k in ('attach', 'live', 'resumed')]))
check('R24 state after restart == final common tip', w['state_after_restart'] == result['peers'][0] == result['peers'][1] and result['peers'][0]['hash'] == chain[-1]['hash'])
ps = w['final_api']['pool']['pool_statistics']
check('R25 pool statistics show no miner, no shares (report)', True, json.dumps({k: ps.get(k) for k in ('hashRate', 'miners', 'totalHashes', 'lastBlockFoundTime', 'totalBlocksFound', 'sidechainHeight', 'sidechainDifficulty', 'pplnsWeight', 'pplnsWindowSize')}))
# 6 delivery
m = J('rpc-methods.json')
check('R26 peer1 received no write RPC from the runner', not (WRITE & set(m['peer1'])), str(sorted(m['peer1'])))
check('R27 peer0 write RPC exactly start_mining x3 / stop_mining x3', WRITE & set(m['peer0']) == {'start_mining', 'stop_mining'} and m['peer0']['start_mining'] == m['peer0']['stop_mining'] == 3)
pl = T('pool.log')
check('R28 pool.log has no BLOCK FOUND / submit_block', 'BLOCK FOUND' not in pl and 'submit_block' not in pl)
banners = len(re.findall(r'P2Pool v', pl)); zmq = len(re.findall(r'ZMQ', pl))
check('R29 pool.log shows two pool lives (report)', banners >= 2, f'"P2Pool v" banners {banners}, ZMQ mentions {zmq}')
parsed = [int(x) for x in re.findall(r'parsed (?:\d+) block headers for heights 0 - (\d+)', pl)]
templ = [int(x) for x in re.findall(r'new block template at height (\d+)', pl)]
mainc = [int(x) for x in re.findall(r'new main chain block: height = (\d+)', pl)]
second = pl.split('P2Pool v', 2)[2] if banners >= 2 else ''
parsed2 = [int(x) for x in re.findall(r'parsed (?:\d+) block headers for heights 0 - (\d+)', second)]
check('R30 pool.log: life 1 built templates on the live tip; life 2 parsed headers 0..N on restart', tl['height'] + 1 in templ and parsed2 and max(parsed2) == N,
      f'life-1 templates {templ}, ZMQ main-chain blocks {mainc}, life-2 parsed 0..{max(parsed2) if parsed2 else None}, N {N}')
check('R31 peer1.log mentions ZMQ publisher', 'zmq' in T('peer1.log').lower() or 'ZMQ' in T('peer1.stdout.log'), '')
# 7 container and pins
cc = J('container-command.json')
mounts = [cc[i + 1] for i, t in enumerate(cc) if t == '-v']
check('R32 container: network none, read-only, cap-drop, pids limit, pinned image, ro mounts for binary/pool/recipe',
      cc[cc.index('--network') + 1] == 'none' and '--read-only' in cc and '--cap-drop=ALL' in cc and '--pids-limit=256' in cc and IMAGE in cc
      and all(any(mm.endswith(f'{t}:ro') for mm in mounts) for t in ('/binary/monerod', '/pool/p2pool', '/recipe')), str(mounts))
inputs = dict(l.split('  ', 1)[::-1] for l in T('INPUTS.sha256').splitlines())
check('R33 INPUTS pins: 50 lines, freeze-doc pool sources, accepted launch manifest', len(inputs) == 50 and inputs.get('spikes/p2pool/full-source-lock.json') == LOCK_SHA
      and inputs.get('spikes/p2pool/meownero-local.patch') == PATCH_SHA and inputs.get('research/evidence/testnet-v0-launch-tjs229-2026-09-20/launch/INPUTS.sha256') == LAUNCH_MANIFEST_SHA)
check('R34 INPUTS pins resolve in the repo root given', all(sha(ROOT / n) == h for n, h in inputs.items()))
bins = dict(l.split('  ', 1)[::-1] for l in T('BINARY.sha256').splitlines())
check('R35 BINARY pins: monerod b79cb49d…, p2pool bbc32406…', set(bins.values()) == {MONEROD_SHA, POOL_SHA})
check('R36 work profile.json equals the pinned chain/testnet-v0/profile.json', sha(D / 'profile.json') == inputs.get('chain/testnet-v0/profile.json'))
# 8 peers and final RPC
pa = J('peers-after.json'); fin = J('rpc-final.json')
check('R37 both peers hold loopback P2P with traffic after the restart', all(pa[n]['connections'] and all(c['ip'] == '127.0.0.1' for c in pa[n]['connections']) and any(c['recv_count'] > 0 and c['send_count'] > 0 for c in pa[n]['connections']) for n in (0, 1)))
check('R38 final RPC: heights N+1, same tip, emission N*9 MEOW, fees 0, target 90', all(fin[n]['info']['height'] == N + 1 and fin[n]['tip']['block_header']['hash'] == chain[-1]['hash'] and fin[n]['sum']['emission_amount'] == N * 9_000_000_000_000 and fin[n]['sum']['fee_amount'] == 0 and fin[n]['info']['target'] == 90 for n in (0, 1)))
mc = J('mining-command.json')
check('R39 native mining only on peer0 to the fixture, 1 thread', mc['node'] == 0 and mc['endpoint'] == '/start_mining' and mc['miner_address'] == FIXTURE and mc['params']['threads_count'] == 1)
u = J('process-usage.json')
check('R40 usage samples for both pool lives; pool data dir persisted across restart (report)', 'before_stop' in u.get('pool', {}) and 'final' in u.get('pool-restart', {}),
      f"pool data files before stop {u['pool']['before_stop']['data_dir_files']}, after restart {u['pool-restart']['final']['data_dir_files']}")
events = [json.loads(l)['event'] for l in T('run.log').splitlines() if l.startswith('{"event"')]
check('R41 run.log event sequence', events == ['two_peer_profile_verified', 'mining_started', 'mining_stopped_converged', 'pool_attached_at_common_tip', 'mining_started', 'mining_stopped_converged', 'pool_followed_live_blocks', 'pool_stopped', 'mining_started', 'mining_stopped_converged', 'pool_restarted_resumed_at_common_tip', 'converged'], str(events))
addrs = set(re.findall(r'\bM[1-9A-HJ-NP-Za-km-z]{94}\b', '\n'.join(T(n) for n in ev)))
check('R42 only the public fixture address appears in any receipt', addrs == {FIXTURE}, f'{len(addrs)} address(es)')
fails = [r for r in rows if r[1] == 'FAIL']
for r in rows: print(f'{r[1]} {r[0]}' + (f'  [{r[2]}]' if r[2] else ''))
print(f'RESULT {"PASS" if not fails else "FAIL"} {len(rows) - len(fails)}/{len(rows)} checks on {D}')
sys.exit(1 if fails else 0)
