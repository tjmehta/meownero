#!/usr/bin/env python3
"""Hash-consistent negative control for the native P2P reorg verifier."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = ROOT / 'research/evidence/vanguard-daemon-p2p-tjs996-2026-09-29'
VERIFY = ROOT / 'vanguard/verify-daemon-p2p.py'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else EVIDENCE
    clean = subprocess.run([sys.executable, '-B', str(VERIFY), str(source)],
                           capture_output=True, text=True)
    if clean.returncode or 'PASS_DAEMON_P2P_RECEIPT_RECONCILIATION' not in clean.stdout:
        raise AssertionError(f'clean evidence failed: {clean.stdout}{clean.stderr}')
    scratch = os.environ.get('PAPERCLIP_RUN_SCRATCH_DIR') or os.environ.get('PAPERCLIP_SCRATCH_DIR')
    with tempfile.TemporaryDirectory(dir=scratch) as tmp:
        work = Path(tmp) / 'evidence'
        shutil.copytree(source, work)
        for run in sorted(work.glob('run*/public')):
            result_path = run / 'result.json'
            result = json.loads(result_path.read_text())
            result['rolled_back']['key_images'] = [0, 0]
            result['rolled_back']['pools'] = [[], []]
            result_path.write_text(json.dumps(result, indent=2) + '\n')
            events_path = run / 'events.jsonl'
            events = [json.loads(row) for row in events_path.read_text().splitlines()]
            for event in events:
                if event['event'] == 'reorg_key_image_rollback':
                    event['state'] = result['rolled_back']
            events_path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in events))
        (work / 'MANIFEST.sha256').write_text(''.join(
            f'{sha(path)}  {path.relative_to(work)}\n' for path in sorted(work.rglob('*'))
            if path.is_file() and 'private' not in path.parts and path.name != 'MANIFEST.sha256'))
        rejected = subprocess.run([sys.executable, '-B', str(VERIFY), str(work)],
                                  capture_output=True, text=True)
        if rejected.returncode == 0 or 'key image chain-state transition' not in rejected.stderr:
            raise AssertionError(f'hash-consistent unspent rollback was not refused: '
                                 f'{rejected.stdout}{rejected.stderr}')
    print('PASS_DAEMON_P2P_HASH_CONSISTENT_REFUSAL')


if __name__ == '__main__':
    main()
