#!/usr/bin/env python3
"""Check hash-bound private CI payloads; export only allowlisted public receipts."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import signal
import stat
import subprocess
import sys
import tarfile
import time
import zipfile

ROOT = Path(__file__).resolve().parent.parent


def sha(path):
    assert path.is_file() and not path.is_symlink() and path.stat().st_nlink == 1
    return hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def mac_check(argv, out, public, *, timeout=1500, cleanup_seconds=240):
    """Allow wrapper cleanup before escalating only recorded, verified children."""
    receipt = {'schema': 'meownero-native-mac-ci-supervision/1', 'result': 'FAIL',
               'wrapper_reaped': False, 'cleanup': [], 'signals': []}
    known, pending = {}, []
    process = None
    began = time.monotonic()

    def snapshot():
        rows = {}
        for line in subprocess.check_output(['/bin/ps', '-axo', 'pid=,ppid=,uid=,lstart=,command='],
                                            text=True, timeout=5).splitlines():
            fields = line.split(None, 8)
            if len(fields) == 9:
                rows[int(fields[0])] = (int(fields[1]), int(fields[2]), tuple(fields[3:8]), fields[8])
        return rows

    def remember():
        running = process is not None and process.poll() is None
        rows = snapshot()
        if process is not None and process.poll() is not None:
            # Reap our direct child before evaluating a stale ps zombie row.
            rows.pop(process.pid, None)
            running = False
        if running:
            owned = {process.pid}
            while True:
                children = {pid for pid, row in rows.items() if row[0] in owned}
                if children <= owned:
                    break
                owned |= children
            for pid in owned & rows.keys():
                row = rows[pid]
                assert row[1] == os.getuid(), 'owned child UID changed'
                known[pid] = row[1:]
        return rows

    def remaining():
        rows = remember()
        alive = []
        for pid, identity in known.items():
            if pid in rows:
                assert rows[pid][1:] == identity, 'remembered PID identity changed; preserve process'
                alive.append(pid)
        return alive

    handlers = {s: signal.signal(s, lambda number, frame: pending.append(number))
                for s in (signal.SIGINT, signal.SIGTERM)}
    mask = signal.pthread_sigmask(signal.SIG_BLOCK, set(handlers))
    try:
        with (out / 'mac-wrapper.log').open('wb') as stream:
            process = subprocess.Popen([str(value) for value in argv], stdout=stream,
                stderr=subprocess.STDOUT, start_new_session=True,
                preexec_fn=lambda: signal.pthread_sigmask(signal.SIG_SETMASK, mask))
            receipt['wrapper_pid'] = process.pid
            remember()
            signal.pthread_sigmask(signal.SIG_SETMASK, mask)
            while process.poll() is None:
                remember()
                if pending:
                    raise RuntimeError('CI cancelled; forward to owned Mac wrapper')
                if time.monotonic() - began >= timeout:
                    raise subprocess.TimeoutExpired(argv, timeout)
                try:
                    process.wait(timeout=0.25)
                except subprocess.TimeoutExpired:
                    pass
            assert process.returncode == 0 and not pending, 'native Intel archive check failed'
            receipt['result'] = 'PASS_WRAPPER_AND_OWNED_CLEANUP'
    except BaseException as error:
        receipt['failure_type'] = type(error).__name__
        raise
    finally:
        # Repeated cancellation cannot interrupt the bounded cleanup interval.
        signal.pthread_sigmask(signal.SIG_BLOCK, set(handlers))
        try:
            if process is not None:
                end = time.monotonic() + cleanup_seconds
                if process.poll() is None:
                    process.send_signal(signal.SIGTERM)
                    receipt['forwarded_sigterm'] = True
                    # The wrapper owns phase sessions and normally removes them itself.
                    while process.poll() is None and time.monotonic() < end - 20:
                        try:
                            remember()
                        except BaseException as error:
                            receipt['result'] = 'FAIL'
                            receipt['observation_failure_type'] = type(error).__name__
                        try:
                            process.wait(timeout=0.25)
                        except subprocess.TimeoutExpired:
                            pass
                for sig, interval in ((signal.SIGTERM, 10), (signal.SIGKILL, 5)):
                    alive = remaining()
                    if not alive:
                        break
                    receipt['result'] = 'FAIL'
                    for pid in alive:
                        # Re-read identity immediately before each individual signal.
                        rows = snapshot()
                        if pid in rows:
                            assert rows[pid][1:] == known[pid], 'PID reused; preserve process'
                            try:
                                os.kill(pid, sig)
                                receipt['signals'].append({'pid': pid, 'signal': int(sig)})
                            except ProcessLookupError:
                                pass
                    wait_end = min(end, time.monotonic() + interval)
                    while remaining() and time.monotonic() < wait_end:
                        time.sleep(0.1)
                assert process.poll() is not None, 'owned Mac wrapper remains'
                process.wait(timeout=1)
                receipt['wrapper_reaped'] = True
                alive = remaining()
                receipt['cleanup'] = [{'pid': pid, 'removed': pid not in alive} for pid in sorted(known)]
                assert not alive, 'known owned Mac descendants remain'
                if 'failure_type' not in receipt:
                    assert receipt['result'] == 'PASS_WRAPPER_AND_OWNED_CLEANUP', 'native Mac supervision failed'
        except BaseException as error:
            receipt['result'] = 'FAIL'
            receipt['cleanup_failure_type'] = type(error).__name__
            if process is not None and process.poll() is None:
                # Popen identifies our direct child even if ps itself failed.
                process.kill()
                process.wait(timeout=5)
                receipt['signals'].append({'pid': process.pid, 'signal': int(signal.SIGKILL)})
            receipt['wrapper_reaped'] = process is not None and process.poll() is not None
            raise
        finally:
            receipt['wall_seconds'] = round(time.monotonic() - began, 3)
            receipt['cancellation_signals'] = pending
            signal.pthread_sigmask(signal.SIG_SETMASK, mask)
            write(public / 'supervision.json', receipt)
            for sig, handler in handlers.items():
                signal.signal(sig, handler)


def windows_check(package, out, row):
    spec = importlib.util.spec_from_file_location('ci_windows', package / 'portable_windows.py')
    backend = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(backend)
    assert backend.native_architecture() == 'x86_64' and backend.C.sizeof(backend.C.c_void_p) == 8
    receipt = {'schema': 'meownero-native-windows-ci-check/1', 'result': 'FAIL',
               'native_architecture': backend.native_architecture(), 'phases': []}
    architecture = json.loads((package / 'release.json').read_text())['architecture']
    assert architecture in ('i686', 'x86_64')
    assert architecture == row.get('architecture', 'x86_64'), 'Windows package target mismatch'
    receipt['package_architecture'] = architecture
    receipt['execution_substrate'] = 'NATIVE_WINDOWS_WOW64' if architecture == 'i686' else 'NATIVE'
    receipt['windows_32bit_os_execution'] = 'UNTESTED'
    # Console attachment is independent of an HWND, including hosted consoles.
    console_pids = (backend.W.DWORD * 1)()
    console_list = backend.api(backend.k, 'GetConsoleProcessList', backend.W.DWORD,
                               backend.C.POINTER(backend.W.DWORD), backend.W.DWORD)
    receipt['initial_console_process_count'] = console_list(console_pids, 1)
    allocated, job = False, None
    began = time.monotonic()

    def phase(name, argv, timeout=1500):
        argv = [str(value) for value in argv]
        row = {'name': name, 'argv': argv, 'reaped': False}
        receipt['phases'].append(row)
        with (out / (name + '.log')).open('wb') as stream, open(os.devnull, 'rb') as null:
            handles = [backend.msvcrt.get_osfhandle(null.fileno()), backend.msvcrt.get_osfhandle(stream.fileno())]
            inherited = [os.get_handle_inheritable(h) for h in handles]
            startup = subprocess.STARTUPINFO()
            startup.dwFlags = subprocess.STARTF_USESTDHANDLES
            startup.hStdInput, startup.hStdOutput, startup.hStdError = handles[0], handles[1], handles[1]
            startup.lpAttributeList = {'handle_list': handles}
            process = thread = None
            pending = []
            handlers = {s: signal.signal(s, lambda number, frame: pending.append(number))
                        for s in (signal.SIGINT, signal.SIGTERM, signal.SIGBREAK)}
            try:
                for h in handles:
                    os.set_handle_inheritable(h, True)
                # Suspend before registration; inherit the owned console for controls.
                process, thread, pid, _ = backend._winapi.CreateProcess(str(argv[0]),
                    subprocess.list2cmdline([str(x) for x in argv]), None, None, True,
                    4 | subprocess.CREATE_NEW_PROCESS_GROUP, os.environ.copy(), str(out), startup)
                child = backend.Process(process, pid)
                job.children.append(child)
                backend.check(backend.assign(job.handle, process))
                assert not job.expired
                assert backend.api(backend.k, 'ResumeThread', backend.W.DWORD, backend.W.HANDLE)(thread) != 0xffffffff
                row['pid'] = pid
            except BaseException:
                if process is not None:
                    backend._winapi.TerminateProcess(process, 1)
                    backend._winapi.WaitForSingleObject(process, 5000)
                raise
            finally:
                if thread is not None:
                    backend._winapi.CloseHandle(thread)
                for h, value in zip(handles, inherited):
                    os.set_handle_inheritable(h, value)
                for s, handler in handlers.items():
                    signal.signal(s, handler)
            if pending:
                raise RuntimeError('CI cancelled after owned child registration')
            row['exit'] = child.wait(timeout=min(timeout, max(1, 1500 - (time.monotonic() - began))))
            row['reaped'] = child.poll() is not None
            assert row['exit'] == 0 and not job.expired, name + ' failed'
        return row

    try:
        if not receipt['initial_console_process_count']:
            # Detach only this CI process; preserve the hosted shell and its pipes.
            saved = [backend.msvcrt.get_osfhandle(fd) for fd in (0, 1, 2)]
            file_type = backend.api(backend.k, 'GetFileType', backend.W.DWORD, backend.W.HANDLE)
            assert all(file_type(handle) in (1, 3) for handle in saved[1:]), 'CI output must be file or pipe before console detach'
            backend.check(backend.api(backend.k, 'FreeConsole', backend.W.BOOL)())
            backend.check(backend.api(backend.k, 'AllocConsole', backend.W.BOOL)())
            allocated = True
            set_handle = backend.api(backend.k, 'SetStdHandle', backend.W.BOOL, backend.W.DWORD, backend.W.HANDLE)
            for number, handle in zip((-10, -11, -12), saved):
                backend.check(set_handle(number & 0xffffffff, handle))
            assert console_list(console_pids, 1) == 1 and console_pids[0] == os.getpid(), 'new console ownership failed'
        receipt['console_mode'] = 'OWNED_NEW_CONSOLE' if allocated else 'EXISTING_ATTACHED_CONSOLE'
        job = backend.Job(seconds=1500)
        if architecture == 'i686':
            probe = row['native_exception_probe']
            manifest = json.loads((package / 'release.json').read_text())
            assert manifest['native_exception_probe'] == {
                'file': probe['file'], 'native_execution': 'UNTESTED', 'required_for_native_acceptance': True}
            for name, digest in probe['files'].items():
                assert manifest['files'][name] == digest and sha(package / name) == digest, 'exception fixture binding changed'
            result = phase('exception-probe', [package / probe['file']], timeout=60)
            log = out / 'exception-probe.log'
            assert log.stat().st_size <= 64, 'exception fixture output exceeds exact marker'
            marker = log.read_bytes()
            assert marker in (b'PASS_NATIVE_I686_EXCEPTION_PROBE\n', b'PASS_NATIVE_I686_EXCEPTION_PROBE\r\n'), 'exception fixture success marker mismatch'
            receipt['native_exception_probe'] = {
                'result': 'PASS_NATIVE_I686_EXCEPTION_PROBE', 'sha256': probe['files'][probe['file']],
                'source_sha256': probe['files']['build-evidence/i686-exception-probe.cpp'],
                'exit': result['exit'], 'reaped': result['reaped'], 'deadline_seconds': 60,
                'exact_success_line': True, 'newline': 'CRLF' if marker.endswith(b'\r\n') else 'LF',
                'cleanup_count_asserted_by_bound_fixture': 1}
        phase('preflight', [sys.executable, '-B', package / 'tester.py', 'preflight'])
        phase('journey', [sys.executable, '-B', package / 'tester.py', 'run', '--out', out / 'journey'])
        phase('controls', [sys.executable, '-B', ROOT / 'vanguard/test-portable-refusals.py',
                           '--package', package, '--out', out / 'controls'])
        receipt['result'] = 'PASS_NATIVE_ARCHIVE_JOURNEY'
    finally:
        try:
            if job is not None:
                job.close()
                receipt['owned_job'] = job.cleanup
                assert job.cleanup['active_processes'] == 0
            else:
                receipt['owned_job_created'] = False
        except BaseException:
            receipt['result'] = 'FAIL'
            raise
        finally:
            receipt['wall_seconds'] = round(time.monotonic() - began, 3)
            if allocated:
                receipt['owned_console_freed'] = bool(backend.api(backend.k, 'FreeConsole', backend.W.BOOL)())
                if not receipt['owned_console_freed']:
                    receipt['result'] = 'FAIL'
            write(out / 'check-receipt.json', receipt)
            assert not allocated or receipt['owned_console_freed'], 'owned console cleanup failed'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--inputs-sha256', required=True)
    parser.add_argument('--target', choices=['windows-i686', 'windows-x86_64', 'macos-x86_64'], required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--prepare-only', action='store_true', help='Verify bytes only; never execution evidence')
    args = parser.parse_args()
    assert sha(args.inputs) == args.inputs_sha256
    inputs = json.loads(args.inputs.read_text())
    assert inputs['schema'] == 'meownero-private-native-ci-inputs/1'
    for name, digest in inputs['source_files'].items():
        assert sha(ROOT / name) == digest, 'CI helper binding changed: ' + name
    row = inputs['targets'][args.target]
    out = args.out.absolute()
    assert out.parent.is_dir() and not out.exists() and not any(p.is_symlink() for p in (out, *out.parents))
    assert shutil.disk_usage(out.parent).free >= 10 * 1024**3
    out.mkdir(mode=0o700)
    public = out / 'public'
    public.mkdir(mode=0o700)
    proof = {'schema': 'meownero-private-native-ci/1', 'target': args.target, 'result': 'FAIL',
             'inputs_sha256': args.inputs_sha256, 'archive_sha256': row['archive_sha256'],
             'github_run_id': os.environ.get('GITHUB_RUN_ID'), 'github_sha': os.environ.get('GITHUB_SHA'),
             'python': sys.version, 'os': platform.platform(), 'process_architecture': platform.machine()}
    check_root = None
    try:
        archive = out / row['archive_name']
        with archive.open('xb') as output:
            for part in row['parts']:
                source = ROOT / part['path']
                assert source.stat().st_size == part['bytes'] and sha(source) == part['sha256'], 'part binding mismatch'
                with source.open('rb') as stream:
                    shutil.copyfileobj(stream, output, length=1024 * 1024)
        assert archive.stat().st_size == row['archive_bytes'] and sha(archive) == row['archive_sha256']
        extract = out / 'binding-extract'
        extract.mkdir(mode=0o700)
        if args.target.startswith('windows-'):
            with zipfile.ZipFile(archive) as stream:
                seen = set()
                for item in stream.infolist():
                    path = PurePosixPath(item.filename)
                    assert path.parts and path.parts[0] == row['package_name'] and not path.is_absolute()
                    assert '..' not in path.parts and '\\' not in item.filename and item.filename not in seen
                    assert not item.is_dir() and stat.S_ISREG(item.external_attr >> 16)
                    seen.add(item.filename)
                stream.extractall(extract)
        else:
            with tarfile.open(archive) as stream:
                seen = set()
                for item in stream.getmembers():
                    path = PurePosixPath(item.name)
                    assert item.isfile() and path.parts[0] == row['package_name'] and not path.is_absolute()
                    assert '..' not in path.parts and item.name not in seen
                    seen.add(item.name)
                stream.extractall(extract, filter='data')
        package = extract / row['package_name']
        assert sha(package / 'release.json') == row['release_manifest_sha256']
        for name, digest in row['package_helpers'].items():
            assert sha(package / name) == digest, 'package helper mismatch'
        proof['parts_archive_and_helper_binding'] = 'PASS'
        if args.prepare_only:
            proof['result'] = 'PASS_INPUT_BYTES_ONLY_NATIVE_EXECUTION_UNTESTED'
            return
        assert sys.version_info >= (3, 13)
        if args.target.startswith('windows-'):
            assert os.name == 'nt' and platform.machine().upper() in ('AMD64', 'X86_64')
            check_root = out
            windows_check(package, out, row)
        else:
            assert platform.system() == 'Darwin' and platform.machine() == 'x86_64'
            native_spec = importlib.util.spec_from_file_location('packaged_mac_guard', package / 'tester.py')
            native = importlib.util.module_from_spec(native_spec)
            native_spec.loader.exec_module(native)
            assert native.mac_physical_architecture() == 'x86_64'
            lock = Path('/tmp/meownero-swarm-20260912-heavy.lock')
            with lock.open('xb') as stream:
                os.chmod(lock, 0o600)
                lock_identity = lock.stat().st_ino
            check_root = out / 'native-check'
            try:
                mac_check([sys.executable, '-B', ROOT / 'vanguard/run-portable-mac-check.py',
                    '--archive', archive, '--sha256', row['archive_sha256'], '--target', 'macos-x86_64',
                    '--out', check_root], out, public)
            finally:
                supervision = json.loads((public / 'supervision.json').read_text())
                assert supervision['wrapper_reaped'] and all(p['removed'] for p in supervision['cleanup'])
                assert 'cleanup_failure_type' not in supervision, 'preserve lock until owned cleanup is verified'
                assert not lock.is_symlink() and lock.stat().st_uid == os.getuid() and lock.stat().st_ino == lock_identity
                lock.unlink()
                proof['owned_lock_removed'] = True
        journey = json.loads((check_root / 'journey/result.json').read_text())
        controls = json.loads((check_root / 'controls/controls.json').read_text())
        check = json.loads((check_root / 'check-receipt.json').read_text())
        assert journey['result'] == 'PASS_NATIVE_JOURNEY' and journey['cleanup'] and all(x['removed'] for x in journey['cleanup'])
        assert journey['architecture'] == ('i686' if args.target == 'windows-i686' else 'x86_64')
        assert journey['upstream_commit'] == inputs['upstream_commit']
        assert journey['release_manifest_sha256'] == row['release_manifest_sha256']
        assert journey['program_sha256'] == row['program_sha256']
        assert journey['receive_atomic'] == 5000000000000 and journey['subsequent_spend_atomic'] == 2000000000000
        assert journey['restore_matches'] and journey['cli_open_restored_wallet']
        assert len(journey['payments']) == 2 and all(x['rct_type'] == 7 and x['carrot_outputs'] for x in journey['payments'])
        assert controls['result'] == 'PASS_REFUSALS' and len(controls['cases']) == 10
        assert controls['release_manifest_sha256'] == row['release_manifest_sha256']
        assert check['result'] == 'PASS_NATIVE_ARCHIVE_JOURNEY'
        if args.target == 'windows-i686':
            assert journey['execution_substrate'] == check['execution_substrate'] == 'NATIVE_WINDOWS_WOW64'
            assert check['native_architecture'] == 'x86_64' and check['windows_32bit_os_execution'] == 'UNTESTED'
            assert [p['name'] for p in check['phases']] == ['exception-probe', 'preflight', 'journey', 'controls']
            assert check['native_exception_probe']['result'] == 'PASS_NATIVE_I686_EXCEPTION_PROBE'
            assert check['native_exception_probe']['exit'] == 0 and check['native_exception_probe']['reaped']
            assert check['native_exception_probe']['cleanup_count_asserted_by_bound_fixture'] == 1
            assert check['owned_job']['active_processes'] == 0
            proof['execution_substrate'] = 'NATIVE_WINDOWS_WOW64'
            proof['windows_32bit_os_execution'] = 'UNTESTED'
        for name, value in [('journey.json', journey), ('controls.json', controls), ('check.json', check)]:
            write(public / name, value)
        proof['result'] = 'PASS_NATIVE_ARCHIVE_JOURNEY_AND_TEN_CONTROLS'
    except BaseException as error:
        proof['failure_type'] = type(error).__name__
        raise
    finally:
        # These are the same explicit public receipts, including honest failure
        # and owned-cleanup evidence. Private phase logs are never exported.
        if check_root is not None:
            for source, name in [('journey/result.json', 'journey.json'),
                                 ('controls/controls.json', 'controls.json'),
                                 ('check-receipt.json', 'check.json')]:
                path = check_root / source
                if path.is_file() and not path.is_symlink():
                    write(public / name, json.loads(path.read_text()))
        write(public / 'ci-receipt.json', proof)
        print(proof['result'])


if __name__ == '__main__':
    main()
