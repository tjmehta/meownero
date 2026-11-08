"""Bound admission and single launch using exact candidate and packaged guard ASTs."""
import ast
import ctypes
import ctypes.wintypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

root = Path(__file__).resolve().parents[3]
source = Path(__file__).with_name('i68629-supervisor.source.py')
base = root / 'build/tjs1882-2493-native-ci-payload21/vanguard/run-portable-ci.py'
tester = root / 'build/tjs1882-2493-validate21-only/binding-extract/meownero-vanguard-windows-i686/tester.py'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(tester) == '17835eafcb740ba1e65030df01c58505e96742dc33f439d9824977e089460ad0'
spec = importlib.util.spec_from_file_location('candidate', source)
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)
tree, original = ast.parse(source.read_text()), ast.parse(base.read_text())
function = lambda tree, name: next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
windows, old_windows = function(tree, 'windows_check'), function(original, 'windows_check')
for name in ('phase',):
    current = next(n for n in ast.walk(windows) if isinstance(n, ast.FunctionDef) and n.name == name)
    old = next(n for n in ast.walk(old_windows) if isinstance(n, ast.FunctionDef) and n.name == name)
    assert ast.dump(current) == ast.dump(old)
outer = next(n for n in windows.body if isinstance(n, ast.Try))
old_outer = next(n for n in old_windows.body if isinstance(n, ast.Try))
assert ast.dump(ast.Module(body=outer.finalbody, type_ignores=[])) == ast.dump(ast.Module(body=old_outer.finalbody, type_ignores=[]))
for name in ('native_cli_event', 'matching_cli_events', 'mac_check'):
    assert ast.dump(function(tree, name)) == ast.dump(function(original, name))

class Clock:
    def __init__(self):
        self.now = 100.0
        self.sleeps = []
        self.cancel = False
    def monotonic(self):
        return self.now
    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds
        if self.cancel:
            os.kill(os.getpid(), signal.SIGUSR1)

cases = []
reserve = 5 * 1024**3
for name, memories, disks, expected in [
    ('below-memory', [reserve - 1], [reserve], 'CAPACITY_WINDOW_EXPIRED'),
    ('below-disk', [reserve], [reserve - 1], 'CAPACITY_WINDOW_EXPIRED'),
    ('at-threshold', [reserve], [reserve], 'READY'),
    ('above-threshold', [reserve + 1], [reserve + 1], 'READY'),
    ('recover-once', [reserve - 1, reserve], [reserve], 'READY'),
    ('cancel-wait', [reserve - 1], [reserve], 'CANCELLED'),
    ('unavailable', [OSError('PRIVATE_SEED_SENTINEL')], [reserve], 'CAPACITY_UNAVAILABLE'),
    ('job-budget', [reserve - 1], [reserve], 'JOB_DEADLINE'),
    ('measurement-overruns-window', [reserve], [reserve], 'CAPACITY_WINDOW_EXPIRED')]:
    clock, receipt, job = Clock(), {}, SimpleNamespace(expired=False)
    clock.cancel = name == 'cancel-wait'
    memory_index, disk_index = [0], [0]
    def memory():
        value = memories[min(memory_index[0], len(memories) - 1)]
        memory_index[0] += 1
        if name == 'measurement-overruns-window':
            clock.now += 60
        if isinstance(value, Exception):
            raise value
        return value
    def disk(path):
        assert path == Path('/fixture/target-volume')
        value = disks[min(disk_index[0], len(disks) - 1)]
        disk_index[0] += 1
        return SimpleNamespace(free=value)
    saved = {s: signal.getsignal(s) for s in (signal.SIGINT, signal.SIGTERM, signal.SIGUSR1)}
    with patch.object(signal, 'SIGBREAK', signal.SIGUSR1, create=True), patch.object(ci.time, 'monotonic', clock.monotonic), patch.object(ci.time, 'sleep', clock.sleep), patch.object(ci.shutil, 'disk_usage', disk):
        try:
            ci.wait_journey_capacity(SimpleNamespace(available_memory=memory), Path('/fixture/target-volume'), job,
                clock.now - 1499 if name == 'job-budget' else clock.now, receipt)
        except RuntimeError:
            assert expected != 'READY'
        else:
            assert expected == 'READY'
    assert all(signal.getsignal(s) == h for s, h in saved.items())
    evidence = receipt['capacity_admission']
    assert evidence['status'] == expected
    assert evidence['elapsed_seconds'] <= 60 and evidence['sample_count'] <= 61
    evidence['private_extra'] = 'PRIVATE_SEED_SENTINEL'
    for sample in evidence['samples']:
        sample['private_extra'] = 'PRIVATE_SEED_SENTINEL'
    public = ci.public_check({'schema': 'meownero-native-windows-ci-check/1', 'result': 'FAIL',
        'capacity_admission': evidence, 'phases': []})
    assert 'PRIVATE_SEED_SENTINEL' not in json.dumps(public)
    cases.append({'case': name, 'status': expected, 'elapsed_seconds': evidence['elapsed_seconds'],
        'samples': evidence['sample_count'], 'handlers_restored': True, 'static_public_projection': 'PASS'})

