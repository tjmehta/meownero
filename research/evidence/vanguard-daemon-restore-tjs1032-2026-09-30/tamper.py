#!/usr/bin/env python3
"""Reproduce required receipt/bundle tamper controls and two verifier gaps."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
VERIFY = ROOT / 'vanguard/verify-daemon-restore.py'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rehash(work):
    (work / 'MANIFEST.sha256').write_text(''.join(
        f'{sha(path)}  {path.relative_to(work)}\n' for path in sorted(work.rglob('*'))
        if path.is_file() and path.name != 'MANIFEST.sha256'))


def main():
    source, destination = map(Path, sys.argv[1:3])
    scratch = Path(os.environ.get('PAPERCLIP_RUN_SCRATCH_DIR') or
                   os.environ.get('PAPERCLIP_SCRATCH_DIR') or ROOT / 'build')
    scratch.mkdir(parents=True, exist_ok=True)
    results = []
    with tempfile.TemporaryDirectory(dir=scratch) as directory:
        for case in ('receipt-rehashed', 'bundle-file', 'binary-hash-rehashed',
                     'divergent-confirmed-tips-rehashed'):
            work = Path(directory) / case
            shutil.copytree(source, work)
            if case == 'receipt-rehashed':
                path = work / 'receipt.json'
                receipt = json.loads(path.read_text())
                receipt['source_sha256']['vanguard/daemon-restore.py'] = '0' * 64
                path.write_text(json.dumps(receipt, indent=2) + '\n')
                rehash(work)
            elif case == 'bundle-file':
                path = work / 'run1/public/result.json'
                path.write_bytes(path.read_bytes() + b'\n')
            elif case == 'binary-hash-rehashed':
                path = work / 'receipt.json'
                receipt = json.loads(path.read_text())
                receipt['binary']['monerod']['sha256'] = '0' * 64
                path.write_text(json.dumps(receipt, indent=2) + '\n')
                rehash(work)
            else:
                path = work / 'run1/public/result.json'
                result = json.loads(path.read_text())
                result['confirmed']['tips'][1][1] = '0' * 64
                path.write_text(json.dumps(result, indent=2) + '\n')
                path = work / 'run1/public/events.jsonl'
                events = [json.loads(row) for row in path.read_text().splitlines()]
                for event in events:
                    if event['event'] == 'restored_spend_confirmed':
                        event['state']['tips'][1][1] = '0' * 64
                path.write_text(''.join(json.dumps(event, separators=(',', ':')) + '\n'
                                        for event in events))
                rehash(work)
            command = ['python3', '-B', str(VERIFY), str(work)]
            process = subprocess.run(command, capture_output=True, text=True)
            results.append({'case': case, 'exit': process.returncode,
                            'stdout': process.stdout.strip(),
                            'stderr_tail': process.stderr.strip().splitlines()[-1]
                            if process.stderr.strip() else ''})
    assert results[0]['exit'] != 0 and 'exact-commit source mismatch' in results[0]['stderr_tail']
    assert results[1]['exit'] != 0 and 'manifest mismatch' in results[1]['stderr_tail']
    assert all(row['exit'] == 0 and row['stdout'] ==
               'PASS_DAEMON_RESTORE_RECEIPT_RECONCILIATION' for row in results[2:])
    destination.write_text(json.dumps(results, indent=2) + '\n')
    print('PASS_TJS1032_TAMPER_CONTROLS_AND_VERIFIER_GAPS')


if __name__ == '__main__':
    main()
