#!/usr/bin/env python3
"""TJS-278 independent re-derivation from run-03 public receipts (QA-authored, not the candidate verifier)."""
import json, sys, statistics
from pathlib import Path
W = Path(sys.argv[1]); COIN = 10**12
r = json.loads((W/'result.json').read_text()); H = json.loads((W/'headers.json').read_text()); F = json.loads((W/'rpc-final.json').read_text())
cases = {c['case']: c for c in r['cases'] if not c['case'].startswith('mining_')}
out = {}
def chk(name, cond, detail=None):
    out[name] = {'ok': bool(cond), 'detail': detail}
    print(('OK  ' if cond else 'FAIL'), name, '' if detail is None else detail)
sf, pr, pc, sr, rr, rc, wr = (cases[k] for k in ('solo_funded','payment_relay','payment_confirmed','seed_restored','recovered_spend_relay','recovered_spend_confirmed','wallet_reopened'))
a0 = sf['sender']['balance']; fee1, fee2 = pr['fee'], rr['fee']
chk('funding = 100 blocks x 9 MEOW', a0 == 100*9*COIN and sf['tip'][0] == 100, a0)
chk('sender debit = amount + fee', pc['sender_after']['balance'] == a0 - 5*COIN - fee1, (a0, 5*COIN, fee1, pc['sender_after']['balance']))
chk('recipient credit = amount', pc['recipient']['balance'] == 5*COIN and pc['incoming'] == [[pr['txid'], 5*COIN]])
chk('payment confirmed same height+hash on both peers', len({(c['height'], c['block_hash']) for c in pc['confirmations']}) == 1 and {c['node'] for c in pc['confirmations']} == {0,1}, pc['confirmations'][0])
chk('restore: address/history/balance equal', sr['address_matches'] and sr['original'] == sr['restored'] and sr['restored']['balance'] == pc['recipient'] and sr['restored']['incoming'] == pc['incoming'])
chk('restored spend debit = amount + fee', rc['sender']['balance'] == 5*COIN - 2*COIN - fee2, rc['sender']['balance'])
chk('return credit to A', rc['recipient']['balance'] == pc['sender_after']['balance'] + 2*COIN, rc['recipient']['balance'])
chk('recovered spend confirmed same height+hash both peers', len({(c['height'], c['block_hash']) for c in rc['confirmations']}) == 1 and {c['node'] for c in rc['confirmations']} == {0,1}, rc['confirmations'][0])
chk('reopen preserves state incl. outgoing spend', wr['address_matches'] and wr['before'] == wr['after'] and [rr['txid'], 2*COIN, fee2] in wr['after']['outgoing'] and wr['after']['balance'] == rc['sender'])
chk('tx type 6 / ring 16 on every input, both peers, both txs', all(d['rct_type']==6 and d['version']==2 and d['ring_sizes'] and all(x==16 for x in d['ring_sizes']) and d['in_pool'] for t in (pr,rr) for d in t['decoded']) and all({d['node'] for d in t['decoded']}=={0,1} for t in (pr,rr)))
chk('txid in both mempools at relay', all(t['txid'] in p for t in (pr,rr) for p in t['pools']))
# chain-level
for n in (0,1):
    c = H[n]; info, s = F[n]['info'], F[n]['sum']
    chk(f'peer{n} header chain linked, 125 headers, v16 after genesis', len(c)==125 and all(c[i]['prev_hash']==c[i-1]['hash'] and c[i]['height']==i for i in range(1,len(c))) and c[0]['height']==0 and all(h['major_version']==16 for h in c[1:]))
    chk(f'peer{n} genesis pinned', c[0]['hash']=='20ce111b9a74c7ce79fbaafd053afb71b2f2335e208fa7e993fb46c8c91964d8' and c[0]['reward']==0)
    chk(f'peer{n} emission = 124 x 9 MEOW', s['emission_amount']==124*9*COIN==r['emission'], s['emission_amount'])
    chk(f'peer{n} fee aggregate = fee1+fee2', s['fee_amount']==fee1+fee2==r['fee_total'], s['fee_amount'])
    chk(f'peer{n} header reward sum = emission + fees', sum(h['reward'] for h in c)==s['emission_amount']+s['fee_amount'])
    chk(f'peer{n} block 101 reward = 9 MEOW + fee1; block 113 = 9 MEOW + fee2; others 9 MEOW', c[101]['reward']==9*COIN+fee1 and c[113]['reward']==9*COIN+fee2 and all(h['reward']==9*COIN for i,h in enumerate(c) if i not in (0,101,113)))
    chk(f'peer{n} num_txes: 1 at 101, 1 at 113, else 0', c[101]['num_txes']==1 and c[113]['num_txes']==1 and all(h['num_txes']==0 for i,h in enumerate(c) if i not in (101,113)))
    chk(f'peer{n} cumulative difficulty = sum(difficulty) = wide tip', sum(h['difficulty'] for h in c)==info['cumulative_difficulty']==int(r['tip'][2],16)==c[-1]['cumulative_difficulty'], info['cumulative_difficulty'])
    chk(f'peer{n} tip matches info', info['height']==125 and info['top_block_hash']==c[-1]['hash']==r['tip'][1] and info['tx_pool_size']==0 and info['tx_count']==2 and info['alt_blocks_count']==0 and info['target']==90)
    chk(f'peer{n} confirmation hashes match canonical headers', pc['confirmations'][n]['block_hash']==c[101]['hash'] and rc['confirmations'][n]['block_hash']==c[113]['hash'])
    # get_block_header_by_height leaves pow_hash empty unless fill_pow_hash=true; the runner did not request it.
    # Native PoW is evidenced instead by per-block nonces and the daemon 'Found block ... for difficulty' log lines.
    chk(f'peer{n} pow_hash empty (RPC default, not requested) and nonces non-constant', all(h['pow_hash']=='' for h in c[1:]) and len({h['nonce'] for h in c[1:]})>100, {'distinct_nonces': len({h['nonce'] for h in c[1:]})})
