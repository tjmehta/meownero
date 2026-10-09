#!/usr/bin/env python3
"""Native ownership/cleanup fault controls on the supported idle build-mac runtime."""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch
import uuid

spec = importlib.util.spec_from_file_location('tester', Path(__file__).with_name('tester.py'))
tester = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tester)


def inspect(identity):
    return tester.command(tester.docker('inspect', identity), timeout=20)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    tester.supported_host()
    tester.preflight(Path(tester.PROFILE['cache']))
    work = tester.fresh(args.work)
    work.mkdir(mode=0o700)
    results = []

    # Freeze only the child's invocation ID to reproduce a genuine stopped-name collision.
    invocation = uuid.uuid4().hex
    name = f'tjs1870-{invocation}-p2p-build'
    identity = None
    child = None
    try:
        with tester.heavy_lock():
            tester.require(not tester.command(tester.docker('ps', '-q')), 'Docker busy')
            identity = tester.command(tester.docker('create', '--name', name, '--pull=never',
                '--network=none', '--cap-drop=ALL', '--security-opt=no-new-privileges',
                '--label', 'tester.fixture=' + invocation, tester.PROFILE['image'], 'true'))
        before = inspect(identity)
        code = '''import importlib.util,sys,uuid
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('tester',Path('vanguard/tester.py'))
t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
with patch.object(t.uuid,'uuid4',return_value=uuid.UUID(sys.argv[1])):
 try:t.run(Path(t.PROFILE['cache']),Path(sys.argv[2]))
 except Exception as e:print(type(e).__name__,str(e));sys.exit(1)
'''
        child = subprocess.Popen([sys.executable, '-B', '-c', code, invocation, str(work / 'collision')],
                                 cwd=tester.ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = child.communicate(timeout=180)
        after = inspect(identity)
        cleanup = tester.read(work / 'collision/cleanup.json')
        tester.require(child.returncode != 0 and 'collision refused' in stdout and before == after,
                       'collision deleted or changed unowned container')
        tester.require(len(cleanup) == 1 and cleanup[0]['container_id'] is None and
                       cleanup[0]['stop_exit'] is None and cleanup[0]['remove_exit'] is None,
                       'collision attempted destructive cleanup')
        results.append({'control': 'pre-existing stopped container collision', 'result': 'PASS_REFUSAL',
                        'fixture_id': identity, 'fixture_unchanged': True, 'run_exit': child.returncode,
                        'cleanup': cleanup})
    finally:
        if child is not None and child.poll() is None:
            child.kill(); child.wait(timeout=10)
        if identity is not None:
            tester.command(tester.docker('rm', identity), timeout=20)
            tester.require(not tester.command(tester.docker('ps', '-aq', '--no-trunc', '--filter', 'id=' + identity)),
                           'owned collision fixture cleanup failed')

    # A foreign cidfile ID also needs the invocation label; no mutation is authorized.
    with tester.heavy_lock():
        tester.require(not tester.command(tester.docker('ps', '-q')), 'Docker busy')
        identity = tester.command(tester.docker('create', '--pull=never', '--network=none',
            '--label', 'tester.fixture=' + invocation, tester.PROFILE['image'], 'true'))
        try:
            cidfile = work / 'foreign.cid'
            cidfile.write_text(identity + '\n')
            before = inspect(identity)
            try:
                tester.owned_identity(cidfile, invocation)
            except RuntimeError as error:
                tester.require('ownership mismatch' in str(error), 'wrong ownership refusal')
            else:
                raise RuntimeError('foreign container identity accepted')
            tester.require(inspect(identity) == before, 'foreign ownership check changed container')
            results.append({'control': 'foreign invocation label', 'result': 'PASS_REFUSAL',
                            'fixture_id': identity, 'fixture_unchanged': True})
        finally:
            tester.command(tester.docker('rm', identity), timeout=20)

    original = subprocess.run
    for operation in ('stop', 'inspect'):
        out = work / (operation + '-timeout')
        injected = []
        removals = []

        def fault(argv, *args, **kwargs):
            # Only the post-stop State inspection; ownership validation stays real.
            match = (argv[:4] == tester.docker('stop') if operation == 'stop' else
                     argv[:4] == tester.docker('inspect') and '{{json .State}}' in argv)
            if match:
                injected.append({'operation': operation, 'timeout_seconds': kwargs['timeout']})
                raise subprocess.TimeoutExpired(argv, kwargs['timeout'])
            if argv[:4] == tester.docker('rm'):
                removals.append(argv[-1])
            return original(argv, *args, **kwargs)

        error = None
        try:
            with patch.object(tester.subprocess, 'run', side_effect=fault):
                tester.run(Path(tester.PROFILE['cache']), out)
        except RuntimeError as caught:
            error = str(caught)
        rows = tester.read(out / 'cleanup.json')
        tester.require(error is not None and len(injected) == 1 and len(rows) == 1,
                       'fault did not propagate or cleanup evidence absent')
        row = rows[0]
        tester.require(row['container_id'] in removals and row['container_absent'] is True and
                       row['remove_exit'] == 0 and row['absence_exit'] == 0 and
                       {'operation': operation, 'error': 'TimeoutExpired'} in row['errors'],
                       'removal skipped after cleanup timeout')
        tester.require(tester.read(out / 'result.json')['result'] == 'FAIL', 'fault output falsely passed')
        results.append({'control': operation + ' transport timeout injection', 'result': 'PASS_REFUSAL',
                        'injected': injected, 'run_error': error, 'cleanup': rows,
                        'fault_output': str(out), 'removal_attempted': True})

    tester.write(work / 'controls.json', results)
    print('PASS_NATIVE_TESTER_CLEANUP', len(results))


if __name__ == '__main__':
    main()
