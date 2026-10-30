#!/usr/bin/env python3
"""Report-boundary regressions. Process/RPC fixtures do not qualify Windows."""
import argparse
from contextlib import nullcontext
import copy
import hashlib
import importlib.machinery
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import urllib.error
import zipfile

ROOT = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser()
parser.add_argument('--helpers', type=Path, default=ROOT / 'vanguard')
parser.add_argument('--package-archive', type=Path, default=ROOT / 'build/tjs1882-run62675-windows-successor-final/meownero-windows-test/meownero-vanguard-windows-i686-sanitized-v1.zip')
parser.add_argument('--evidence', type=Path)
args, remaining = parser.parse_known_args()
if args.evidence:
    args.evidence.mkdir(parents=True, exist_ok=True)

def retain(path, name):
    if args.evidence:
        (args.evidence / name).write_bytes(path.read_bytes())

def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, args.helpers / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

ci = load('fix_ci', 'run-portable-ci.py')
bundle = load('fix_bundle', 'windows-test-bundle.py')
PRIVATE = 'PRIVATE_WALLET_SEED_LOG_SENTINEL'

class ControlTests(unittest.TestCase):
    def exercise(self, fault=None):
        with tempfile.TemporaryDirectory(prefix='tjs1882-control-fix-') as folder:
            base = Path(folder)
            package = base / 'package'; package.mkdir(); (package / 'bin').mkdir()
            (package / 'bin/monerod.exe').write_bytes(b'fixture')
            (package / 'tester.py').write_text('# no native execution\n')
            (package / 'portable_windows.py').write_text('# fixture backend\n')
            (package / 'release.json').write_text(json.dumps({'architecture': 'aarch64'}))
            controls = load('fix_controls', 'test-portable-refusals.py')
            # Change only this module's platform view, never pathlib's os.name.
            controls.os = SimpleNamespace(**{**vars(os), 'name': 'nt'})
            busy = [False]
            class Lock:
                def __enter__(self): busy[0] = True
                def __exit__(self, *error): busy[0] = False
            original_load = importlib.machinery.SourceFileLoader.exec_module
            def backend_load(loader, module):
                if module.__name__ == 'windows_backend':
                    module.lock = lambda *a: Lock()
                    module.k = None; module.W = SimpleNamespace(HANDLE=None, DWORD=None, BOOL=None)
                    module.api = lambda *a: lambda *a: 0
                else:
                    original_load(loader, module)
            reasons = {'wrong-pin': 'wrong source pin', 'wrong-target': 'wrong architecture',
                'changed-binary': 'package hash mismatch', 'unlisted-private-file': 'package file set mismatch',
                'symlink-directory': 'package symlink refused', 'hardlink': 'hard-linked input refused'}
            def invoke(argv, **kw):
                name = Path(argv[2]).parent.name
                rc, stderr = 1, reasons.get(name, '')
                if name == 'package':
                    rc, stderr = (1, 'tester busy') if busy[0] else (0, '')
                    if 'run' in argv: rc, stderr = 1, 'output must be new'
                if fault == 'refusal' and name == 'symlink-directory': rc = 0
                if fault == 'later-refusal' and name == 'hardlink': rc = 0
                return subprocess.CompletedProcess(argv, rc, PRIVATE, stderr + ' ' + PRIVATE)
            original_link = Path.symlink_to
            def link(path, *a, **kw):
                if fault in ('1314', 'other', 'later-refusal'):
                    error = OSError(22, PRIVATE); error.winerror = 1314 if fault != 'other' else 5
                    raise error
                return original_link(path, *a, **kw)
            class Child:
                pid = 12345
                def __init__(self, argv, **kw):
                    self.returncode = None
                    journey = Path(argv[argv.index('--out') + 1])
                    (journey / 'private').mkdir(parents=True)
                    for name in ('sender.log', 'daemon.log'): (journey / 'private' / name).write_text(PRIVATE)
                    (journey / 'result.json').write_text(json.dumps({'result': 'FAIL_NATIVE_JOURNEY',
                        'cleanup': [{'pid': self.pid, 'removed': True}], 'owned_job_cleanup': True}))
                def poll(self): return self.returncode
                def send_signal(self, value): self.returncode = 1
                def wait(self, **kw): self.returncode = 1; return 1
                def terminate(self): self.returncode = 1
                def kill(self): self.returncode = 1
            out = base / 'controls'
            with patch.object(sys, 'argv', ['controls', '--package', str(package), '--out', str(out)]), \
                 patch.object(controls.subprocess, 'run', invoke), patch.object(controls.subprocess, 'Popen', Child), \
                 patch.object(Path, 'symlink_to', link), patch.object(signal, 'CTRL_BREAK_EVENT', 1, create=True), \
                 patch.object(controls.subprocess, 'CREATE_NEW_PROCESS_GROUP', 0x200, create=True), \
                 patch.object(importlib.machinery.SourceFileLoader, 'exec_module', backend_load):
                error = None
                try: code = controls.main()
                except BaseException as e: error = e; code = 1
            value = json.loads((out / 'controls.json').read_text())
            self.assertNotIn(PRIVATE, json.dumps(value))
            # Exercise the real ZIP allowlist, not a parallel serializer.
            public = base / 'public'; public.mkdir()
            (public / 'controls.json').write_text(json.dumps(value))
            bundle.export_report(base / 'report.zip', {'result': value['result'], 'evidence': 'SYNTHETIC_NO_WINDOWS_EXECUTION'}, public)
            with zipfile.ZipFile(base / 'report.zip') as z:
                self.assertEqual(json.loads(z.read('public/controls.json')), value)
                self.assertNotIn(PRIVATE.encode(), b''.join(z.read(n) for n in z.namelist()))
            retain(base / 'report.zip', 'control-' + str(fault) + '-report.zip')
            return value, code, error

    def test_1314_incomplete_continues_all_later_controls(self):
        value, code, error = self.exercise('1314')
        self.assertIsNone(error)
        self.assertEqual((value['result'], code), ('INCOMPLETE_REFUSALS', 2))
        self.assertEqual(len(value['cases']), 10)
        self.assertEqual(value['cases'][4], {'case': 'symlink-directory', 'status': 'NOT_EXECUTED',
            'reason_enum': 'SYMLINK_PRIVILEGE_NOT_HELD', 'winerror': 1314})
        self.assertTrue(ci.control_coverage(value))
        for bad in ('refused', 'winerror'):
            forged = copy.deepcopy(value)
            forged['cases'][4][bad] = True if bad == 'refused' else 5
            with self.assertRaises(AssertionError): ci.control_coverage(forged)

    def test_real_symlink_fixture_and_refusal_success(self):
        value, code, error = self.exercise()
        self.assertIsNone(error)
        self.assertEqual((value['result'], code), ('PASS_REFUSALS', 0))
        self.assertFalse(ci.control_coverage(value))

    def test_other_fixture_error_still_fails(self):
        value, code, error = self.exercise('other')
        self.assertIsInstance(error, OSError)
        self.assertEqual(value['result'], 'FAIL_REFUSALS')
        self.assertEqual(value['first_failed_case']['winerror'], 5)
        self.assertEqual(len(value['cases']), 4)

    def test_actual_refusal_failure_still_fails(self):
        value, code, error = self.exercise('refusal')
        self.assertIsInstance(error, AssertionError)
        self.assertEqual(value['result'], 'FAIL_REFUSALS')
        self.assertEqual(value['first_failed_case']['reason_enum'], 'EXPECTED_REFUSAL_NOT_OBSERVED')

    def test_later_failure_overrides_incomplete(self):
        value, code, error = self.exercise('later-refusal')
        self.assertIsInstance(error, AssertionError)
        self.assertEqual(value['result'], 'FAIL_REFUSALS')
        self.assertEqual(value['first_failed_case']['case'], 'hardlink')

