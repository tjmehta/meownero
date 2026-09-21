#!/usr/bin/env python3
"""Exercise sync.py's actual admission refusals (same cases as the accepted recipe) without starting nodes."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
CASES = {
    'wrong-genesis': ('genesis_hash', '11' * 32),
    'wrong-genesis-reward': ('genesis_reward_atomic', 1),
    'wrong-reward': ('reward_atomic', 12000000000000),
    'wrong-target': ('target_seconds', 120),
    'wrong-fork': ('fork', {'genesis_version': 1, 'version': 15, 'height': 1}),
    'wrong-fork-height': ('fork', {'genesis_version': 1, 'version': 16, 'height': 2}),
    'wrong-pool': ('pool_profile', 'stock-p2pool'),
    'pool-enabled': ('pool_enabled', True),
    'wrong-prefix': ('address_prefix', 18),
    'testnet-mode': ('network_mode', 'testnet'),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', required=True, type=Path)
    parser.add_argument('--binary', type=Path, default=ROOT / 'build/repro-selected-20260918/selected-9-90/first/source/build/release/bin/monerod')
    args = parser.parse_args()
    args.work.mkdir(parents=True)  # Refuse to overwrite earlier receipts.
    profile = json.loads((HERE / 'profile.json').read_text())
    results = []
    base = [sys.executable, '-B', str(HERE / 'sync.py'), '--binary', str(args.binary)]

    def check(name, cmd, wanted, expected_code=2):
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        (args.work / f'{name}.stdout.log').write_text(proc.stdout)
        (args.work / f'{name}.stderr.log').write_text(proc.stderr)
        (args.work / f'{name}.exit').write_text(str(proc.returncode) + '\n')
        row = {'case': name, 'command': cmd, 'exit': proc.returncode, 'expected_message': wanted}
        results.append(row)
        if proc.returncode != expected_code or wanted not in proc.stdout + proc.stderr:
            raise RuntimeError(row)

    for name, (field, value) in CASES.items():
        changed = copy.deepcopy(profile)
        changed[field] = value
        path = args.work / f'{name}.json'
        path.write_text(json.dumps(changed, indent=2) + '\n')
        output = args.work / f'{name}-output'
        check(name, base + ['--profile', str(path), '--work', str(output)], f'wrong {field} profile')
        assert not output.exists(), name
    stale = args.work / 'stale-data'
    stale.mkdir()
    (stale / 'sentinel').write_text('existing node data must survive\n')
    check('stale-data', base + ['--work', str(stale)], 'stale data/output directory refused')
    assert list(stale.iterdir()) == [stale / 'sentinel']
    assert (stale / 'sentinel').read_text() == 'existing node data must survive\n'
    wrong = args.work / 'wrong-binary'
    wrong.write_bytes(b'not the accepted executable\n')
    wrong_output = args.work / 'wrong-binary-output'
    check('wrong-binary', [sys.executable, '-B', str(HERE / 'sync.py'), '--binary', str(wrong), '--work', str(wrong_output)],
          'binary SHA-256 mismatch')
    assert not wrong_output.exists()
    check('accepted-control', base + ['--work', str(args.work / 'control-output'), '--check-only'],
          'PASS: accepted recipe manifest, profile, binary and baseline inputs verified', expected_code=0)
    assert not (args.work / 'control-output').exists()
    (args.work / 'result.json').write_text(json.dumps({'result': 'PASS', 'cases': results}, indent=2) + '\n')
    files = sorted(p for p in args.work.rglob('*') if p.is_file())
    (args.work / 'MANIFEST.sha256').write_text(''.join(
        f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(args.work)}\n' for p in files))
    print(f'PASS: {len(results) - 1} admission refusals and accepted-input control; no nodes started')


if __name__ == '__main__':
    main()
