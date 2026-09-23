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


def run_metrics(d, edit):
    for run in ('run1', 'run2'):
        path = d / run / 'metrics.json'
        metrics = json.loads(path.read_text())
        edit(metrics)
        path.write_text(json.dumps(metrics))


def drop_consistently(d, vid):
    """Drop a vector and rewrite the summary and stdout to match, so only the pinned vector set can catch it."""
    def edit(results):
        results['vectors'].remove(vector(results, vid))
        n = len(results['vectors'])
        results['summary'] = {'total': n, 'passed': n, 'known_findings': sum(1 for v in results['vectors'] if v['finding']), 'failed': 0}
    both_runs(d, edit)
    for run in ('run1', 'run2'):
        replace_in(d, f'{run}/stdout.log', 'vectors=187 failed=0', 'vectors=186 failed=0')


def corrupt_address(results):
    v = vector(results, 'carrot.address.integrated.stagenet.round_trip')
    v['detail'] = v['detail'][:-1] + ('B' if v['detail'].endswith('A') else 'A')


# name, mutation, re-manifest after mutating, expected refusal text
CASES = [
    ('byte flip without re-manifest', lambda d: replace_in(d, 'run2/results.json', '"reject"', '"rejecT"'), False, 'hash mismatch'),
    ('run1 differs from run2', lambda d: replace_in(d, 'run2/results.json', '\n}\n', '\n} \n'), True, 'run1/run2 results differ'),
    ('finding misapplied', lambda d: both_runs(d, lambda r: vector(r, 'fcmp_pp.fixed_1in.truncated_1_byte').update(finding='VG-F1', observed='accept')), True, 'vector set'),
    ('finding verdict altered', lambda d: both_runs(d, lambda r: vector(r, 'fcmp_pp.fixed_1in.wrong_n_layers_minus_1').update(observed='reject_abort_signal_11')), True, 'misapplied'),
    ('valid proof rejected', lambda d: both_runs(d, lambda r: vector(r, 'fcmp_pp.fixed_8in.valid').update(observed='reject_false')), True, 'expected accept'),
    ('address checksum altered', lambda d: both_runs(d, corrupt_address), True, 'checksum mismatch'),
    ('negative vector dropped', lambda d: both_runs(d, lambda r: r['vectors'].remove(vector(r, 'sal.wrong_key_image'))), True, 'vector set'),
    ('negative vector dropped with consistent summary', lambda d: drop_consistently(d, 'fcmp_pp.fixed_2in.wrong_n_layers_minus_1'), True, 'vector set'),
    ('negative vector relabelled as accept', lambda d: both_runs(d, lambda r: vector(r, 'fcmp_pp.fixed_2in.wrong_n_layers_minus_1').update(expect='accept', observed='accept')), True, 'vector set'),
    ('VG-F2 mark removed from a fixed vector', lambda d: both_runs(d, lambda r: vector(r, 'fcmp_pp.fixed_4in.wrong_n_layers_minus_1').update(finding='', observed='reject_false')), True, 'vector set'),
    ('crash on a non-finding vector', lambda d: both_runs(d, lambda r: vector(r, 'fcmp_pp.fixed_8in.wrong_tree_root').update(observed='reject_abort_signal_11')), True, 'expected reject, observed reject_abort_signal_11'),
    ('crash in raw metrics', lambda d: run_metrics(d, lambda m: m['random_input_observed'].update({'sal.wrong_key_image': 'reject_abort_signal_11'})), True, 'not permitted'),
    ('raw verdict disagrees with its class', lambda d: run_metrics(d, lambda m: m['random_input_observed'].update({'fcmp_pp.fresh_1in.valid': 'reject_false'})), True, 'does not reduce'),
    ('extra upstream injection diff line', lambda d: (d / 'upstream-injection.diff').write_text((d / 'upstream-injection.diff').read_text() + '-add_subdirectory(unit_tests)\n'), True, 'injection diff'),
    ('upstream vector hash changed', lambda d: replace_in(d, 'upstream-vectors.sha256', '649fc27f', '749fc27f'), True, 'upstream vector hashes'),
    ('grown-root rejection without growth', lambda d: both_runs(d, lambda r: vector(r, 'fcmp_pp.fresh_1in.old_root_proof_vs_grown_root').update(detail='grew_by=1 grow_ok=false')), True, 'did not grow'),
    ('implausible run wall time', lambda d: run_metrics(d, lambda m: m.update(total_wall_seconds=0.001)), True, 'section timings'),
    ('implausible run peak RSS', lambda d: run_metrics(d, lambda m: m.update(peak_rss_kib=1)), True, 'peak RSS'),
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
