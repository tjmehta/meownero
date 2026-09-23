#!/usr/bin/env python3
"""Tamper controls for vanguard/verify.py: each case mutates a scratch copy of the evidence
(re-manifesting where needed so the deeper checks are reached) and must be refused."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
VERIFY = ROOT / 'vanguard/verify.py'


def remanifest(d):
    lines = [f'{hashlib.sha256(p.read_bytes()).hexdigest()}  ./{p.relative_to(d)}'
             for p in sorted(d.rglob('*')) if p.is_file() and p.name != 'MANIFEST.sha256']
    (d / 'MANIFEST.sha256').write_text('\n'.join(lines) + '\n')


def both_runs(d, edit):
    for run in ('run1', 'run2'):
        path = d / run / 'results.json'
        results = json.loads(path.read_text())
        edit(results)
        path.write_text(json.dumps(results))


def vector(results, vid):
    return next(v for v in results['vectors'] if v['id'] == vid)


def replace_in(d, name, old, new):
    (d / name).write_text((d / name).read_text().replace(old, new, 1))


def corrupt_address(results):
    v = vector(results, 'carrot.address.integrated.stagenet.round_trip')
    v['detail'] = v['detail'][:-1] + ('B' if v['detail'].endswith('A') else 'A')


# name, mutation, re-manifest after mutating, expected refusal text
CASES = [
    ('byte flip without re-manifest', lambda d: replace_in(d, 'run2/results.json', '"reject"', '"rejecT"'), False, 'hash mismatch'),
    ('run1 differs from run2', lambda d: replace_in(d, 'run2/results.json', '\n}\n', '\n} \n'), True, 'run1/run2 results differ'),
    ('finding misapplied', lambda d: both_runs(d, lambda r: vector(r, 'fcmp_pp.fixed_1in.truncated_1_byte').update(finding='VG-F1', observed='accept')), True, 'misapplied'),
    ('valid proof rejected', lambda d: both_runs(d, lambda r: vector(r, 'fcmp_pp.fixed_8in.valid').update(observed='reject_false')), True, 'expected accept'),
    ('address checksum altered', lambda d: both_runs(d, corrupt_address), True, 'checksum mismatch'),
    ('negative vector dropped', lambda d: both_runs(d, lambda r: r['vectors'].remove(vector(r, 'sal.wrong_key_image'))), True, 'summary'),
    ('rustc receipt changed', lambda d: replace_in(d, 'toolchain.txt', 'rustc 1.93.0 (', 'rustc 1.94.0 ('), True, 'rustc != pin'),
    ('harness source drift', lambda d: replace_in(d, 'harness-source.sha256', '  vanguard_tests.cpp', '0  vanguard_tests.cpp'), True, 'different harness source'),
    ('upstream head changed', lambda d: replace_in(d, 'upstream-head.txt', 'e151', 'e152'), True, 'upstream HEAD != pin'),
]


def main():
    evidence = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / 'research/evidence/vanguard-tjs356-2026-09-23')
    clean = subprocess.run([sys.executable, str(VERIFY), str(evidence)], capture_output=True, text=True).stdout.strip()
    if not clean.startswith('PASS_VANGUARD_RECEIPTS'):
        print(f'FAIL clean evidence does not verify: {clean}')
        return 1
    failed = 0
    for name, mutate, re_manifest, expected in CASES:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / 'evidence'
            shutil.copytree(evidence, work)
            mutate(work)
            if re_manifest:
                remanifest(work)
            out = subprocess.run([sys.executable, str(VERIFY), str(work)], capture_output=True, text=True).stdout.strip()
            ok = out.startswith('FAIL') and expected in out
            failed += not ok
            print(f"{'REFUSED' if ok else 'NOT_REFUSED'} {name}: {out[:120]}")
    print('PASS_VANGUARD_REFUSALS' if failed == 0 else f'FAIL {failed} tamper case(s) not refused')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
