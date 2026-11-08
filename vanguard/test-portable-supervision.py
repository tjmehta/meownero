#!/usr/bin/env python3
"""Exercise real Linux exit/reaping races without a build or wallet workload."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

spec = importlib.util.spec_from_file_location('portable_supervisor', Path(__file__).with_name('run-portable-ci.py'))
supervisor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(supervisor)

WRAPPER = '''import os, signal, sys, time
stopping = False
def stop(number, frame):
    global stopping
    stopping = True
signal.signal(signal.SIGTERM, stop)
for _ in range(30):
    child = os.fork()
    if child == 0:
        os._exit(0)
    try:
        end = time.monotonic() + float(sys.argv[1])
        while not stopping and time.monotonic() < end:
            time.sleep(0.005)
    finally:
        os.waitpid(child, 0)
    if stopping:
        sys.exit(130)
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    assert platform.system() == 'Linux' and hasattr(os, 'fork')
    assert args.out.parent.is_dir() and not args.out.exists()
    args.out.mkdir(mode=0o700)
    wrapper = args.out / 'wrapper.py'
    wrapper.write_text(WRAPPER)
    rows = []
    # Its liveness proves that process-tree cleanup preserves unrelated work.
    unrelated = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
    try:
        for name, delay, failure in [('transient', '0.12', None),
                                     ('persistent', '1.5', 'UNVERIFIED_FIRST_ZOMBIE')]:
            private = args.out / name
            private.mkdir(mode=0o700)
            public = private / 'public'
            public.mkdir(mode=0o700)
            caught = None
            try:
                supervisor.mac_check([sys.executable, '-B', wrapper, delay], private, public,
                    timeout=10, cleanup_seconds=30, supervision_schema='meownero-linux-reaping-regression/1')
            except AssertionError as error:
                caught = str(error)
            receipt = json.loads((public / 'supervision.json').read_text())
            assert receipt['wrapper_reaped'] and all(row['removed'] for row in receipt['cleanup'])
            assert all(row['removed'] for row in receipt['rejected_observation_cleanup'])
            assert not receipt['signals'], 'unverified zombies must never authorize a cleanup signal'
            assert unrelated.poll() is None, 'unrelated process was disturbed'
            row = {'case': name, 'expected_failure': failure, 'actual_failure': caught,
                   'result': 'PASS' if caught == failure else 'FAIL',
                   'wrapper_reaped': True, 'unrelated_preserved': True,
                   'receipt': str((public / 'supervision.json').relative_to(args.out))}
            rows.append(row)
            if caught != failure:
                raise AssertionError(name + ': ' + str(caught))
            if failure is None:
                observations = receipt['unverified_observations']
                assert observations, 'fixture must actually observe an unverified zombie'
                assert all(row.get('absence_proof') == 'ACTUAL_PID_ABSENCE' for row in observations)
                assert receipt['result'] == 'PASS_WRAPPER_AND_OWNED_CLEANUP'
            else:
                assert receipt['result'] == 'FAIL'
    finally:
        unrelated.terminate()
        unrelated.wait(timeout=5)
        supervisor.write(args.out / 'result.json', {'cases': rows,
            'unrelated_fixture_reaped': unrelated.poll() is not None,
            'result': 'PASS' if len(rows) == 2 and all(row['result'] == 'PASS' for row in rows) else 'FAIL'})
    print('PASS_LINUX_REAPING_AND_PERSISTENT_ZOMBIE_REFUSAL')


if __name__ == '__main__':
    main()
