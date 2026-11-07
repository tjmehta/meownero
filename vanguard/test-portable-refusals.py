#!/usr/bin/env python3
"""Exercise actual package refusals and owned cleanup on its runtime target."""
import argparse
import os
if os.name == 'posix':
    import fcntl
import hashlib
import json
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import importlib.util
import stat


def interruption_observation(journey, diagnostic, tester_sha256, child_exit, began, project):
    """Keep early-exit scalars and the existing bound diagnostic projection."""
    value = {'child_exit': child_exit, 'elapsed_seconds': round(time.monotonic() - began, 6),
             'output_exists': journey.is_dir(), 'result_exists': (journey / 'result.json').is_file(),
             'diagnostic_status': 'MISSING', 'diagnostic_phase': 'UNKNOWN', 'diagnostic_reason': 'UNKNOWN'}
    if not diagnostic.exists():
        return value
    try:
        info = diagnostic.lstat()
        assert stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= 32 * 1024
        assert not any(p.is_symlink() or getattr(p.lstat(), 'st_file_attributes', 0) & 0x400
                       for p in (diagnostic, *diagnostic.parents))
        bound = project(json.loads(diagnostic.read_text()))
        assert bound['tester_sha256'] == tester_sha256
        first = bound.get('first_failure', {})
        value.update(diagnostic_status='BOUND', diagnostic_phase=first.get('phase', bound['phase']),
                     diagnostic_reason=first.get('reason', 'UNKNOWN'))
        for key in ('available_memory_bytes', 'disk_free_bytes_used_by_guard'):
            if key in bound:
                value[key] = bound[key]
    except (OSError, ValueError, AssertionError, KeyError, TypeError, OverflowError):
        value['diagnostic_status'] = 'INVALID'
    return value