# Execute the actual wrapper control flow and finalizer. The unchanged Windows
# phase launcher is the fixture seam; it models phase results, never native proof.
stub = ast.parse('def phase(name, argv, timeout=1500):\n    return fixture_phase(name, argv, timeout)').body[0]
windows.body = [stub if isinstance(n, ast.FunctionDef) and n.name == 'phase' else n for n in windows.body]
namespace = dict(ci.__dict__)
exec(compile(ast.fix_missing_locations(ast.Module(body=[windows], type_ignores=[])), str(source), 'exec'), namespace)
run = function(ast.parse(tester.read_text()), 'run')
guard = next(n for n in ast.walk(run) if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
    and isinstance(n.value.func, ast.Name) and n.value.func.id == 'require'
    and any(isinstance(a, ast.Constant) and a.value == 'requires five GiB available memory and disk' for a in n.value.args))
def require(condition, message):
    if not condition:
        raise RuntimeError(message)

with tempfile.TemporaryDirectory() as tmp:
    package = Path(tmp) / 'package'
    package.mkdir()
    (package / 'release.json').write_text(json.dumps({'architecture': 'i686', 'native_exception_probe':
        {'file': 'probe.exe', 'native_execution': 'UNTESTED', 'required_for_native_acceptance': True},
        'files': {'probe.exe': 'a' * 64, 'build-evidence/i686-exception-probe.cpp': 'b' * 64}}))
    for name in ('success', 'handoff-drop', 'exhaustion', 'cancellation'):
        out = Path(tmp) / name
        out.mkdir()
        clock, phases, jobs = Clock(), [], []
        clock.cancel = name == 'cancellation'
        def api(library, name, *signature):
            assert name == 'GetConsoleProcessList'
            return lambda *args: 1
        class Job:
            def __init__(self, seconds):
                assert seconds == 1500
                self.expired = False
                jobs.append(self)
            def close(self):
                self.cleanup = {'active_processes': 0, 'children': []}
        backend = SimpleNamespace(C=ctypes, W=ctypes.wintypes, k=None, api=api, Job=Job,
            native_architecture=lambda: 'x86_64', available_memory=lambda: reserve - 1 if name in ('exhaustion', 'cancellation') else reserve)
        def fixture_phase(phase, argv, timeout):
            phases.append(phase)
            if phase == 'exception-probe':
                (out / 'exception-probe.log').write_bytes(b'PASS_NATIVE_I686_EXCEPTION_PROBE\n')
            if phase == 'journey' and name == 'handoff-drop':
                scope = {'available': reserve - 1, 'out': out / 'journey', 'shutil': ci.shutil, 'require': require}
                exec(compile(ast.Module(body=[guard], type_ignores=[]), str(tester), 'exec'), scope)
            return {'exit': 0, 'reaped': True}
        namespace['fixture_phase'] = fixture_phase
        loader = SimpleNamespace(loader=SimpleNamespace(exec_module=lambda module: None))
        row = {'architecture': 'i686', 'native_exception_probe': {'file': 'probe.exe',
            'files': {'probe.exe': 'a' * 64, 'build-evidence/i686-exception-probe.cpp': 'b' * 64}},
            'package_helpers': {'tester.py': sha(tester)}}
        saved = {s: signal.getsignal(s) for s in (signal.SIGINT, signal.SIGTERM, signal.SIGUSR1)}
        with patch.object(signal, 'SIGBREAK', signal.SIGUSR1, create=True), patch.object(ci.importlib.util, 'spec_from_file_location', return_value=loader), patch.object(ci.importlib.util, 'module_from_spec', return_value=backend), patch.object(ci.time, 'monotonic', clock.monotonic), patch.object(ci.time, 'sleep', clock.sleep), patch.object(ci.shutil, 'disk_usage', return_value=SimpleNamespace(free=reserve)), patch.dict(namespace, sha=lambda path: 'a' * 64 if path.name == 'probe.exe' else 'b' * 64, native_cli_event=lambda *args: {'status': 'NOT_REQUESTED', 'cause': 'UNKNOWN'}):
            try:
                namespace['windows_check'](package, out, row)
            except RuntimeError:
                assert name != 'success'
            else:
                assert name == 'success'
        assert all(signal.getsignal(s) == h for s, h in saved.items())
        receipt = json.loads((out / 'check-receipt.json').read_text())
        assert receipt['owned_job']['active_processes'] == 0
        assert phases.count('journey') == (1 if name in ('success', 'handoff-drop') else 0)
        assert ('controls' in phases) == (name == 'success')
        receipt['private_extra'] = 'PRIVATE_SEED_SENTINEL'
        main = function(tree, 'main')
        success = next(n for n in ast.walk(main) if isinstance(n, ast.For) and isinstance(n.iter, ast.List) and n.iter.elts and isinstance(n.iter.elts[0], ast.Tuple) and isinstance(n.iter.elts[0].elts[0], ast.Constant) and n.iter.elts[0].elts[0].value == 'journey.json')
        finalizer = next(n.finalbody for n in main.body if isinstance(n, ast.Try) and n.finalbody)
        public = out / 'public'
        public.mkdir()
        ci.write(out / 'check-receipt.json', receipt)
        scope = dict(ci.__dict__, check_root=out, public=public, check=receipt, journey={}, controls={}, proof={'result': 'FAIL'})
        writes = []
        def write(path, value):
            if path.name == 'check.json':
                assert 'PRIVATE_SEED_SENTINEL' not in json.dumps(value)
                writes.append(True)
            ci.write(path, value)
        scope['write'] = write
        exec(compile(ast.Module(body=[success], type_ignores=[]), str(source), 'exec'), scope)
        exec(compile(ast.Module(body=finalizer, type_ignores=[]), str(source), 'exec'), scope)
        assert len(writes) == 2
        cases.append({'case': 'wrapper-' + name, 'phases': phases, 'journey_launches': phases.count('journey'),
            'controls_gated': True, 'owned_job_close_executed': True, 'all_public_check_writes': len(writes),
            'private_sentinel_exported': False, 'handlers_restored': True,
            'fixture_scope': 'EXACT_WRAPPER_CONTROL_FLOW_AND_FINALIZER_WITH_UNCHANGED_PHASE_LAUNCHER_STUB'})

result = {'schema': 'meownero-i68629-capacity-fixtures/1', 'result': 'PASS',
    'candidate_sha256': sha(source), 'preserved_base_sha256': sha(base), 'packaged_tester_sha256': sha(tester),
    'protected_phase_finalizer_event_and_mac_AST': 'UNCHANGED', 'cases': cases,
    'native_Windows_capacity_or_CLI_fix_proven': False}
Path(__file__).with_suffix('.json').write_text(json.dumps(result, indent=2) + '\n')
print('PASS', len(cases), 'source-bound cases')
