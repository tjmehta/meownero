#!/usr/bin/env python3
"""Verify bound early-exit diagnostics and unchanged interruption ownership."""
import argparse
import ast
from contextlib import nullcontext
import hashlib
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parent.parent
SHA = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--predecessor', type=Path, required=True)
    parser.add_argument('--archive', type=Path, required=True)
    args = parser.parse_args()
    assert args.out.parent.is_dir() and not args.out.exists()
    assert SHA(args.archive) == '3a0a34d874184165a83f9025cdabd18b67b19fa862c57cfac5b04d21d736e745'
    harness_path = ROOT / 'vanguard/test-portable-refusals.py'
    diagnostic_path = ROOT / 'vanguard/run-portable-journey-diagnostic.py'
    harness = load('interruption_harness', harness_path)
    diagnostic = load('interruption_diagnostic', diagnostic_path)
    controller = load('bound_control_projection', args.predecessor / 'vanguard/run-portable-ci.py')
    old = ast.parse((args.predecessor / 'vanguard/test-portable-refusals.py').read_text())
    new = ast.parse(harness_path.read_text())
    loop = lambda tree: next(n for n in ast.walk(tree) if isinstance(n, ast.For) and isinstance(n.iter, ast.Name) and n.iter.id == 'interruptions')
    before, after = loop(old), loop(new)
    protected = lambda node: [[ast.dump(v) for v in n.finalbody]
                              for n in ast.walk(node) if isinstance(n, ast.Try) and n.finalbody]
    assert protected(before) == protected(after)
    popen = lambda node: next(n for n in ast.walk(node) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == 'Popen')
    assert [ast.dump(k) for k in popen(before).keywords] == [ast.dump(k) for k in popen(after).keywords]
    assert [ast.dump(n) for n in ast.walk(before) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in {'send_signal', 'wait', 'terminate', 'kill'}] == [ast.dump(n) for n in ast.walk(after) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in {'send_signal', 'wait', 'terminate', 'kill'}]
    cases = [{'case': 'registration-group-signal-wait-and-finalizers-preserved', 'result': 'PASS_AST'}]
    with tempfile.TemporaryDirectory(prefix='PRIVATE_SENTINEL-', dir=args.out.parent) as directory:
        base = Path(directory)
        package = base / 'package'
        package.mkdir()
        with zipfile.ZipFile(args.archive) as stream:
            prefix = 'meownero-vanguard-windows-i686/'
            release = json.loads(stream.read(prefix + 'release.json'))
            for name in ['release.json', 'tester.py', *['bin/' + n + '.exe' for n in ('monerod', 'monero-wallet-cli', 'monero-wallet-rpc')]]:
                path = package / name
                path.parent.mkdir(parents=True, exist_ok=True)
                data = stream.read(prefix + name)
                assert name == 'release.json' or hashlib.sha256(data).hexdigest() == release['files'][name]
                path.write_bytes(data)
        tester = package / 'tester.py'
        digest = SHA(tester)
        assert digest == '17835eafcb740ba1e65030df01c58505e96742dc33f439d9824977e089460ad0'
        original_exec = importlib.machinery.SourceFileLoader.exec_module
        capacity_journal = None
        for name in ('collision', 'wrong-os', 'capacity', 'deadline-forwarding'):
            out = base / name
            journal = base / (name + '.json')
            job_seconds = []
            if name == 'collision':
                out.mkdir()

            def execute(loader, module):
                original_exec(loader, module)
                if module.__name__ != 'bound_portable_journey':
                    return
                if name in ('capacity', 'deadline-forwarding'):
                    module.preflight = lambda translated=False: release
                    module.lock = nullcontext
                    module.available_memory = lambda: 0 if name == 'capacity' else 8 * 1024**3
                if name == 'deadline-forwarding':
                    def job(seconds):
                        job_seconds.append(seconds)
                        raise PermissionError(13, 'PRIVATE_SENTINEL')
                    module.WINDOWS = True
                    module.portable_windows = SimpleNamespace(native_architecture=lambda: 'x86_64', Job=job)

            argv = ['diagnostic', '--tester', str(tester), '--tester-sha256', digest,
                    '--diagnostic', str(journal), '--out', str(out)]
            if name == 'deadline-forwarding':
                argv += ['--deadline-seconds', '5']
            with patch.object(sys, 'argv', argv), patch.object(importlib.machinery.SourceFileLoader, 'exec_module', execute):
                try:
                    diagnostic.main()
                except (RuntimeError, PermissionError):
                    pass
                else:
                    raise AssertionError('fixture refusal lost')
            value = json.loads(journal.read_text())
            expected = {'collision': 'OUTPUT_COLLISION_OR_PARENT', 'wrong-os': 'OS_MISMATCH',
                        'capacity': 'CAPACITY_RESERVE_NOT_MET', 'deadline-forwarding': 'EXCEPTION_UNCLASSIFIED'}[name]
            assert value['first_failure']['reason'] == expected
            if name == 'deadline-forwarding':
                assert job_seconds == [5]
            observed = harness.interruption_observation(out, journal, digest, 1, harness.time.monotonic(), controller.public_diagnostic)
            assert observed['diagnostic_status'] == 'BOUND' and observed['diagnostic_reason'] == expected
            assert 'PRIVATE_SENTINEL' not in json.dumps(observed)
            if name == 'capacity':
                assert not observed['output_exists'] and not observed['result_exists']
                capacity_journal = journal.read_bytes()
            cases.append({'case': name, 'result': 'PASS', 'scope': 'ACTUAL_PINNED_SOURCE_GUARDS_WITH_DECLARED_CAPACITY_JOB_SEAMS'})

        for seconds in (0, 1201):
            journal = base / f'bad-deadline-{seconds}.json'
            argv = ['diagnostic', '--tester', str(tester), '--tester-sha256', digest,
                    '--diagnostic', str(journal), '--out', str(base / f'bad-deadline-{seconds}'),
                    '--deadline-seconds', str(seconds)]
            with patch.object(sys, 'argv', argv):
                try:
                    diagnostic.main()
                except AssertionError as error:
                    assert str(error) == 'deadline must be within 1..1200 seconds'
                else:
                    raise AssertionError('invalid deadline admitted')
            assert not journal.exists()
            cases.append({'case': f'invalid-deadline-{seconds}', 'result': 'PASS_REFUSAL'})

        bad = base / 'invalid.json'
        original = json.loads(capacity_journal)
        for name, mutate in [('phase', lambda v: v.update(phase='PRIVATE_SENTINEL')),
                             ('reason', lambda v: v['first_failure'].update(reason='PRIVATE_SENTINEL')),
                             ('wrong-binding', lambda v: v.update(tester_sha256='0' * 64)),
                             ('invalid-scalar', lambda v: v.update(available_memory_bytes='PRIVATE_SENTINEL'))]:
            value = json.loads(json.dumps(original))
            mutate(value)
            bad.write_text(json.dumps(value))
            row = harness.interruption_observation(base / 'absent', bad, digest, 1, harness.time.monotonic(), controller.public_diagnostic)
            assert row['diagnostic_status'] == 'INVALID' and 'PRIVATE_SENTINEL' not in json.dumps(row)
            cases.append({'case': 'private-or-invalid-' + name, 'result': 'PASS_REFUSAL'})
        bad.write_bytes(b'X' * (32 * 1024 + 1))
        assert harness.interruption_observation(base / 'absent', bad, digest, 1, harness.time.monotonic(), controller.public_diagnostic)['diagnostic_status'] == 'INVALID'
        cases.append({'case': 'bounded-diagnostic-size', 'result': 'PASS_REFUSAL'})
        link = base / 'linked.json'
        link.symlink_to(base / 'capacity.json')
        assert harness.interruption_observation(base / 'absent', link, digest, 1, harness.time.monotonic(), controller.public_diagnostic)['diagnostic_status'] == 'INVALID'
        cases.append({'case': 'diagnostic-symlink', 'result': 'PASS_REFUSAL'})

        # Execute the actual interruption loop with controlled Popen/WinAPI seams.
        # No simulated child is accepted as a native cancellation witness.
        for label in ('early-exit', 'live-cancel', 'live-deadline', 'not-ready-owned-stop'):
            out = base / ('loop-' + label)
            out.mkdir()
            name = 'deadline' if label == 'live-deadline' else 'cancelled'
            journey = out / name
            calls, current, rows = [], {}, []
            class Child:
                def __init__(self):
                    self.exited = label == 'early-exit'
                def poll(self):
                    return 1 if self.exited else None
                def send_signal(self, value):
                    calls.append(('signal', value))
                def terminate(self):
                    calls.append(('terminate',))
                    self.exited = True
                def kill(self):
                    raise AssertionError('unexpected forced kill')
                def wait(self, timeout):
                    calls.append(('wait', timeout))
                    self.exited = True
                    (journey / 'result.json').write_text(json.dumps({'result': 'FAIL_NATIVE_JOURNEY',
                        'cleanup': [{'removed': True, 'pid': 12345}], 'owned_job_cleanup': True}))
                    return 1
            child = Child()
            def spawn(argv, **kwargs):
                calls.append(('spawn',))
                assert kwargs['creationflags'] == 512
                assert argv[2] == str(diagnostic_path) and '--tester-sha256' in argv
                if label == 'live-deadline':
                    assert argv[-2:] == ['--deadline-seconds', '5']
                if label == 'early-exit':
                    (out / (name + '-journey-diagnostic.json')).write_bytes(capacity_journal)
                else:
                    (journey / 'private').mkdir(parents=True)
                    if label != 'not-ready-owned-stop':
                        (journey / ('private/daemon.log' if name == 'deadline' else 'private/sender.log')).write_bytes(b'')
                return child
            def begin(case, phase, reason):
                current.update(case=case, phase=phase, reason_enum=reason)
            def expect(condition, reason):
                current['reason_enum'] = reason
                if not condition:
                    raise AssertionError(reason)
            clock = iter([0, 0, 61, 61, 61]) if label == 'not-ready-owned-stop' else None
            clock_module = SimpleNamespace(monotonic=lambda: next(clock), sleep=lambda seconds: None) if clock else harness.time
            backend = SimpleNamespace(k=None, W=SimpleNamespace(HANDLE=None, DWORD=None, BOOL=None),
                                      api=lambda *args: lambda *argv: 0)
            scope = {'out': out, 'package': package, 'ROOT': ROOT, 'windows': True, 'args': SimpleNamespace(translated_macos_x86_64=False),
                     'interruptions': [(name, None if name == 'deadline' else 123)], 'begin': begin, 'expect': expect,
                     'current': current, 'rows': rows, 'signal': signal, 'sys': sys, 'time': clock_module,
                     'json': json, 'diagnostic_wrapper': diagnostic_path, 'tester_digest': digest, 'projection': controller,
                     'interruption_observation': harness.interruption_observation, 'backend': backend,
                     'subprocess': SimpleNamespace(Popen=spawn, CREATE_NEW_PROCESS_GROUP=512, STDOUT=subprocess.STDOUT,
                                                   TimeoutExpired=subprocess.TimeoutExpired)}
            try:
                exec(compile(ast.Module(body=[after], type_ignores=[]), str(harness_path), 'exec'), scope)
            except AssertionError as error:
                assert label in ('early-exit', 'not-ready-owned-stop') and str(error) == 'NATIVE_INTERRUPTION_FIXTURE_NOT_LIVE'
            else:
                assert label in ('live-cancel', 'live-deadline')
            if label == 'early-exit':
                assert calls == [('spawn',)] and current['interruption_fixture']['child_exit'] == 1
                assert current['interruption_fixture']['diagnostic_reason'] == 'CAPACITY_RESERVE_NOT_MET'
            elif label == 'live-cancel':
                assert calls == [('spawn',), ('signal', 123), ('wait', 60)]
            elif label == 'live-deadline':
                assert calls == [('spawn',), ('wait', 120)]
            else:
                assert calls == [('spawn',), ('terminate',), ('wait', 60)]
            assert 'PRIVATE_SENTINEL' not in json.dumps(current)
            cases.append({'case': label, 'result': 'PASS_CONTROLLED_LOOP', 'scope': 'EXACT_LOOP_WITH_CONTROLLED_POPEN_WINAPI_SEAMS'})
    receipt = {'schema': 'meownero-i68635-interruption-diagnostic-fixtures/1', 'result': 'PASS',
               'source_sha256': {p.name: SHA(p) for p in (harness_path, diagnostic_path)},
               'fixture_source_sha256': SHA(Path(__file__)), 'cases': cases,
               'packaged_tester_sha256': digest, 'native_acceptance': False}
    args.out.write_text(json.dumps(receipt, indent=2) + '\n')
    print('PASS', len(cases), 'bound early-exit and ownership cases')


if __name__ == '__main__':
    main()
