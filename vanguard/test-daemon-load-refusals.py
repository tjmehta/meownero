#!/usr/bin/env python3
"""Hash-consistent load receipt controls; never edits the source bundle."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
VERIFIER = ROOT / 'vanguard/verify-daemon-load.py'


def manifest(out):
    (out / 'MANIFEST.sha256').write_text(''.join(
        f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(out)}\n'
        for p in sorted(out.rglob('*')) if p.is_file() and p.name != 'MANIFEST.sha256'))


def check(out, src):
    return subprocess.run(['python3', '-B', str(VERIFIER), str(out), '--src', str(src)],
                          capture_output=True, text=True)


def copy_public(source, target):
    target.mkdir()
    for line in (source / 'MANIFEST.sha256').read_text().splitlines():
        _, relative = line.split('  ', 1)
        dest = target / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / relative, dest)
    shutil.copy2(source / 'MANIFEST.sha256', target / 'MANIFEST.sha256')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('out', type=Path)
    parser.add_argument('--src', type=Path, required=True)
    parser.add_argument('--scratch', type=Path, required=True)
    args = parser.parse_args()
    source, src = args.out.resolve(), args.src.resolve()
    args.scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='vanguard-load-refusals-', dir=args.scratch) as temp:
        base = Path(temp)
        clean = check(source, src)
        assert clean.returncode == 0, clean.stderr

        forged_binary = base / 'forged-src/monero-fcmp/build/vanguard/bin'
        forged_binary.mkdir(parents=True)
        (forged_binary / 'monerod').write_bytes(b'wrong executable')
        shutil.copy2(src / 'monero-fcmp/build/vanguard/bin/monero-wallet-rpc',
                     forged_binary / 'monero-wallet-rpc')
        invalid = check(source, base / 'forged-src')
        assert invalid.returncode != 0 and 'local executable bytes: monerod' in invalid.stderr
        print('REFUSED wrong executable bytes: local executable bytes: monerod')

        tampered = base / 'invalid-proof-response'
        copy_public(source, tampered)
        result_path = tampered / 'run1/public/result.json'
        result = json.loads(result_path.read_text())
        result['controls']['invalid_proof']['responses'][0]['status'] = 'OK'
        result_path.write_text(json.dumps(result, indent=2) + '\n')
        manifest(tampered)
        invalid = check(tampered, src)
        assert invalid.returncode != 0 and 'invalid_proof refusal' in invalid.stderr
        print('REFUSED hash-consistent invalid-proof acceptance: invalid_proof refusal')

        # This intentionally demonstrates the post-run authenticity limit.
        tampered = base / 'equal-wrong-tips'
        copy_public(source, tampered)
        result_path = tampered / 'run1/public/result.json'
        event_path = tampered / 'run1/public/events.jsonl'
        result = json.loads(result_path.read_text())
        wrong = list(result['baseline']['tips'][0])
        wrong[1] = '0' * 64 if wrong[1] != '0' * 64 else '1' * 64
        result['baseline']['tips'] = [wrong, list(wrong)]
        result_path.write_text(json.dumps(result, indent=2) + '\n')
        rows = [json.loads(line) for line in event_path.read_text().splitlines()]
        next(row for row in rows if row['event'] == 'idle_baseline')['metric'] = result['baseline']
        event_path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        manifest(tampered)
        unverified = check(tampered, src)
        assert unverified.returncode == 0 and 'UNVERIFIED_LIVE_TIPS' in unverified.stdout
        print('UNVERIFIED hash-consistent equal-wrong idle tips pass receipt checks')


if __name__ == '__main__':
    main()
