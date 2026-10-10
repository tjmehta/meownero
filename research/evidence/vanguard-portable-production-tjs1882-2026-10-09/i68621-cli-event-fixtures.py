"""Bound CLI trace, private event matching and actual public export regions.

Linux fixtures exercise owned query timeout cleanup. Native Windows execution
and Application Error availability remain untested by these fixtures.
"""
import ast
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

root = Path(__file__).resolve().parents[3]
source = root / 'build/tjs1882-2493-i68621-supervisor.py'
spec = importlib.util.spec_from_file_location('ci21', source)
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)
helper = root / 'vanguard/run-portable-journey-diagnostic.py'
tester = root / 'build/tjs1882-3175-ci19-prepare-only01/binding-extract/meownero-vanguard-windows-i686/tester.py'
spec = importlib.util.spec_from_file_location('bound', tester)
bound = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bound)
main = next(n for n in ast.parse(helper.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == 'main')
functions = [n for n in ast.walk(main) if isinstance(n, ast.FunctionDef) and n.name in ('failure', 'trace')]
run = next(n for n in ast.parse(tester.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == 'run')
lines = tester.read_text().splitlines()
line = lambda prefix: next(i + 1 for i in range(run.lineno - 1, run.end_lineno) if lines[i].strip().startswith(prefix))
start, wait, check = line("cli = spawn('cli',"), line('cli.wait(timeout=60)'), line('require(cli.returncode == 0')
records, cases = [], []
for status in (0, 0xC0000005, 1, None):
    receipt = {'schema': 'meownero-bound-journey-diagnostic/1', 'result': 'FAIL',
        'tester_sha256': hashlib.sha256(tester.read_bytes()).hexdigest(),
        'phase': 'OPEN_NATIVE_CLI', 'completed_phases': [], 'private_extra': 'PRIVATE_WALLET_SENTINEL'}
    child = SimpleNamespace(pid=1234, returncode=status, argv=['PRIVATE_WALLET_SENTINEL'])
    snapshots = []
    namespace = dict(receipt=receipt, save=lambda: snapshots.append(json.loads(json.dumps(receipt))),
        module=bound, anchors={}, seen=set(), cli_clock={}, cli_starts=[start], cli_waits=[wait], cli_checks=[check], time=ci.time)
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(helper), 'exec'), namespace)
    frame = SimpleNamespace(f_code=bound.run.__code__, f_lineno=start, f_locals={'cli': child, 'processes': [('cli', child)]})
    namespace['trace'](frame, 'line', None)
    frame.f_lineno = wait
    namespace['trace'](frame, 'line', None)
    if status is None:
        error = subprocess.TimeoutExpired('PRIVATE_WALLET_SENTINEL', 60)
        namespace['trace'](frame, 'exception', (type(error), error, None))
        assert receipt['native_cli']['exit_class'] == 'WAIT_TIMEOUT'
        assert receipt['first_failure']['reason'] == 'NATIVE_CLI_WAIT_TIMEOUT'
    else:
        frame.f_lineno = check
        namespace['trace'](frame, 'line', None)
        if status:
            error = RuntimeError('native CLI could not open restored wallet')
            namespace['trace'](frame, 'exception', (type(error), error, None))
            assert receipt['first_failure']['reason'] == 'NATIVE_CLI_RESTORED_WALLET_FAILED'
        else:
            receipt['result'] = 'PASS_BOUND_JOURNEY_CALL'
    records.append(receipt)
    cases.append({'case': 'bound-cli-' + ('timeout' if status is None else str(status)),
                  'exit_class': receipt['native_cli']['exit_class'], 'actual_trace_code_and_packaged_run_identity': True})

