"""Exercise pre-receipt failures using unchanged, hash-bound packaged source."""
from contextlib import nullcontext
import ast
import hashlib
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
import zipfile

root = Path(__file__).resolve().parents[3]
helper = root / 'vanguard/run-portable-journey-diagnostic.py'
archive = Path('/storage/data/meownero-tjs1882-3175/windows-x86-package02/meownero-vanguard-windows-i686.zip')
assert hashlib.sha256(archive.read_bytes()).hexdigest() == '3a0a34d874184165a83f9025cdabd18b67b19fa862c57cfac5b04d21d736e745'
spec = importlib.util.spec_from_file_location('diagnostic', helper)
diagnostic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagnostic)
cases = []
with tempfile.TemporaryDirectory(prefix='i68616-owned-', dir='/storage/data/meownero-tjs1882-3175') as tmp:
    base = Path(tmp)
    package = base / 'package'
    package.mkdir(mode=0o700)
    with zipfile.ZipFile(archive) as stream:
        prefix = 'meownero-vanguard-windows-i686/'
        release = json.loads(stream.read(prefix + 'release.json'))
        for name in ['release.json', 'tester.py', *['bin/' + n + '.exe' for n in ('monerod', 'monero-wallet-cli', 'monero-wallet-rpc')]]:
            data = stream.read(prefix + name)
            if name != 'release.json':
                assert hashlib.sha256(data).hexdigest() == release['files'][name]
            p = package / name
            p.parent.mkdir(mode=0o700, exist_ok=True)
            p.write_bytes(data)
    tester = package / 'tester.py'
    digest = hashlib.sha256(tester.read_bytes()).hexdigest()
    original_exec = importlib.machinery.SourceFileLoader.exec_module
    for name, phase, reason in [
        ('collision', 'OUTPUT_GUARD', 'OUTPUT_COLLISION_OR_PARENT'),
        ('actual-wrong-os', 'PREFLIGHT', 'OS_MISMATCH'),
        ('capacity', 'CAPACITY_GUARD', 'CAPACITY_RESERVE_NOT_MET'),
        ('owned-job-error', 'INITIALIZE_OWNED_JOB', 'EXCEPTION_UNCLASSIFIED'),
        ('private-exception', 'PREFLIGHT', 'EXCEPTION_UNCLASSIFIED')]:
        out = base / name
        journal = base / (name + '.json')
        if name == 'collision':
            out.mkdir(mode=0o700)

        def load(loader, module):
            original_exec(loader, module)
            if module.__name__ != 'bound_portable_journey':
                return
            if name in ('capacity', 'owned-job-error'):
                module.preflight = lambda translated=False: release
                module.lock = nullcontext
                module.available_memory = lambda: 0 if name == 'capacity' else 8 * 1024**3
            if name == 'owned-job-error':
                def bad_job(**kwargs):
                    raise PermissionError(13, 'PRIVATE_WALLET_SEED_SENTINEL')
                module.WINDOWS = True
                module.portable_windows = SimpleNamespace(native_architecture=lambda: 'x86_64', Job=bad_job)
            if name == 'private-exception':
                def bad_preflight(translated=False):
                    raise RuntimeError('PRIVATE_WALLET_SEED_SENTINEL')
                module.preflight = bad_preflight

        argv = ['diagnostic', '--tester', str(tester), '--tester-sha256', digest,
                '--diagnostic', str(journal), '--out', str(out)]
        with patch.object(sys, 'argv', argv), patch.object(importlib.machinery.SourceFileLoader, 'exec_module', load):
            try:
                diagnostic.main()
                raise AssertionError('fixture failure was accepted')
            except (RuntimeError, PermissionError):
                pass
        value = json.loads(journal.read_text())
        assert value['result'] == 'FAIL' and value['first_failure']['phase'] == phase, (name, value)
        assert value['first_failure']['reason'] == reason, (name, value)
        assert 'PRIVATE_WALLET_SEED_SENTINEL' not in journal.read_text()
        assert not any(k in value['first_failure'] for k in ('message', 'argv', 'stderr', 'stdout', 'traceback'))
        if name == 'capacity':
            assert value['available_memory_bytes'] == 0 and value['disk_free_bytes_used_by_guard'] is None
        if name == 'owned-job-error':
            assert value['first_failure']['errno'] == 13
        cases.append({'case': name, 'first_failure': value['first_failure'],
                      'completed_phases': value['completed_phases'], 'privacy': 'PASS',
                      'actual_native_journey': 'NOT_EXECUTED',
                      'fixture': 'REAL_BOUND_SOURCE_GUARDS' if name in ('collision', 'actual-wrong-os') else 'INJECTED_PRE_RECEIPT_FAILURE'})
    # Exercise the actual source-bound trace on exact immutable run-code identity
    # and its cleanup line. No simulated wallet journey is accepted as native.
    spec = importlib.util.spec_from_file_location('fixture_bound_source', tester)
    bound = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bound)
    run = next(n for n in ast.parse(tester.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == 'run')
    finalizer = next(n for n in ast.walk(run) if isinstance(n, ast.Try) and n.finalbody and
                     isinstance(n.finalbody[0], ast.If) and isinstance(n.finalbody[0].test, ast.UnaryOp))
    main = next(n for n in ast.parse(helper.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == 'main')
    functions = [n for n in ast.walk(main) if isinstance(n, ast.FunctionDef) and n.name in ('failure', 'trace')]
    assert len(functions) == 2
    for interrupted in (False, True):
        receipt = {'phase': 'FINAL_PREFLIGHT', 'completed_phases': []}
        namespace = {'receipt': receipt, 'save': lambda: None, 'module': bound,
                     'anchors': {finalizer.finalbody[0].lineno: 'OWNED_CLEANUP'}, 'seen': set()}
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(helper), 'exec'), namespace)
        frame = SimpleNamespace(f_code=bound.run.__code__, f_lineno=finalizer.finalbody[0].lineno, f_locals={})
        if interrupted:
            error = bound.JourneyInterrupted('native journey interrupted or deadline reached')
            namespace['trace'](frame, 'exception', (type(error), error, None))
            assert receipt['first_failure']['reason'] == 'JOURNEY_INTERRUPTED'
        namespace['trace'](frame, 'line', None)
        assert ('FINAL_PREFLIGHT' in receipt['completed_phases']) != interrupted
        cases.append({'case': 'interrupted-cleanup-transition' if interrupted else 'successful-final-preflight-transition',
                      'static_first_failure': receipt.get('first_failure'), 'completed_phases': receipt['completed_phases'],
                      'fixture': 'ACTUAL_TRACE_AST_BOUND_RUN_CODE_IDENTITY_AND_CLEANUP_LINE_NO_NATIVE_JOURNEY'})
result = {'schema': 'meownero-i68616-public-journey-diagnostic-fixtures/1',
          'result': 'PASS_ENTRY_CAPACITY_JOB_FAILURE_PHASES_AND_PRIVATE_TEXT_EXCLUSION',
          'diagnostic_sha256': hashlib.sha256(helper.read_bytes()).hexdigest(),
          'packaged_tester_sha256': digest, 'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
          'cases': cases, 'native_acceptance': 'UNTESTED_BY_FIXTURES'}
Path(__file__).with_suffix('.json').write_text(json.dumps(result, indent=2) + '\n')
print(result['result'])
