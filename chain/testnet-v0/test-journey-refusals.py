#!/usr/bin/env python3
"""Exercise journey.py's actual admission refusals (accepted recipe cases, every pinned executable, busy lock) without starting nodes."""
import argparse
import copy
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
BINDIR = ROOT / 'build/repro-selected-20260918/selected-9-90/first/source/build/release/bin'
POOL = ROOT / 'build/tjs187-port-20260920/source/build-local/p2pool'
LOCK = '/tmp/meownero-swarm-20260912-heavy.lock'
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
CONTROL = 'PASS: five accepted recipe admissions, profile, binaries, builder image and baseline inputs verified'
STEP_DIRS = ['01-launch', '02-payment', '03-sync', '04-recover', '05-pool-restart']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', required=True, type=Path)
    parser.add_argument('--binary', type=Path, default=BINDIR / 'monerod')
    parser.add_argument('--wallet', type=Path, default=BINDIR / 'monero-wallet-rpc')
    parser.add_argument('--pool', type=Path, default=POOL)
    args = parser.parse_args()
    args.work.mkdir(parents=True)  # Refuse to overwrite earlier receipts.
    profile = json.loads((HERE / 'profile.json').read_text())
    results = []
    recipe = [sys.executable, '-B', str(HERE / 'journey.py')]
    pins = ['--binary', str(args.binary), '--wallet', str(args.wallet), '--pool', str(args.pool)]
    base = recipe + pins

    def check(name, cmd, wanted, expected_code=2):
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
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
    for name, flag, message, content in [('wrong-binary', '--binary', 'binary SHA-256 mismatch', b'not the accepted executable\n'),
                                         ('wrong-wallet', '--wallet', 'wallet SHA-256 mismatch', b'not the accepted wallet executable\n'),
                                         ('wrong-pool-binary', '--pool', 'pool binary SHA-256 mismatch', b'not the candidate pool executable\n')]:
        wrong = args.work / name
        wrong.write_bytes(content)
        output = args.work / f'{name}-output'
        replaced = [str(wrong) if pins[i - 1] == flag else v for i, v in enumerate(pins)]
        check(name, recipe + replaced + ['--work', str(output)], message)
        assert not output.exists(), name
    # Busy lock: admission passes, the journey probes the shared lock, records BLOCKED and starts no step.
    with open(LOCK, 'a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('shared heavy lock busy; the busy-lock case cannot be exercised now')
        try:
            blocked = args.work / 'busy-lock-output'
            check('busy-lock', base + ['--work', str(blocked)], 'BLOCKED: shared heavy lock busy', expected_code=75)
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
    assert json.loads((blocked / 'result.json').read_text())['result'] == 'BLOCKED'
    assert json.loads((blocked / 'lock-probe.json').read_text())['busy'] is True
    assert not any((blocked / step).exists() for step in STEP_DIRS)
    assert (blocked / 'launcher.exit').read_text().strip() == '75'
    check('accepted-control', base + ['--work', str(args.work / 'control-output'), '--check-only'], CONTROL, expected_code=0)
    assert not (args.work / 'control-output').exists()
    (args.work / 'result.json').write_text(json.dumps({'result': 'PASS', 'cases': results}, indent=2) + '\n')
    files = sorted(p for p in args.work.rglob('*') if p.is_file())
    (args.work / 'MANIFEST.sha256').write_text(''.join(
        f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(args.work)}\n' for p in files))
    print(f'PASS: {len(results) - 1} admission refusals and accepted-input control; no nodes started')


if __name__ == '__main__':
    main()
