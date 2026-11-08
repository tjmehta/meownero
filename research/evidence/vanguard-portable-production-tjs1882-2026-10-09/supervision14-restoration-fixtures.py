"""Real caller signals after supervised cleanup must use restored handlers."""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import signal
import sys
import tempfile
from types import SimpleNamespace

root = Path(__file__).resolve().parents[3]
files = {
    'original-Intel11': root / 'build/tjs1882-3175-native-ci-payload11/vanguard/run-portable-ci.py',
    'corrected-Intel14': root / 'build/tjs1882-3175-intel14-supervisor.py',
    'original-LinuxARM13': root / 'build/tjs1882-3175-native-linux-arm-ci-payload13/vanguard/run-portable-ci.py',
    'corrected-LinuxARM15': root / 'build/tjs1882-3175-linux-arm15-supervisor.py',
}
cases = []
with tempfile.TemporaryDirectory(prefix='tjs1882-supervision14-') as tmp:
    for name, source in files.items():
        spec = importlib.util.spec_from_file_location(name, source)
        ci = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ci)
        callbacks = []

        def caller(number, frame):
            callbacks.append(int(number))

        original = {number: signal.signal(number, caller) for number in (signal.SIGTERM, signal.SIGINT)}
        initial_mask = signal.pthread_sigmask(signal.SIG_BLOCK, set())
        ordinary_write = ci.write
        delivered_during_write = []

        def cancellation_write(path, value):
            if not delivered_during_write:
                delivered_during_write.append(True)
                os.kill(os.getpid(), signal.SIGTERM)
                os.kill(os.getpid(), signal.SIGINT)
            return ordinary_write(path, value)

        ci.write = cancellation_write
        try:
            out = Path(tmp) / name
            out.mkdir(mode=0o700)
            public = out / 'public'
            public.mkdir(mode=0o700)
            ci.mac_check([sys.executable, '-B', '-c', 'import time;time.sleep(.1)'], out, public,
                         timeout=5, cleanup_seconds=5)
            receipt = json.loads((public / 'supervision.json').read_text())
            assert receipt['wrapper_reaped'] and all(p['removed'] for p in receipt['cleanup'])
            restored = all(signal.getsignal(number) is caller for number in original)
            assert signal.pthread_sigmask(signal.SIG_BLOCK, set()) == initial_mask
            expected = name.startswith('corrected')
            assert restored and bool(callbacks) == expected
            if expected:
                assert sorted(callbacks) == sorted([int(signal.SIGTERM), int(signal.SIGINT)])
                assert receipt['result'] == 'FAIL'
                assert receipt['failure_reason'] == 'CANCELLATION_DURING_OWNED_CLEANUP'
            else:
                assert receipt['result'] == 'PASS_WRAPPER_AND_OWNED_CLEANUP'
            cases.append({'case': name, 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                          'actual_owned_worker_reaped': True, 'original_mask_restored': True,
                          'caller_handlers_restored': restored,
                          'actual_final_receipt_signals_delivered_to_caller': callbacks,
                          'honest_cleanup_cancellation_failure': receipt['result'] == 'FAIL'})
        finally:
            for number, handler in original.items():
                signal.signal(number, handler)
            signal.pthread_sigmask(signal.SIG_SETMASK, initial_mask)

    for name in ('original-Intel11', 'corrected-Intel14'):
        source = files[name]
        mac = next(n for n in ast.parse(source.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == 'mac_check')
        fn = next(n for n in mac.body if isinstance(n, ast.FunctionDef) and n.name == 'remember_identity')
        first = {'pid': 9999, 'ppid': 1000, 'ruid': 501, 'euid': 0, 'role': 'FIRST_REJECTED'}
        receipt = {'failure_reason': 'FIRST_REASON', 'failure_observation': first,
                   'helper_observations': [], 'unverified_observations': []}
        binding = (1, 2, 0o104755, 'bound-helper-sha')
        namespace = {'receipt': receipt, 'known': {}, 'states': {}, 'rejected_live': {},
                     'helper_bindings': {}, 'unverified_zombies': set(), 'shlex': shlex,
                     'process': SimpleNamespace(pid=1000), 'platform': SimpleNamespace(system=lambda: 'Darwin'),
                     'os': SimpleNamespace(getuid=lambda: 501, geteuid=lambda: 501),
                     'helper_binding': lambda pid: binding, 'helper_file_binding': lambda: binding,
                     'pid_absent': lambda pid, rows: False,
                     'reject': lambda reason, observation=None: (_ for _ in ()).throw(AssertionError(reason))}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), str(source), 'exec'), namespace)
        namespace['remember_identity'](1001, (1000, 501, 0, ('Fri', 'Oct', '9', '15:00:00', '2026'),
                                             '/bin/ps -axo pid=,ppid=,rss='))
        preserved = receipt.get('failure_observation') == first
        assert preserved == name.startswith('corrected')
        cases.append({'case': name + '-later-approved-helper', 'first_failure_observation_preserved': preserved,
                      'original_reason_preserved': receipt['failure_reason'] == 'FIRST_REASON',
                      'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest()})
result = {'schema': 'meownero-supervision14-caller-handler-first-observation-fixtures/1',
          'result': 'PASS_OLD_LOSS_REPRODUCED_NEW_CALLER_SIGNAL_AND_FIRST_OBSERVATION_RESTORED',
          'cases': cases, 'native_archive_journeys': 'UNTESTED_BY_FIXTURES'}
Path(__file__).with_suffix('.json').write_text(json.dumps(result, indent=2) + '\n')
print(result['result'])
