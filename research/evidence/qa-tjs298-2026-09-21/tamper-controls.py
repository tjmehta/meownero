#!/usr/bin/env python3
"""TJS-298 QA: negative controls for verify-pool-restart.py on re-signed COPIES of a receipt directory.
Each case copies the receipts, applies one edit, re-signs EVIDENCE.sha256 (except the unsigned cases), runs the verifier
and records exit + last line. Usage: tamper-controls.py <receipts> <scratch> <out.json>"""
import hashlib, json, shutil, subprocess, sys
from pathlib import Path
SRC, SCRATCH, OUT = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
VERIFY = Path('chain/testnet-v0/verify-pool-restart.py')
def J(d, n): return json.loads((d / n).read_text())
def W(d, n, v): (d / n).write_text(json.dumps(v, indent=2, sort_keys=True) + '\n')
def resign(d):
    files = sorted(p for p in d.iterdir() if p.is_file() and p.name != 'EVIDENCE.sha256')
    (d / 'EVIDENCE.sha256').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n' for p in files))
def edit_witness(f):
    def g(d):
        w = J(d, 'pool-restart.json'); f(w); W(d, 'pool-restart.json', w)
    return g
def edit(name, f):
    def g(d):
        v = J(d, name); f(v); W(d, name, v)
    return g
def zmq_off(c):
    i = c['peer1'].index('--zmq-rpc-bind-ip'); c['peer1'][i:i + 6] = ['--no-zmq']
CASES = {
    'faithful': (lambda d: None, 0, 'PASS_RECEIPT_RECONCILIATION'),
    # the writer's ten named tampers + unsigned
    'resumed-job-height': (edit_witness(lambda w: w['resumed']['job'].__setitem__('height', w['resumed']['job']['height'] - 1)), 1, 'resumed: job is not on the common tip'),
    'resumed-prev-hash': (edit_witness(lambda w: w['resumed']['job'].__setitem__('prev_hash', w['tip_at_stop']['hash'])), 1, 'resumed: job is not on the common tip'),
    'api-tip-stale': (edit_witness(lambda w: w['resumed']['api']['network'].update(hash=w['tip_at_stop']['hash'], height=w['tip_at_stop']['height'])), 1, 'resumed: pool API tip'),
    'pool-found-block': (edit_witness(lambda w: w['resumed']['api']['pool']['pool_statistics'].__setitem__('totalBlocksFound', 1)), 1, 'resumed: pool found blocks'),
    'pool-exit-1': (edit_witness(lambda w: w.__setitem__('pool_exit_code', 1)), 1, 'pool stopped cleanly at the live tip'),
    'zero-blocks-missed': (edit_witness(lambda w: w.__setitem__('blocks_missed', 0)), 1, 'blocks mined while the pool was down'),
    'restart-command-changed': (edit('process-commands.json', lambda c: c['pool-restart'].append('--no-color')), 1, 'restart must reuse the exact pool command'),
    'pool-mining-flag': (edit('process-commands.json', lambda c: (c['pool'].append('--start-mining'), c['pool-restart'].append('--start-mining'))), 1, 'pool must not mine, merge-mine, proxy or carry credentials'),
    'peer1-submit-block': (edit('rpc-methods.json', lambda m: m['peer1'].__setitem__('submit_block', 1)), 1, 'peer1 received a block-injecting or mining RPC'),
    'peer1-no-zmq': (edit('process-commands.json', zmq_off), 1, 'daemons must run the exact recipe commands'),
    'unsigned-edit': ('UNSIGNED', 1, 'changed receipt: pool-restart.json'),
    'manifest-removed': ('NOMANIFEST', 1, 'EVIDENCE.sha256'),
    # QA extras
    'header-link-break': (edit('headers.json', lambda h: [c.__getitem__(3).__setitem__('prev_hash', '00' * 32) for c in h]), 1, 'header link'),
    'final-tip-hash': (edit('headers.json', lambda h: [c[-1].__setitem__('hash', 'ff' * 32) for c in h]), 1, 'RPC tip'),
    'rpc-final-height': (edit('rpc-final.json', lambda f: f[0]['info'].__setitem__('height', f[0]['info']['height'] + 1)), 1, 'height/target'),
    'seed-epoch': (edit_witness(lambda w: w['resumed']['job'].__setitem__('seed_hash', '11' * 32)), 1, 'RandomX seed epoch changed within the witness'),
    'network-host': (edit('container-command.json', lambda c: c.__setitem__(c.index('--network') + 1, 'host')), 1, 'container network isolation'),
    'memory-cap': (edit('resources.json', lambda r: r.__setitem__('memory.max', '8589934592\n')), 1, 'memory/swap cap'),
    'result-fail': (edit('result.json', lambda r: r.__setitem__('result', 'FAIL')), 1, 'journey did not pass on the pinned pool'),
    'peer0-generateblocks': (edit('rpc-methods.json', lambda m: m['peer0'].__setitem__('generateblocks', 1)), 1, 'peer0 write RPC beyond native mining'),
    'no-p2p-traffic': (edit('peers-after.json', lambda p: [c.__setitem__('recv_count', 0) for n in p for c in n['connections']]), 1, 'P2P traffic'),
    'live-blocks-short': (edit_witness(lambda w: w.__setitem__('live_blocks', 1)), 1, 'live blocks while the pool ran'),
    'pool-log-block-found': (lambda d: (d / 'pool.log').open('a').write('NOTICE BLOCK FOUND: main chain block\n'), 1, 'the pool submitted or found a block'),
    'pool-binary-pin': (lambda d: (d / 'BINARY.sha256').write_text((d / 'BINARY.sha256').read_text().replace('bbc32406', 'deadbeef')), 1, 'pool binary pin'),
    'wallet-address': (edit('process-commands.json', lambda c: [c[k].__setitem__(c[k].index('--wallet') + 1, 'M' + 'A' * 94) for k in ('pool', 'pool-restart')]), 1, 'pool pays the public fixture address'),
    'attach-after-chain-moved': (edit_witness(lambda w: w['tip_at_attach'].__setitem__('hash', w['tip_after_live']['hash'])), 1, 'tip is not on the final chain'),
    'phase-minimum': (edit('result.json', lambda r: r['phases'].__setitem__('initial_blocks', 1)), 1, 'at least seven mined blocks required'),
}
out = {}
for name, (fn, want_exit, want_text) in CASES.items():
    d = SCRATCH / name
    shutil.copytree(SRC, d)
    if fn == 'UNSIGNED':
        w = J(d, 'pool-restart.json'); w['blocks_missed'] = 0; W(d, 'pool-restart.json', w)
    elif fn == 'NOMANIFEST':
        (d / 'EVIDENCE.sha256').unlink()
    else:
        fn(d); resign(d)
    p = subprocess.run([sys.executable, '-B', str(VERIFY), str(d)], capture_output=True, text=True)
    last = (p.stderr.strip().splitlines() or p.stdout.strip().splitlines() or [''])[-1]
    ok = p.returncode == want_exit and want_text in (p.stdout + p.stderr)
    out[name] = {'exit': p.returncode, 'last_line': last, 'expected': want_text, 'as_expected': ok}
    print(f"{'ok ' if ok else 'UNEXPECTED'} {name:26s} exit={p.returncode} {last[:100]}")
OUT.write_text(json.dumps(out, indent=2, sort_keys=True) + '\n')
n = sum(1 for v in out.values() if v['as_expected'])
print(f'RESULT {n}/{len(out)} controls behaved as expected')
sys.exit(0 if n == len(out) else 1)