with tempfile.TemporaryDirectory(prefix='tjs1882-cli21-') as tmp:
    base = Path(tmp)
    image = base / 'package/bin/monero-wallet-cli.exe'
    image.parent.mkdir(parents=True)
    image.write_bytes(b'BOUND_IMAGE_FIXTURE')
    digest = ci.sha(image)
    (image.parent.parent / 'release.json').write_text(json.dumps({'files': {'bin/monero-wallet-cli.exe': digest}}))
    row = {'program_sha256': {'monero-wallet-cli': digest}}
    now = ci.time.time()
    cli = {'pid': 1234, 'exit': 0xC0000005, 'started_epoch_seconds': now - 4, 'observed_exit_epoch_seconds': now - 1}
    stamp = datetime.datetime.fromtimestamp(now - 2, datetime.timezone.utc).isoformat().replace('+00:00', 'Z')
    creation = hex(int((now - 3 + 11644473600) * 10**7))
    def xml(pid='0x4d2', created=creation, app=str(image), module=str(image), exception='c0000005'):
        from xml.sax.saxutils import escape
        return ('<Events><Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">'
            '<System><Provider Name="Application Error"/><EventID>1000</EventID><TimeCreated SystemTime="' + stamp + '"/></System><EventData>' +
            ''.join('<Data Name="' + k + '">' + escape(v) + '</Data>' for k, v in {
                'ProcessId': pid, 'ProcessCreationTime': created, 'AppPath': app, 'ModulePath': module,
                'ExceptionCode': exception, 'FaultingOffset': '123', 'Message': 'PRIVATE_WALLET_SENTINEL'}.items()) + '</EventData></Event></Events>').encode()
    for name, data, expected in [('match', xml(), 'MATCHED_BOUND_CLI_EVENT'),
        ('wrong-pid', xml(pid='0x999'), 'NO_MATCHING_EVENT'), ('reused-pid', xml(created='0x1'), 'NO_MATCHING_EVENT'),
        ('wrong-image', xml(app='C:/PRIVATE_WALLET_SENTINEL.exe'), 'NO_MATCHING_EVENT'),
        ('wrong-status', xml(exception='bad'), 'NO_MATCHING_EVENT'),
        ('unknown-module', xml(module='C:/PRIVATE_WALLET_SENTINEL.dll'), 'MATCHED_BOUND_CLI_EVENT')]:
        safe = ci.matching_cli_events(data, cli, image, digest, Path('C:/Windows/System32'), now)
        assert safe['status'] == expected and 'PRIVATE_WALLET_SENTINEL' not in json.dumps(safe)
        if name == 'unknown-module': assert safe['module_class'] == 'UNKNOWN'
        cases.append({'case': name, 'status': safe['status']})
    duplicate = xml().replace(b'</Events>', b'') + xml().split(b'<Events>')[1]
    assert ci.matching_cli_events(duplicate, cli, image, digest, Path('C:/Windows/System32'), now)['status'] == 'AMBIGUOUS_MATCH'
    for data in (b'<!DOCTYPE Events><Events/>', b'x' * (128 * 1024 + 1)):
        try: ci.matching_cli_events(data, cli, image, digest, Path('C:/Windows/System32'), now)
        except AssertionError: pass
        else: raise AssertionError('hostile XML accepted')

    # Execute actual owned-query cleanup, substituting only the Windows Job/API.
    import ctypes
    def api(*args):
        def system_directory(buffer, size):
            buffer.value = 'C:/Windows/System32'
            return len(buffer.value)
        return system_directory
    backend = SimpleNamespace(C=ctypes, W=SimpleNamespace(UINT=int, LPWSTR=str), k=None, api=api)
    for name, status in [('match', 'MATCHED_BOUND_CLI_EVENT'), ('empty', 'NO_MATCHING_EVENT'),
                         ('failure', 'QUERY_FAILED'), ('timeout', 'QUERY_TIMEOUT')]:
        out = base / name
        out.mkdir()
        (out / 'journey-diagnostic.json').write_text(json.dumps({'native_cli': cli}))
        children = []
        def spawn(executable, arguments, stream, env, cwd):
            assert arguments[:2] == ['qe', 'Application'] and '/c:32' in arguments and '/f:xml' in arguments
            assert '/r:' not in ' '.join(arguments)
            if name in ('match', 'empty'):
                stream.write((xml().decode() if name == 'match' else '<Events/>').encode('utf-16'))
                stream.flush()
            code = 'import time; time.sleep(30)' if name == 'timeout' else 'raise SystemExit(' + ('1' if name == 'failure' else '0') + ')'
            child = subprocess.Popen([sys.executable, '-B', '-c', code], stdout=stream, stderr=stream)
            children.append(child)
            return child
        evidence = ci.native_cli_event(image.parent.parent, out, row, backend, SimpleNamespace(spawn=spawn))
        assert evidence['status'] == status and evidence['query_reaped']
        assert children[0].poll() is not None
        try: os.kill(children[0].pid, 0)
        except ProcessLookupError: pass
        else: raise AssertionError('query child remains')
        assert 'PRIVATE_WALLET_SENTINEL' not in json.dumps(evidence)
        cases.append({'case': 'owned-query-' + name, 'status': status, 'actual_child_reaped_and_absent': True})

    main = next(n for n in ast.parse(source.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == 'main')
    finalizer = next(n.finalbody for n in main.body if isinstance(n, ast.Try) and n.finalbody)
    success = next(n for n in ast.walk(main) if isinstance(n, ast.For) and isinstance(n.iter, ast.List) and n.iter.elts and isinstance(n.iter.elts[0], ast.Tuple) and isinstance(n.iter.elts[0].elts[0], ast.Constant) and n.iter.elts[0].elts[0].value == 'journey.json')
    for receipt in records:
        out = base / ('public-write-' + receipt['native_cli']['exit_class'])
        out.mkdir()
        public = out / 'public'
        public.mkdir()
        check = {'schema': 'meownero-native-windows-ci-check/1', 'result': 'FAIL', 'phases': [],
            'native_cli_event': {'status': 'NO_MATCHING_EVENT', 'cause': 'UNKNOWN', 'xml': 'PRIVATE_WALLET_SENTINEL'},
            'argv': ['PRIVATE_WALLET_SENTINEL']}
        ci.write(out / 'journey-diagnostic.json', receipt)
        ci.write(out / 'check-receipt.json', check)
        writes = []
        def write(path, value):
            assert 'PRIVATE_WALLET_SENTINEL' not in json.dumps(value)
            writes.append(path.name)
            ci.write(path, value)
        namespace = dict(ci.__dict__, check_root=out, public=public, proof={'result': 'FAIL'},
            check=check, journey={'result': 'FAIL'}, controls={'result': 'NOT_REACHED'}, write=write)
        exec(compile(ast.Module(body=[success], type_ignores=[]), str(source), 'exec'), namespace)
        exec(compile(ast.Module(body=finalizer, type_ignores=[]), str(source), 'exec'), namespace)
        assert writes.count('check.json') == 2 and writes.count('journey-diagnostic.json') == 1
        assert json.loads((out / 'journey-diagnostic.json').read_text()) == receipt
        cases.append({'case': 'all-public-writes-' + receipt['native_cli']['exit_class'], 'private_receipt_unchanged': True})

result = {'schema': 'meownero-i68621-cli-diagnostic-fixtures/1', 'result': 'PASS', 'cases': cases,
    'helper_sha256': hashlib.sha256(helper.read_bytes()).hexdigest(), 'supervisor_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
    'native_Windows_event_query': 'UNTESTED_BY_LINUX_FIXTURES', 'native_acceptance': False}
Path(__file__).with_suffix('.json').write_text(json.dumps(result, indent=2) + '\n')
print('PASS_BOUND_CLI_EVENTS_OWNED_TIMEOUT_CLEANUP_AND_ALL_PUBLIC_WRITES')