def main():
    def cancelled(signum, frame):
        raise RuntimeError('control harness interrupted; stop its owned tester')
    signal.signal(signal.SIGTERM, cancelled)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--translated-macos-x86_64', action='store_true')
    args = parser.parse_args()
    package, out = args.package.resolve(), args.out.resolve()
    windows = os.name == 'nt'
    monerod = 'monerod.exe' if windows else 'monerod'
    assert not out.exists() and out.parent.is_dir()
    out.mkdir(mode=0o700)
    rows = []
    current = {'case': 'clean-preflight', 'phase': 'PREFLIGHT', 'reason_enum': 'CLEAN_PREFLIGHT_FAILED'}
    receipt = {'schema': 'meownero-portable-controls/2', 'result': 'FAIL_REFUSALS',
               'release_manifest_sha256': hashlib.sha256((package / 'release.json').read_bytes()).hexdigest(),
               'cases': rows}

    def begin(case, phase, reason):
        current.clear()
        current.update(case=case, phase=phase, reason_enum=reason)

    def expect(condition, reason):
        current['reason_enum'] = reason
        if not condition:
            raise AssertionError(reason)

    def invoke(root, action='preflight', extra=()):
        translated = ['--translated-macos-x86_64'] if args.translated_macos_x86_64 else []
        return subprocess.run([sys.executable, '-B', str(root / 'tester.py'), action, *translated, *extra],
                              capture_output=True, text=True, timeout=60)

    def refuse(name, mutate, reason):
        begin(name, 'MUTATE_PACKAGE', 'PACKAGE_COPY_OR_MUTATION_ERROR')
        root = out / name
        shutil.copytree(package, root)
        try:
            mutate(root)
        except OSError as error:
            # Only fixture creation can be unavailable. Copy/preflight failures
            # and every other OS error still fail the control.
            if not (windows and name == 'symlink-directory' and getattr(error, 'winerror', None) == 1314):
                raise
            rows.append({'case': name, 'status': 'NOT_EXECUTED',
                         'reason_enum': 'SYMLINK_PRIVILEGE_NOT_HELD', 'winerror': 1314})
            return
        current.update(phase='RUN_PREFLIGHT', reason_enum='TESTER_INVOCATION_ERROR')
        result = invoke(root)
        current.update(phase='REFUSAL_ASSERTION', child_exit=result.returncode)
        expect(result.returncode != 0 and reason in result.stderr, 'EXPECTED_REFUSAL_NOT_OBSERVED')
        rows.append({'case': name, 'refused': True})

    def change_manifest(root, key, value):
        path = root / 'release.json'
        data = json.loads(path.read_text())
        data[key] = value
        path.write_text(json.dumps(data))

    try:
        expect(invoke(package).returncode == 0, 'CLEAN_PREFLIGHT_FAILED')
        refuse('wrong-pin', lambda root: change_manifest(root, 'upstream_commit', '0' * 40), 'wrong source pin')
        arch = json.loads((package / 'release.json').read_text())['architecture']
        diagnostic_wrapper = None
        if windows and arch == 'i686':
            diagnostic_wrapper = Path(__file__).with_name('run-portable-journey-diagnostic.py')
            assert diagnostic_wrapper.is_file() and not diagnostic_wrapper.is_symlink()
            spec = importlib.util.spec_from_file_location('bound_control_projection', Path(__file__).with_name('run-portable-ci.py'))
            projection = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(projection)
            tester_digest = hashlib.sha256((package / 'tester.py').read_bytes()).hexdigest()
        refuse('wrong-target', lambda root: change_manifest(root, 'architecture',
               'aarch64' if arch != 'aarch64' else 'x86_64'), 'wrong architecture')
        refuse('changed-binary', lambda root: (root / 'bin' / monerod).write_bytes(b'changed'), 'package hash mismatch')
        refuse('unlisted-private-file', lambda root: (root / 'wallet.keys').write_text('disposable sentinel'),
               'package file set mismatch')
        refuse('symlink-directory', lambda root: (root / 'linked').symlink_to(out, target_is_directory=True),
               'package symlink refused')
        refuse('hardlink', lambda root: os.link(root / 'bin' / monerod, out / 'extra-hardlink'), 'hard-linked input refused')
        begin('collision-preservation', 'OUTPUT_COLLISION', 'COLLISION_FIXTURE_ERROR')
        collision = out / 'existing-output'
        collision.mkdir()
        sentinel = collision / 'keep'
        sentinel.write_text('must survive')
        result = invoke(package, 'run', ('--out', str(collision)))
        current['child_exit'] = result.returncode
        expect(result.returncode != 0 and 'output must be new' in result.stderr and sentinel.read_text() == 'must survive', 'OUTPUT_COLLISION_OR_PRESERVATION_REFUSAL_FAILED')
        rows.append({'case': 'collision-preservation', 'refused': True, 'sentinel_preserved': True})
        begin('busy-lock', 'LOCK_CONTENTION', 'LOCK_CONTENTION_REFUSAL_FAILED')
        if windows:
            spec = importlib.util.spec_from_file_location('windows_backend', package / 'portable_windows.py')
            backend = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(backend)
            with backend.lock(lambda path: path):
                result = invoke(package)
                assert result.returncode != 0 and 'tester busy' in result.stderr
        else:
            lock = Path(tempfile.gettempdir()) / ('meownero-vanguard-tester-' + str(os.getuid()) + '.lock')
            with lock.open('r+b') as stream:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                result = invoke(package)
                assert result.returncode != 0 and 'tester busy' in result.stderr
        rows.append({'case': 'busy-lock', 'refused': True})
        interruptions = [('cancelled', signal.CTRL_BREAK_EVENT), ('deadline', None)] if windows else [('cancelled', signal.SIGTERM), ('deadline', signal.SIGALRM)]
        for name, interruption in interruptions:
            begin(name + '-owned-cleanup', 'START_INTERRUPTION_FIXTURE', 'INTERRUPTION_FIXTURE_LAUNCH_ERROR')
            journey = out / name
            with (out / (name + '.log')).open('wb') as log:
                child = None
                mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGINT}) if not windows else None
                try:
                    translated = ['--translated-macos-x86_64'] if args.translated_macos_x86_64 else []
                    if windows and name == 'deadline':
                        translated += ['--deadline-seconds', '5']
                    argv = [sys.executable, '-B', str(package / 'tester.py'), 'run', '--out', str(journey), *translated]
                    diagnostic = out / (name + '-journey-diagnostic.json')
                    if diagnostic_wrapper is not None:
                        argv = [sys.executable, '-B', str(diagnostic_wrapper), '--tester', str(package / 'tester.py'),
                                '--tester-sha256', tester_digest, '--diagnostic', str(diagnostic), '--out', str(journey), *translated]
                    started = time.monotonic()
                    child = subprocess.Popen(argv,
                        stdout=log, stderr=subprocess.STDOUT,
                        **({'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP} if windows else {'preexec_fn': lambda: signal.pthread_sigmask(signal.SIG_SETMASK, mask)}))
                    if not windows:
                        signal.pthread_sigmask(signal.SIG_SETMASK, mask)
                    end = time.monotonic() + 60
                    fixture = journey / ('private/daemon.log' if windows and name == 'deadline' else 'private/sender.log')
                    while not fixture.exists() and child.poll() is None and time.monotonic() < end:
                        time.sleep(0.1)
                    current['phase'] = 'WAIT_LIVE_INTERRUPTION_FIXTURE'
                    if diagnostic_wrapper is not None:
                        current['interruption_fixture'] = interruption_observation(journey, diagnostic, tester_digest,
                            child.poll(), started, projection.public_diagnostic)
                        current['interruption_fixture']['fixture_exists'] = fixture.is_file()
                    expect(child.poll() is None and fixture.exists(), 'NATIVE_INTERRUPTION_FIXTURE_NOT_LIVE')
                    if interruption is not None:
                        current.update(phase='DELIVER_INTERRUPTION', reason_enum='INTERRUPTION_SIGNAL_DELIVERY_ERROR')
                        child.send_signal(interruption)
                    current.update(phase='WAIT_INTERRUPTED_EXIT', reason_enum='INTERRUPTED_EXIT_WAIT_ERROR')
                    current['child_exit'] = child.wait(timeout=120 if windows and interruption is None else 60)
                    expect(current['child_exit'] != 0, 'INTERRUPTED_ATTEMPT_PASSED')
                finally:
                    if not windows:
                        signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGINT})
                    if child is not None and child.poll() is None:
                        child.terminate()
                        try:
                            child.wait(timeout=60)
                        except subprocess.TimeoutExpired:
                            child.kill()
                            child.wait(timeout=5)
                    if not windows:
                        signal.pthread_sigmask(signal.SIG_SETMASK, mask)
            current.update(phase='VERIFY_INTERRUPTED_CLEANUP', reason_enum='INTERRUPTED_RECEIPT_UNAVAILABLE')
            interrupted = json.loads((journey / 'result.json').read_text())
            expect(interrupted['result'] == 'FAIL_NATIVE_JOURNEY' and interrupted['cleanup'] and all(r['removed'] for r in interrupted['cleanup']), 'INTERRUPTED_CLEANUP_RECEIPT_INVALID')
            expect(not windows or interrupted.get('owned_job_cleanup'), 'WINDOWS_OWNED_JOB_CLEANUP_NOT_WITNESSED')
            current.update(phase='VERIFY_PID_REMOVAL', reason_enum='OWNED_PID_STILL_PRESENT')
            for row in interrupted['cleanup']:
                if windows:
                    # Open the recorded PID without creating or signalling anything.
                    handle = backend.api(backend.k, 'OpenProcess', backend.W.HANDLE,
                        backend.W.DWORD, backend.W.BOOL, backend.W.DWORD)(0x100000, False, row['pid'])
                    if handle:
                        try:
                            assert backend._winapi.WaitForSingleObject(handle, 0) == 0, 'owned process remains'
                        finally:
                            backend.close(handle)
                    continue
                try:
                    os.kill(row['pid'], 0)
                except ProcessLookupError:
                    pass
                else:
                    raise AssertionError('owned process remains')
            rows.append({'case': name + '-owned-cleanup', 'signal': ('CTRL_BREAK_EVENT' if windows else interruption.name) if interruption is not None else 'WINDOWS_JOB_TIMER',
                         'removed': True, 'process_count': len(interrupted['cleanup'])})
        receipt['result'] = 'INCOMPLETE_REFUSALS' if any(row.get('status') == 'NOT_EXECUTED' for row in rows) else 'PASS_REFUSALS'
    except BaseException as error:
        receipt['first_failed_case'] = {**current, 'failure_type': type(error).__name__}
        for attribute in ('errno', 'winerror'):
            value = getattr(error, attribute, None)
            if isinstance(value, int):
                receipt['first_failed_case'][attribute] = value
        raise
    finally:
        # Only static case/phase/reason and scalar exit/OS codes leave this harness.
        # Captured tester output and private interruption logs remain private.
        mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGINT}) if not windows else None
        try:
            (out / 'controls.json').write_text(json.dumps(receipt, indent=2) + '\n')
        finally:
            if not windows:
                signal.pthread_sigmask(signal.SIG_SETMASK, mask)
    print(receipt['result'], len(rows))
    return 2 if receipt['result'] == 'INCOMPLETE_REFUSALS' else 0


if __name__ == '__main__':
    raise SystemExit(main())
