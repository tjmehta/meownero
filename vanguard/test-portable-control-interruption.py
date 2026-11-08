#!/usr/bin/env python3
"""Regression: a cancellation delivered while the controls harness waits for its
live interruption fixture must export as that wait, not as a fixture launch error.

Runs the real harness as a POSIX subprocess against a disposable fake package
and delivers a real SIGTERM. This qualifies failure labelling only; it is not
native package or platform evidence.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent

# Refusal cases are dispatched by the copied package directory name, so every
# earlier control passes and the harness reaches its interruption fixtures.
FAKE_TESTER = r'''
import fcntl, os, sys, tempfile, time
from pathlib import Path
here = Path(__file__).resolve().parent
action = sys.argv[1]
reasons = {'wrong-pin': 'wrong source pin', 'wrong-target': 'wrong architecture',
           'changed-binary': 'package hash mismatch', 'unlisted-private-file': 'package file set mismatch',
           'symlink-directory': 'package symlink refused', 'hardlink': 'hard-linked input refused'}
if here.name in reasons:
    sys.stderr.write(reasons[here.name] + '\n'); sys.exit(1)
lock = Path(tempfile.gettempdir()) / ('meownero-vanguard-tester-' + str(os.getuid()) + '.lock')
stream = lock.open('a+b')
try:
    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    sys.stderr.write('tester busy\n'); sys.exit(1)
if action == 'preflight':
    sys.exit(0)
out = Path(sys.argv[sys.argv.index('--out') + 1])
if out.exists():
    sys.stderr.write('output must be new\n'); sys.exit(1)
out.mkdir()
(out / 'fake-started').write_text(str(os.getpid()))
if os.environ.get('FAKE_FIXTURE') == 'exit-early':
    sys.exit(3)
time.sleep(300)  # Never becomes live; only the harness's own cleanup stops it.
'''


def build_package(base):
    package = base / 'package'
    (package / 'bin').mkdir(parents=True)
    (package / 'bin/monerod').write_bytes(b'fixture')
    (package / 'release.json').write_text(json.dumps({'architecture': 'x86_64'}))
    (package / 'tester.py').write_text(FAKE_TESTER)
    return package


def scenario(harness, base, fixture, deliver):
    package = build_package(base / fixture)
    out = base / fixture / 'controls'
    private_tmp = base / fixture / 'tmp'
    private_tmp.mkdir()
    # A private TMPDIR keeps the fake busy lock off any real tester lock path.
    env = {**os.environ, 'TMPDIR': str(private_tmp), 'FAKE_FIXTURE': fixture}
    harness_process = subprocess.Popen([sys.executable, '-B', str(harness), '--package', str(package), '--out', str(out)],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
    started = out / 'cancelled' / 'fake-started'
    deadline = time.monotonic() + 60
    while not started.exists() and harness_process.poll() is None and time.monotonic() < deadline:
        time.sleep(0.05)
    assert started.exists(), 'harness never reached the cancellation fixture'
    fixture_pid = int(started.read_text())
    if deliver:
        time.sleep(0.3)  # Inside the bounded live-fixture poll; never past it.
        harness_process.send_signal(signal.SIGTERM)
    exit_code = harness_process.wait(timeout=90)
    receipt = json.loads((out / 'controls.json').read_text())
    try:
        os.kill(fixture_pid, 0)
        fixture_removed = False
    except ProcessLookupError:
        fixture_removed = True
    return {'exit': exit_code, 'first_failed_case': receipt.get('first_failed_case'),
            'cases_passed': len(receipt['cases']), 'fixture_removed': fixture_removed}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--harness', type=Path, default=ROOT / 'vanguard/test-portable-refusals.py')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    assert os.name == 'posix'
    results, failures = {}, []
    with tempfile.TemporaryDirectory(prefix='tjs1882-control-interruption-') as folder:
        base = Path(folder)
        results['cancel-during-live-wait'] = cancel = scenario(args.harness, base, 'never-live', deliver=True)
        results['fixture-exits-before-live'] = early = scenario(args.harness, base, 'exit-early', deliver=False)
    first = cancel['first_failed_case'] or {}
    checks = {
        'cancel_exit_nonzero': cancel['exit'] != 0,
        'cancel_earlier_controls_passed': cancel['cases_passed'] == 8,
        'cancel_case': first.get('case') == 'cancelled-owned-cleanup',
        'cancel_phase_is_wait': first.get('phase') == 'WAIT_LIVE_INTERRUPTION_FIXTURE',
        'cancel_not_launch_error': first.get('reason_enum') != 'INTERRUPTION_FIXTURE_LAUNCH_ERROR',
        'cancel_signal_recorded': first.get('interrupted_by_signal') == 'SIGTERM',
        'cancel_stamps_ordered': (first.get('case_started_monotonic', 0) <= first.get('fixture_spawned_monotonic', -1)
                                  <= first.get('interrupted_monotonic', -2)),
        'cancel_fixture_removed': cancel['fixture_removed'],
        'early_exit_reason': (early['first_failed_case'] or {}).get('reason_enum') == 'NATIVE_INTERRUPTION_FIXTURE_NOT_LIVE',
        'early_exit_not_marked_interrupted': 'interrupted_by_signal' not in (early['first_failed_case'] or {}),
        'early_fixture_removed': early['fixture_removed'],
    }
    failures = sorted(name for name, ok in checks.items() if not ok)
    report = {'schema': 'meownero-control-interruption-regression/1', 'harness': str(args.harness.name),
              'result': 'PASS' if not failures else 'FAIL', 'failed_checks': failures, 'checks': checks,
              'scenarios': results, 'evidence': 'SYNTHETIC_POSIX_FIXTURE_NOT_NATIVE_PACKAGE'}
    text = json.dumps(report, indent=2) + '\n'
    if args.out:
        args.out.write_text(text)
    print(text)
    return 0 if not failures else 1


if __name__ == '__main__':
    raise SystemExit(main())
