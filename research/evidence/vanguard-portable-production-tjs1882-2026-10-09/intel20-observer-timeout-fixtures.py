"""Force real bounded owned subprocess timeouts through the exact supervisor.

Only the observer subprocess is substituted. No wallet or native Intel claim.
"""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

root = Path(__file__).resolve().parents[3]
sources = {'original14': root / 'build/tjs1882-3175-native-ci-payload14/vanguard/run-portable-ci.py',
           'corrected20': root / 'build/tjs1882-3175-intel20-supervisor.py'}
cases = []
with tempfile.TemporaryDirectory(prefix='tjs1882-intel20-timeout-') as tmp:
    for version, mode in [('original14', 'initial'), ('corrected20', 'initial'),
                          ('corrected20', 'live'), ('corrected20', 'cleanup'),
                          ('corrected20', 'live-and-cleanup')]:
        source = sources[version]
        spec = importlib.util.spec_from_file_location(version, source)
        ci = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ci)
        out = Path(tmp) / (version + '-' + mode)
        out.mkdir(mode=0o700)
        public = out / 'public'
        public.mkdir(mode=0o700)
        worker = out / 'PRIVATE_ARGUMENT_SENTINEL.py'
        worker.write_text('import time\ntime.sleep(' + ('.15' if mode == 'cleanup' else '15') + ')\n')
        original_output, original_popen = subprocess.check_output, subprocess.Popen
        wrappers, observer_helpers, observations, injected = [], [], [], []

        def popen(*args, **kwargs):
            child = original_popen(*args, **kwargs)
            if str(worker) in args[0]:
                wrappers.append(child)
            elif 'import time;time.sleep(30)' in args[0]:
                observer_helpers.append(child)
            return child

        def output(argv, **kwargs):
            if argv[:2] != ['/bin/ps', '-axo']:
                return original_output(argv, **kwargs)
            observations.append(True)
            cleaning = wrappers and wrappers[0].poll() is not None
            force = ((mode == 'initial' and len(observations) == 1) or
                     (mode in ('live', 'live-and-cleanup') and len(observations) == 2) or
                     (mode in ('cleanup', 'live-and-cleanup') and cleaning and
                      len(injected) < (2 if mode == 'live-and-cleanup' else 1)))
            if force:
                injected.append(True)
                # The actual standard-library timeout must kill and reap its own
                # child. Five seconds and all supervisor ownership code unchanged.
                return original_output([sys.executable, '-B', '-c', 'import time;time.sleep(30)'], **kwargs)
            return original_output(argv, **kwargs)

        before = {number: signal.getsignal(number) for number in (signal.SIGTERM, signal.SIGINT)}
        mask = signal.pthread_sigmask(signal.SIG_BLOCK, set())
        subprocess.check_output, subprocess.Popen = output, popen
        began = time.monotonic()
        try:
            try:
                ci.mac_check([sys.executable, '-B', worker], out, public, timeout=30, cleanup_seconds=25)
            except subprocess.TimeoutExpired:
                pass
            else:
                raise AssertionError('injected owned timeout must fail closed')
        finally:
            subprocess.check_output, subprocess.Popen = original_output, original_popen
            for child in wrappers + observer_helpers:
                if child.poll() is None:
                    child.kill()
                child.wait(timeout=5)
        receipt = json.loads((public / 'supervision.json').read_text())
        assert receipt['result'] == 'FAIL' and receipt['wrapper_reaped']
        assert receipt.get('cleanup_failure_type' if mode == 'cleanup' else 'failure_type') == 'TimeoutExpired'
        assert {number: signal.getsignal(number) for number in before} == before
        assert signal.pthread_sigmask(signal.SIG_BLOCK, set()) == mask
        assert all(child.poll() is not None for child in observer_helpers)
        for child in observer_helpers:
            try:
                os.kill(child.pid, 0)
            except ProcessLookupError:
                continue
            raise AssertionError('owned timeout helper has not actually disappeared')
        assert 'PRIVATE_ARGUMENT_SENTINEL' not in json.dumps(receipt)
        expected = ('INITIAL_OBSERVATION' if mode == 'initial' else
                    'OWNED_CLEANUP' if mode == 'cleanup' else 'LIVE_OBSERVATION')
        if version == 'corrected20':
            events = receipt['snapshot_timeouts']
            assert events[0]['context'] == expected
            assert events[0]['operation'] == 'OWNED_PROCESS_SNAPSHOT'
            assert events[0]['timeout_seconds'] == 5 and 4.8 <= events[0]['elapsed_seconds'] < 8
            if mode != 'cleanup':
                assert receipt['failure_operation'] == 'OWNED_PROCESS_SNAPSHOT'
                assert receipt['failure_context'] == expected
                assert receipt['failure_timeout_seconds'] == 5
                assert receipt['failure_reason'] == 'PROCESS_SNAPSHOT_DEADLINE'
            if mode == 'live-and-cleanup':
                assert events[-1]['context'] == 'OWNED_CLEANUP'
                assert receipt['failure_context'] == 'LIVE_OBSERVATION'
        else:
            assert 'failure_operation' not in receipt and receipt['failure_reason'] == 'OWNED_SUPERVISION_ERROR'
        main = next(n for n in ast.parse(source.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == 'main')
        finalizer = next(n.finalbody for n in ast.walk(main) if isinstance(n, ast.Try) and
                         any(isinstance(q, ast.Call) and getattr(q.func, 'attr', None) == 'unlink'
                             for q in ast.walk(ast.Module(body=n.finalbody, type_ignores=[]))))
        lock = out / 'owned.lock'
        lock.touch(mode=0o600)
        proof = {}
        try:
            exec(compile(ast.Module(body=finalizer, type_ignores=[]), str(source), 'exec'),
                 dict(json=json, public=public, lock=lock, lock_identity=lock.stat().st_ino,
                      os=os, signal=signal, proof=proof))
        except AssertionError:
            assert 'cleanup_failure_type' in receipt
        assert lock.exists() == ('cleanup_failure_type' in receipt)
        cases.append({'version': version, 'case': mode,
                      'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                      'actual_timeout_helpers_reaped_and_absent': len(observer_helpers),
                      'five_second_bound_unchanged': True, 'wrapper_reaped': receipt['wrapper_reaped'],
                      'first_context': receipt.get('failure_context'),
                      'timeout_events': receipt.get('snapshot_timeouts', []),
                      'lock_retained': lock.exists(), 'caller_handlers_and_mask_restored': True,
                      'wall_seconds': round(time.monotonic() - began, 3)})
result = {'schema': 'meownero-intel20-owned-observer-timeout-fixtures/1',
          'result': 'PASS_FAIL_CLOSED_STATIC_PROVENANCE_FIRST_ERROR_CLEANUP_AND_CALLER_RESTORATION',
          'cases': cases, 'actual_Intel14_timeout_call': 'NOT_RECORDED_SOURCE_CANDIDATE_ONLY',
          'native_Intel_execution': 'UNTESTED_BY_FIXTURE'}
Path(__file__).with_suffix('.json').write_text(json.dumps(result, indent=2) + '\n')
print(result['result'])
