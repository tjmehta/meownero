#!/usr/bin/env python3
"""Observe the exact packaged journey without changing its checks or bytes."""
import argparse
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tester', type=Path, required=True)
    parser.add_argument('--tester-sha256', required=True)
    parser.add_argument('--diagnostic', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--deadline-seconds', type=int)
    args = parser.parse_args()
    assert args.deadline_seconds is None or 1 <= args.deadline_seconds <= 1200, 'deadline must be within 1..1200 seconds'
    receipt = {'schema': 'meownero-bound-journey-diagnostic/1', 'result': 'FAIL',
               'tester_sha256': args.tester_sha256, 'phase': 'VERIFY_BOUND_TESTER',
               'completed_phases': [], 'available_memory_bytes': None,
               'disk_free_bytes_used_by_guard': None}
    destination = args.diagnostic.absolute()
    assert destination.parent.is_dir()
    assert not destination.exists() and not any(p.is_symlink() or
        getattr(p.lstat(), 'st_file_attributes', 0) & 0x400 for p in destination.parents)
    with destination.open('x', encoding='utf-8') as stream:
        os.chmod(destination, 0o600)
        stream.write(json.dumps(receipt, indent=2) + '\n')

    def save():
        info = destination.lstat()
        assert stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and not destination.is_symlink()
        with destination.open('r+', encoding='utf-8') as stream:
            stream.write(json.dumps(receipt, indent=2) + '\n')
            stream.truncate()

    def failure(error):
        if 'first_failure' in receipt:
            return
        reasons = {
            'requires five GiB available memory and disk': 'CAPACITY_RESERVE_NOT_MET',
            'output must be new under an existing parent': 'OUTPUT_COLLISION_OR_PARENT',
            'tester busy; no processes started': 'TESTER_LOCK_BUSY',
            'wrong architecture': 'TARGET_MISMATCH', 'wrong operating system': 'OS_MISMATCH',
            'wrong source pin': 'SOURCE_PIN_MISMATCH', 'package file set mismatch': 'PACKAGE_FILE_SET',
            'symlink path refused': 'SYMLINK_PATH_REFUSED', 'unsafe tester lock': 'UNSAFE_LOCK',
            'native journey interrupted or deadline reached': 'JOURNEY_INTERRUPTED',
            'owned Windows journey deadline reached': 'WINDOWS_DEADLINE',
            'native CLI could not open restored wallet': 'NATIVE_CLI_RESTORED_WALLET_FAILED',
        }
        prefixes = {'package hash mismatch: ': 'PACKAGE_HASH_MISMATCH',
                    'program startup failed: ': 'VERSION_CHILD_FAILED',
                    'owned process exited: ': 'JOURNEY_CHILD_EXITED',
                    'startup timeout: ': 'NATIVE_STARTUP_TIMEOUT', 'RPC failed: ': 'RPC_FAILURE'}
        # Compare internally; never serialize exception text or traceback.
        message = str(error) if isinstance(error, (RuntimeError, TimeoutError)) or type(error).__name__ == 'JourneyInterrupted' else ''
        reason = reasons.get(message, 'EXCEPTION_UNCLASSIFIED')
        if type(error).__name__ == 'TimeoutExpired' and receipt['phase'] == 'OPEN_NATIVE_CLI':
            reason = 'NATIVE_CLI_WAIT_TIMEOUT'
        for prefix, value in prefixes.items():
            if message.startswith(prefix):
                reason = value
                break
        allowed_types = {'RuntimeError', 'TimeoutError', 'OSError', 'PermissionError', 'FileExistsError',
                         'FileNotFoundError', 'AssertionError', 'JourneyInterrupted', 'KeyboardInterrupt',
                         'ValueError', 'KeyError', 'TypeError', 'URLError', 'HTTPError', 'TimeoutExpired'}
        kind = type(error).__name__
        row = {'phase': receipt['phase'], 'reason': reason,
               'exception_type': kind if kind in allowed_types else 'OTHER_EXCEPTION'}
        for key in ('errno', 'winerror'):
            value = getattr(error, key, None)
            if isinstance(value, int):
                row[key] = value
        receipt['first_failure'] = row
        save()

    old_trace, old_path = sys.gettrace(), list(sys.path)
    module, original_disk_usage = None, None
    try:
        tester = args.tester.absolute()
        assert tester.is_file() and not tester.is_symlink() and tester.stat().st_nlink == 1
        source = tester.read_bytes()
        assert hashlib.sha256(source).hexdigest() == args.tester_sha256
        tree = ast.parse(source)
        run = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'run')
        lines = source.decode().splitlines()
        anchors = {}
        patterns = [
            ('out = safe(out)', 'OUTPUT_GUARD'), ('with lock():', 'ACQUIRE_TESTER_LOCK'),
            ('manifest = preflight(', 'PREFLIGHT'), ('available = available_memory()', 'CAPACITY_GUARD'),
            ('out.mkdir(', 'PREPARE_PRIVATE_OUTPUT'), ('job = portable_windows.Job(', 'INITIALIZE_OWNED_JOB'),
            ('reservations = [socket.socket()', 'RESERVE_LOOPBACK_PORTS'),
            ("start('daemon',", 'START_DAEMON'), ("for name, port in [('sender', sender), ('receiver', receiver),", 'START_WALLETS'),
            ("for name, port in [('sender', sender), ('receiver', receiver)]:", 'CREATE_WALLETS'),
            ('mine(70)', 'FUND_WALLET'), ('first_tx = payment(', 'PAYMENT_RECEIVE'),
            ('seed = rpc(receiver,', 'RESTORE_WALLET'), ('later_tx = payment(', 'PAYMENT_SPEND'),
            ('restored_process = next(', 'OPEN_NATIVE_CLI'), ('preflight(translated_macos_x64)', 'FINAL_PREFLIGHT'),
            ("require(receipt['result'] ==", 'VERIFY_OWNED_CLEANUP')]
        for prefix, phase in patterns:
            matches = [i + 1 for i in range(run.lineno - 1, run.end_lineno) if lines[i].strip().startswith(prefix)]
            assert len(matches) == 1, 'bound phase anchor mismatch'
            anchors[matches[0]] = phase
        finalizers = [n for n in ast.walk(run) if isinstance(n, ast.Try) and n.finalbody and
                      isinstance(n.finalbody[0], ast.If) and isinstance(n.finalbody[0].test, ast.UnaryOp)]
        assert len(finalizers) == 1
        anchors[finalizers[0].finalbody[0].lineno] = 'OWNED_CLEANUP'
        cli_checks = [i + 1 for i in range(run.lineno - 1, run.end_lineno)
                      if lines[i].strip().startswith('require(cli.returncode == 0')]
        assert len(cli_checks) == 1, 'bound native CLI exit anchor mismatch'
        cli_starts = [i + 1 for i in range(run.lineno - 1, run.end_lineno)
                      if lines[i].strip().startswith("cli = spawn('cli',")]
        assert len(cli_starts) == 1, 'bound native CLI start anchor mismatch'
        cli_waits = [i + 1 for i in range(run.lineno - 1, run.end_lineno)
                     if lines[i].strip().startswith('cli.wait(timeout=60)')]
        assert len(cli_waits) == 1, 'bound native CLI wait anchor mismatch'
        sys.path.insert(0, str(tester.parent))
        spec = importlib.util.spec_from_file_location('bound_portable_journey', tester)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        original_disk_usage = module.shutil.disk_usage

        def disk_usage(path):
            value = original_disk_usage(path)
            if receipt['phase'] == 'CAPACITY_GUARD' and Path(path) == args.out.parent:
                receipt['disk_free_bytes_used_by_guard'] = int(value.free)
                save()
            return value

        module.shutil.disk_usage = disk_usage
        seen = set()
        cli_clock = {}

        def trace(frame, event, value):
            if frame.f_code is not module.run.__code__:
                return None
            if event == 'line':
                if frame.f_lineno == cli_starts[0]:
                    cli_clock['started'] = time.time()
                if frame.f_lineno == cli_waits[0]:
                    cli = frame.f_locals['cli']
                    assert any(name == 'cli' and child is cli for name, child in frame.f_locals['processes'])
                    receipt['native_cli'] = {'pid': cli.pid, 'exit': None, 'exit_class': 'RUNNING',
                        'stage': 'OPEN_RESTORED_WALLET_BALANCE',
                        'started_epoch_seconds': cli_clock['started'], 'observed_exit_epoch_seconds': None}
                    save()
                if frame.f_lineno == cli_checks[0]:
                    cli = frame.f_locals.get('cli')
                    owned = frame.f_locals.get('processes', [])
                    assert any(name == 'cli' and child is cli for name, child in owned), 'unowned CLI observation'
                    assert type(cli.pid) is int and type(cli.returncode) is int, 'CLI exit must be observed after wait'
                    status = cli.returncode
                    receipt['native_cli'] = {'pid': cli.pid, 'exit': status,
                        'started_epoch_seconds': cli_clock['started'], 'observed_exit_epoch_seconds': time.time(),
                        'stage': 'OPEN_RESTORED_WALLET_BALANCE',
                        'exit_class': 'SUCCESS' if status == 0 else
                            'ACCESS_VIOLATION_STATUS' if status == 0xC0000005 else 'OTHER_NONZERO_STATUS'}
                    save()
                available = frame.f_locals.get('available')
                if isinstance(available, int):
                    receipt['available_memory_bytes'] = available
                phase = anchors.get(frame.f_lineno)
                if phase and phase not in seen:
                    if 'first_failure' not in receipt:
                        receipt['completed_phases'].append(receipt['phase'])
                    receipt['phase'] = phase
                    seen.add(phase)
                    save()
            elif event == 'exception':
                if frame.f_lineno == cli_waits[0] and type(value[1]).__name__ == 'TimeoutExpired':
                    receipt['native_cli']['exit_class'] = 'WAIT_TIMEOUT'
                failure(value[1])
            return trace

        receipt['phase'] = 'CALL_BOUND_JOURNEY'
        save()
        sys.settrace(trace)
        if args.deadline_seconds is None:
            module.run(args.out)
        else:
            module.run(args.out, deadline_seconds=args.deadline_seconds)
        receipt['result'] = 'PASS_BOUND_JOURNEY_CALL'
        receipt['completed_phases'].append('VERIFY_OWNED_CLEANUP')
    except BaseException as error:
        failure(error)
        raise
    finally:
        sys.settrace(old_trace)
        sys.path[:] = old_path
        if module is not None and original_disk_usage is not None:
            module.shutil.disk_usage = original_disk_usage
        receipt['journey_public_receipt_exists'] = (args.out / 'result.json').is_file()
        save()


if __name__ == '__main__':
    main()
