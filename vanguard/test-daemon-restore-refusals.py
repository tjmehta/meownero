#!/usr/bin/env python3
"""Hash-consistent negative controls for the daemon restore receipt verifier."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
VERIFY = ROOT / 'vanguard/verify-daemon-restore.py'
DEFAULT_EVIDENCE = ROOT / 'research/evidence/vanguard-daemon-restore-tjs1010-2026-09-29'


def rehash(work):
    (work / 'MANIFEST.sha256').write_text(''.join(
        f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(work)}\n'
        for path in sorted(work.rglob('*'))
        if path.is_file() and path.name != 'MANIFEST.sha256'))


def mutate_binary(work, name):
    path = work / 'receipt.json'
    receipt = json.loads(path.read_text())
    receipt['binary'][name]['sha256'] = '0' * 64
    path.write_text(json.dumps(receipt, indent=2) + '\n')


def mutate_tip(work, stage):
    path = work / 'run1/public/result.json'
    result = json.loads(path.read_text())
    result[stage]['tips'][1][1] = '0' * 64
    path.write_text(json.dumps(result, indent=2) + '\n')
    path = work / 'run1/public/events.jsonl'
    events = [json.loads(row) for row in path.read_text().splitlines()]
    event_name = 'restored_spend_' + stage
    for event in events:
        if event['event'] == event_name:
            event['state']['tips'][1][1] = '0' * 64
    path.write_text(''.join(json.dumps(event, separators=(',', ':')) + '\n'
                            for event in events))


def mutate_final_tip(work):
    path = work / 'run1/public/result.json'
    result = json.loads(path.read_text())
    result['final_tip'][1] = '0' * 64
    path.write_text(json.dumps(result, indent=2) + '\n')


def mutate_confirmed_event_block(work):
    path = work / 'run1/public/events.jsonl'
    events = [json.loads(row) for row in path.read_text().splitlines()]
    for event in events:
        if event['event'] == 'restored_spend_confirmed':
            event['block'] = '0' * 64
    path.write_text(''.join(json.dumps(event, separators=(',', ':')) + '\n'
                            for event in events))


def run_verifier(work):
    return subprocess.run([sys.executable, '-B', str(VERIFY), str(work)],
                          capture_output=True, text=True)


def main():
    source = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_EVIDENCE
    clean = run_verifier(source)
    if clean.returncode or 'PASS_DAEMON_RESTORE_RECEIPT_RECONCILIATION' not in clean.stdout:
        raise AssertionError(f'clean receipt failed: {clean.stdout}{clean.stderr}')
    cases = (
        ('monerod-hash', lambda work: mutate_binary(work, 'monerod'),
         'binary pin mismatch: monerod'),
        ('wallet-rpc-hash', lambda work: mutate_binary(work, 'monero-wallet-rpc'),
         'binary pin mismatch: monero-wallet-rpc'),
        ('confirmed-tip', lambda work: mutate_tip(work, 'confirmed'),
         'cross-daemon tip divergence'),
        ('pooled-tip', lambda work: mutate_tip(work, 'pooled'),
         'cross-daemon tip divergence'),
        ('final-tip', mutate_final_tip, 'final tip/confirmed snapshot mismatch'),
        ('confirmed-event-block', mutate_confirmed_event_block,
         'final tip/confirmed event mismatch'),
    )
    scratch = os.environ.get('PAPERCLIP_RUN_SCRATCH_DIR') or os.environ.get('PAPERCLIP_SCRATCH_DIR')
    with tempfile.TemporaryDirectory(dir=scratch) as directory:
        for name, mutate, expected in cases:
            work = Path(directory) / name
            shutil.copytree(source, work)
            mutate(work)
            rehash(work)
            rejected = run_verifier(work)
            if rejected.returncode == 0 or expected not in rejected.stderr:
                raise AssertionError(f'{name} was not refused: {rejected.stdout}{rejected.stderr}')
            print(f'EXPECTED_REFUSAL {name}: {expected}')
    print('PASS_DAEMON_RESTORE_HASH_CONSISTENT_REFUSALS')


if __name__ == '__main__':
    main()