chk('both peers identical header hash list', [h['hash'] for h in H[0]]==[h['hash'] for h in H[1]])
chk('both peers identical difficulty list', [h['difficulty'] for h in H[0]]==[h['difficulty'] for h in H[1]])
# timing / DAA sanity: timestamps vs wall clock
ts = [h['timestamp'] for h in H[0]]
d = [ts[i]-ts[i-1] for i in range(2,len(ts))]
chk('timestamps non-decreasing after genesis (no steering signature)', all(x >= -60 for x in d), {'min':min(d),'max':max(d),'median':statistics.median(d),'mean':round(sum(d)/len(d),1)})
chk('block 1 timestamp >= daemon start_time and tip <= adjusted_time', ts[1] >= F[0]['info']['start_time'] and ts[-1] <= F[0]['info']['adjusted_time'], {'start':F[0]['info']['start_time'],'b1':ts[1],'tip':ts[-1],'adj':F[0]['info']['adjusted_time']})
chk('elapsed inside container consistent with 124 blocks near 90 s target', 124*60 < (ts[-1]-ts[1]) < 124*130, ts[-1]-ts[1])
diffs=[h['difficulty'] for h in H[0]]
print('difficulty samples h1,h10,h25,h50,h100,h124:', [diffs[i] for i in (1,10,25,50,100,124)])
print('block interval per 25: ', [round(sum(d[i:i+25])/len(d[i:i+25]),1) for i in range(0,len(d),25)])
fails=[k for k,v in out.items() if not v['ok']]
print('SUMMARY', 'PASS' if not fails else 'FAIL', 'checks=%d fails=%s' % (len(out), fails))
json.dump(out, open(sys.argv[2],'w'), indent=1)