class FundingTests(unittest.TestCase):
    def exercise(self, failing):
        diagnostic = load('fix_diagnostic', 'run-portable-journey-diagnostic.py')
        with tempfile.TemporaryDirectory(prefix='tjs1882-funding-fix-') as folder:
            base = Path(folder); package = base / 'package'; package.mkdir()
            with zipfile.ZipFile(args.package_archive) as archive:
                prefix = next(n for n in archive.namelist() if n.endswith('/release.json'))[:-len('release.json')]
                release = json.loads(archive.read(prefix + 'release.json'))
                for name in ['release.json', 'tester.py', *['bin/' + n + '.exe' for n in ('monerod','monero-wallet-cli','monero-wallet-rpc')]]:
                    data = archive.read(prefix + name)
                    if name != 'release.json': self.assertEqual(hashlib.sha256(data).hexdigest(), release['files'][name])
                    dest = package / name; dest.parent.mkdir(exist_ok=True); dest.write_bytes(data)
            tester = package / 'tester.py'; digest = hashlib.sha256(tester.read_bytes()).hexdigest()
            processes = []; roles = {}; module_holder = []
            class Process:
                def __init__(self, executable): self.pid = 9000 + len(processes); self.returncode = None; self.executable = executable
                def poll(self): return self.returncode
                def terminate(self): self.returncode = 1
                def kill(self): self.returncode = 1
                def wait(self, **kw): self.returncode = 1; return 1
            class Job:
                expired = False
                def __init__(self, **kw): pass
                def spawn(self, executable, arguments, stream, *unused):
                    process = Process(executable); processes.append(process)
                    if '--rpc-bind-port' in arguments:
                        port = int(arguments[arguments.index('--rpc-bind-port')+1]); roles[port] = 'node' if executable.stem == 'monerod' else len(roles)
                    return process
                def close(self):
                    for process in processes: process.terminate()
                    self.cleanup = {'active_processes': 0, 'children': [{'pid': p.pid, 'exit': 1} for p in processes]}
            class Response(io.BytesIO): pass
            class Opener:
                def open(self, request, timeout):
                    self_outer.assertEqual(timeout, 90)
                    data = json.loads(request.data); method = data['method']
                    if method == failing: raise TimeoutError(PRIVATE)
                    if failing == 'wrapped' and method == 'refresh': raise urllib.error.URLError(TimeoutError(PRIVATE))
                    if method == 'transfer': raise RuntimeError(PRIVATE)
                    result = {'get_address': {'address': PRIVATE}, 'generateblocks': {'blocks': list(range(70))},
                              'get_balance': {'balance': 10**14}}.get(method, {})
                    return Response(json.dumps({'result': result}).encode())
            self_outer = self
            original_load = importlib.machinery.SourceFileLoader.exec_module
            def instrument(loader, module):
                original_load(loader, module)
                if module.__name__ != 'bound_portable_journey': return
                module_holder.append(module)
                module.preflight = lambda *a: release
                module.lock = nullcontext
                module.available_memory = lambda: 8 * 1024**3
                module.WINDOWS = True
                module.portable_windows = SimpleNamespace(Job=Job, native_architecture=lambda: 'x86_64',
                    mapped_paths=lambda p: (p.executable, []))
                module.child_environment = lambda: {}
            out, journal = base / 'journey', base / 'diagnostic.json'
            with patch.object(sys, 'argv', ['diagnostic', '--tester', str(tester), '--tester-sha256', digest,
                    '--diagnostic', str(journal), '--out', str(out)]), \
                 patch.object(importlib.machinery.SourceFileLoader, 'exec_module', instrument), \
                 patch('urllib.request.build_opener', lambda *a: Opener()), \
                 patch.object(signal, 'SIGBREAK', signal.SIGUSR1, create=True):
                with self.assertRaises((TimeoutError, RuntimeError, urllib.error.URLError)):
                    diagnostic.main()
            value = json.loads(journal.read_text())
            projected = ci.public_diagnostic(value)
            journey = json.loads((out / 'result.json').read_text())
            self.assertEqual(len(processes), 4)
            self.assertTrue(journey['owned_job_cleanup'])
            self.assertTrue(all(p['removed'] for p in journey['cleanup']))
            self.assertTrue(all(p.poll() is not None for p in processes))
            self.assertNotIn(PRIVATE, json.dumps(projected))
            public = base / 'public'; public.mkdir()
            (public / 'journey-diagnostic.json').write_text(json.dumps(projected))
            (public / 'journey.json').write_text(json.dumps(journey))
            (public / 'seed.txt').write_text(PRIVATE)
            bundle.export_report(base / 'report.zip', {'result': 'FAIL', 'evidence': 'SYNTHETIC_NO_WINDOWS_EXECUTION'}, public)
            with zipfile.ZipFile(base / 'report.zip') as z:
                self.assertEqual(json.loads(z.read('public/journey-diagnostic.json')), projected)
                self.assertNotIn(PRIVATE.encode(), b''.join(z.read(n) for n in z.namelist()))
            retain(base / 'report.zip', 'funding-' + str(failing) + '-report.zip')
            return projected

    def test_each_funding_timeout_has_distinct_exported_operation(self):
        for method in ('generateblocks', 'refresh', 'get_balance'):
            with self.subTest(operation=method):
                value = self.exercise(method)
                self.assertEqual(value['first_failure']['phase'], 'FUND_WALLET')
                self.assertEqual(value['first_failure']['reason'], 'FUNDING_RPC_TIMEOUT')
                self.assertEqual(value['first_failure']['operation'], method)
                rows = value['funding_operations']
                self.assertEqual(rows[-1]['operation'], method)
                self.assertEqual(rows[-1]['outcome'], 'TIMEOUT')
                self.assertTrue(all(r['outcome'] == 'PASS' for r in rows[:-1]))
                for row in rows:
                    self.assertEqual(row['socket_timeout_seconds'], 90)
                    self.assertEqual(row['journey_deadline_seconds'], 1200)
                    self.assertTrue(math.isfinite(row['elapsed_seconds']))

    def test_successful_funding_does_not_attribute_later_error(self):
        value = self.exercise(None)
        self.assertEqual([r['outcome'] for r in value['funding_operations']], ['PASS'] * 3)
        self.assertEqual(value['first_failure']['phase'], 'PAYMENT_RECEIVE')
        self.assertNotIn('operation', value['first_failure'])

    def test_wrapped_socket_timeout(self):
        value = self.exercise('wrapped')
        self.assertEqual(value['first_failure']['operation'], 'refresh')
        self.assertEqual(value['first_failure']['reason'], 'FUNDING_RPC_TIMEOUT')

    def test_projector_rejects_malformed_operations_and_times(self):
        good = self.exercise('get_balance')
        for field, bad in [('operation', PRIVATE), ('elapsed_seconds', float('nan')),
                ('elapsed_seconds', float('inf')), ('elapsed_seconds', -1), ('elapsed_seconds', True),
                ('socket_timeout_seconds', 180), ('journey_remaining_at_start_seconds', 1201)]:
            value = copy.deepcopy(good); value['funding_operations'][0][field] = bad
            with self.assertRaises(AssertionError): ci.public_diagnostic(value)
        value = copy.deepcopy(good); value['funding_operations'] *= 2
        with self.assertRaises(AssertionError): ci.public_diagnostic(value)
        value = copy.deepcopy(good); value['funding_operations'][0]['private'] = PRIVATE
        self.assertNotIn(PRIVATE, json.dumps(ci.public_diagnostic(value)))

if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0], *remaining])
