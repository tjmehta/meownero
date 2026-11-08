#!/usr/bin/env python3
"""Check hash-bound private CI payloads; export only allowlisted public receipts."""
import argparse
import ctypes
import hashlib
import importlib.util
import json
import datetime
import math
import ntpath
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import shlex
import signal
import stat
import subprocess
import sys
import tarfile
import threading
import time
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent


def sha(path):
    assert path.is_file() and not path.is_symlink() and path.stat().st_nlink == 1
    return hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def public_cli_event(value):
    result = {}
    enums = {'status': {'NOT_REQUESTED', 'NO_MATCHING_EVENT', 'MATCHED_BOUND_CLI_EVENT',
        'AMBIGUOUS_MATCH', 'QUERY_TIMEOUT', 'QUERY_FAILED', 'QUERY_UNAVAILABLE',
        'INVALID_EVENT_DATA', 'OUTPUT_LIMIT', 'IMAGE_BINDING_MISMATCH'},
        'module_class': {'BOUND_CLI_IMAGE', 'WINDOWS_NTDLL', 'WINDOWS_KERNELBASE',
                         'WINDOWS_UCRTBASE', 'UNKNOWN'}, 'cause': {'UNKNOWN'}}
    for key, allowed in enums.items():
        if key in value:
            assert value[key] in allowed
            result[key] = value[key]
    for key in ('pid', 'exit', 'fault_offset', 'query_pid', 'query_exit', 'query_reaped', 'query_seconds'):
        if key in value:
            assert type(value[key]) in (int, float, bool) and math.isfinite(value[key])
            result[key] = value[key]
    if 'image_sha256' in value:
        assert len(value['image_sha256']) == 64 and set(value['image_sha256']) <= set('0123456789abcdef')
        result['image_sha256'] = value['image_sha256']
    return result


def public_diagnostic(value):
    phases = {'VERIFY_BOUND_TESTER', 'CALL_BOUND_JOURNEY', 'OUTPUT_GUARD', 'ACQUIRE_TESTER_LOCK',
        'PREFLIGHT', 'CAPACITY_GUARD', 'PREPARE_PRIVATE_OUTPUT', 'INITIALIZE_OWNED_JOB',
        'RESERVE_LOOPBACK_PORTS', 'START_DAEMON', 'START_WALLETS', 'CREATE_WALLETS', 'FUND_WALLET',
        'PAYMENT_RECEIVE', 'RESTORE_WALLET', 'PAYMENT_SPEND', 'OPEN_NATIVE_CLI', 'FINAL_PREFLIGHT',
        'VERIFY_OWNED_CLEANUP', 'OWNED_CLEANUP'}
    assert value['schema'] == 'meownero-bound-journey-diagnostic/1'
    assert value['result'] in {'FAIL', 'PASS_BOUND_JOURNEY_CALL'} and value['phase'] in phases
    digest = value['tester_sha256']
    assert len(digest) == 64 and set(digest) <= set('0123456789abcdef')
    completed = value['completed_phases']
    assert type(completed) is list and all(p in phases for p in completed)
    result = {key: value[key] for key in ('schema', 'result', 'phase', 'tester_sha256', 'completed_phases')}
    for key in ('available_memory_bytes', 'disk_free_bytes_used_by_guard', 'journey_public_receipt_exists'):
        if key in value:
            assert value[key] is None or type(value[key]) in (int, bool)
            result[key] = value[key]
    if 'native_cli' in value:
        cli = value['native_cli']
        assert cli['stage'] == 'OPEN_RESTORED_WALLET_BALANCE'
        assert cli['exit_class'] in {'SUCCESS', 'ACCESS_VIOLATION_STATUS', 'OTHER_NONZERO_STATUS', 'RUNNING', 'WAIT_TIMEOUT'}
        result['native_cli'] = {k: cli[k] for k in ('stage', 'exit_class')}
        for key in ('pid', 'exit', 'started_epoch_seconds', 'observed_exit_epoch_seconds'):
            assert cli[key] is None or type(cli[key]) in (int, float) and math.isfinite(cli[key])
            result['native_cli'][key] = cli[key]
    if 'first_failure' in value:
        first = value['first_failure']
        assert first['phase'] in phases
        assert first['reason'] in {'CAPACITY_RESERVE_NOT_MET', 'OUTPUT_COLLISION_OR_PARENT', 'TESTER_LOCK_BUSY',
            'TARGET_MISMATCH', 'OS_MISMATCH', 'SOURCE_PIN_MISMATCH', 'PACKAGE_FILE_SET', 'SYMLINK_PATH_REFUSED',
            'UNSAFE_LOCK', 'JOURNEY_INTERRUPTED', 'WINDOWS_DEADLINE', 'NATIVE_CLI_RESTORED_WALLET_FAILED', 'NATIVE_CLI_WAIT_TIMEOUT',
            'PACKAGE_HASH_MISMATCH', 'VERSION_CHILD_FAILED', 'JOURNEY_CHILD_EXITED', 'NATIVE_STARTUP_TIMEOUT',
            'RPC_FAILURE', 'FUNDING_RPC_TIMEOUT', 'EXCEPTION_UNCLASSIFIED'}
        assert first['exception_type'] in {'RuntimeError', 'TimeoutError', 'OSError', 'PermissionError',
            'FileExistsError', 'FileNotFoundError', 'AssertionError', 'JourneyInterrupted', 'KeyboardInterrupt',
            'ValueError', 'KeyError', 'TypeError', 'URLError', 'HTTPError', 'TimeoutExpired', 'OTHER_EXCEPTION'}
        result['first_failure'] = {k: first[k] for k in ('phase', 'reason', 'exception_type')}
        for key in ('errno', 'winerror'):
            if key in first:
                assert type(first[key]) is int
                result['first_failure'][key] = first[key]
        if 'operation' in first:
            assert first['phase'] == 'FUND_WALLET' and first['operation'] in {'generateblocks', 'refresh', 'get_balance'}
            result['first_failure']['operation'] = first['operation']
    if 'funding_operations' in value:
        operations = value['funding_operations']
        assert type(operations) is list and len(operations) <= 3
        result['funding_operations'] = []
        for index, operation in enumerate(operations):
            assert operation['operation'] == ('generateblocks', 'refresh', 'get_balance')[index]
            assert operation['outcome'] in {'RUNNING', 'PASS', 'TIMEOUT', 'ERROR'}
            row = {k: operation[k] for k in ('operation', 'outcome')}
            for key in ('elapsed_seconds', 'socket_timeout_seconds', 'journey_deadline_seconds',
                        'journey_elapsed_at_start_seconds', 'journey_remaining_at_start_seconds'):
                number = operation[key]
                assert type(number) in (int, float) and math.isfinite(number) and number >= 0
                row[key] = number
            assert row['socket_timeout_seconds'] == 90 and 1 <= row['journey_deadline_seconds'] <= 1200
            assert row['journey_remaining_at_start_seconds'] <= row['journey_deadline_seconds']
            result['funding_operations'].append(row)
    return result


def control_coverage(controls):
    """Validate all ten outcomes; one unavailable fixture cannot grant PASS."""
    names = ['wrong-pin', 'wrong-target', 'changed-binary', 'unlisted-private-file',
             'symlink-directory', 'hardlink', 'collision-preservation', 'busy-lock',
             'cancelled-owned-cleanup', 'deadline-owned-cleanup']
    assert [row['case'] for row in controls['cases']] == names
    incomplete = False
    for row in controls['cases']:
        if row.get('status') == 'NOT_EXECUTED':
            assert row == {'case': 'symlink-directory', 'status': 'NOT_EXECUTED',
                           'reason_enum': 'SYMLINK_PRIVILEGE_NOT_HELD', 'winerror': 1314}
            incomplete = True
        elif row['case'].endswith('-owned-cleanup'):
            assert row['removed'] is True and type(row['process_count']) is int and row['process_count'] > 0
        else:
            assert row['refused'] is True
            if row['case'] == 'collision-preservation':
                assert row['sentinel_preserved'] is True
    assert controls['result'] == ('INCOMPLETE_REFUSALS' if incomplete else 'PASS_REFUSALS')
    return incomplete


def matching_cli_events(data, cli, image, image_sha256, system_directory, query_end):
    """Match private Application Error XML to owned PID, creation time and image."""
    assert len(data) <= 128 * 1024
    if isinstance(data, bytes):
        data = data.decode('utf-8')
    # No DTD/entities, messages, XML, module names or paths enter the receipt.
    assert '<!DOCTYPE' not in data.upper() and '<!ENTITY' not in data.upper()
    ns = '{http://schemas.microsoft.com/win/2004/08/events/event}'
    events, matches = ET.fromstring(data), []
    assert len(events) <= 32
    same_path = lambda a, b: ntpath.normcase(ntpath.normpath(a)) == ntpath.normcase(ntpath.normpath(str(b)))
    for event in events:
        system = event.find(ns + 'System')
        provider = system.find(ns + 'Provider') if system is not None else None
        if provider is None or provider.get('Name') != 'Application Error' or system.findtext(ns + 'EventID') != '1000':
            continue
        fields = {item.get('Name'): item.text or '' for item in event.findall(ns + 'EventData/' + ns + 'Data')}
        try:
            pid = int(fields['ProcessId'], 16)
            creation = int(fields['ProcessCreationTime'], 16) / 10**7 - 11644473600
            stamp = datetime.datetime.fromisoformat(system.find(ns + 'TimeCreated').get('SystemTime').replace('Z', '+00:00')).timestamp()
            status = int(fields['ExceptionCode'], 16)
            offset = int(fields['FaultingOffset'], 16)
        except (KeyError, ValueError, AttributeError):
            continue
        if not (pid == cli['pid'] and status == cli['exit'] and 0 <= offset < 2**64 and
                cli['started_epoch_seconds'] <= creation <= cli['observed_exit_epoch_seconds'] and
                creation <= stamp <= query_end and same_path(fields.get('AppPath', ''), image)):
            continue
        module = fields.get('ModulePath', '')
        kind = 'UNKNOWN'
        if same_path(module, image):
            kind = 'BOUND_CLI_IMAGE'
        else:
            for name, label in [('ntdll.dll', 'WINDOWS_NTDLL'), ('kernelbase.dll', 'WINDOWS_KERNELBASE'), ('ucrtbase.dll', 'WINDOWS_UCRTBASE')]:
                if same_path(module, ntpath.join(str(system_directory), name)):
                    kind = label
        matches.append({'status': 'MATCHED_BOUND_CLI_EVENT', 'pid': pid, 'exit': status,
                        'fault_offset': offset, 'module_class': kind,
                        'image_sha256': image_sha256, 'cause': 'UNKNOWN'})
    return matches[0] if len(matches) == 1 else {'status': 'AMBIGUOUS_MATCH' if matches else 'NO_MATCHING_EVENT', 'cause': 'UNKNOWN'}


def native_cli_event(package, out, row, backend, job):
    """Read at most 32 local events in a suspended/registered owned child."""
    evidence = {'status': 'QUERY_UNAVAILABLE', 'cause': 'UNKNOWN', 'query_seconds': 5}
    child = None
    try:
        path = out / 'journey-diagnostic.json'
        if not path.is_file() or path.is_symlink():
            return {'status': 'NOT_REQUESTED', 'cause': 'UNKNOWN'}
        cli = json.loads(path.read_text()).get('native_cli', {})
        if not cli or cli.get('exit') in (None, 0):
            return {'status': 'NOT_REQUESTED', 'cause': 'UNKNOWN'}
        assert type(cli['pid']) is int and cli['pid'] > 0 and type(cli['exit']) is int
        start, end = cli['started_epoch_seconds'], cli['observed_exit_epoch_seconds']
        assert type(start) in (int, float) and type(end) in (int, float) and math.isfinite(start) and math.isfinite(end)
        assert start <= end <= time.time() and end - start <= 1500
        image = package / 'bin/monero-wallet-cli.exe'
        manifest = json.loads((package / 'release.json').read_text())
        digest = manifest['files']['bin/monero-wallet-cli.exe']
        assert digest == row['program_sha256']['monero-wallet-cli']
        assert sha(image) == digest
        buffer = backend.C.create_unicode_buffer(32768)
        length = backend.api(backend.k, 'GetSystemDirectoryW', backend.W.UINT, backend.W.LPWSTR, backend.W.UINT)(buffer, len(buffer))
        assert 0 < length < len(buffer)
        system_directory = Path(buffer.value)
        query_end = time.time()
        utc = lambda value: datetime.datetime.fromtimestamp(value, datetime.timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
        query = "*[System[Provider[@Name='Application Error'] and EventID=1000 and TimeCreated[@SystemTime>='" + utc(start) + "' and @SystemTime<='" + utc(query_end) + "']]]"
        private = out / 'native-cli-events.xml'
        with private.open('xb') as stream:
            child = job.spawn(system_directory / 'wevtutil.exe',
                ['qe', 'Application', '/q:' + query, '/rd:true', '/c:32', '/f:xml', '/e:Events', '/uni:true'],
                stream, os.environ.copy(), out)
            evidence['query_pid'] = child.pid
            try:
                evidence['query_exit'] = child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                evidence['status'] = 'QUERY_TIMEOUT'
                return evidence
        if evidence['query_exit'] != 0:
            evidence['status'] = 'QUERY_FAILED'
            return evidence
        if private.stat().st_size > 128 * 1024:
            evidence['status'] = 'OUTPUT_LIMIT'
            return evidence
        if sha(image) != digest:
            evidence['status'] = 'IMAGE_BINDING_MISMATCH'
            return evidence
        data = private.read_bytes()
        # Unicode mode emits UTF-16. Normalize only in private memory.
        text = data.decode('utf-16') if data.startswith((b'\xff\xfe', b'\xfe\xff')) else data.decode('utf-16-le')
        evidence.update(matching_cli_events(text, cli, image, digest, system_directory, query_end))
    except (OSError, ValueError, KeyError, AssertionError, ET.ParseError):
        evidence['status'] = 'INVALID_EVENT_DATA'
    finally:
        if child is not None:
            if child.poll() is None:
                child.terminate()
            child.wait(timeout=5)
            evidence['query_reaped'] = child.poll() is not None
    return evidence


def public_check(value):
    """Project fixed check evidence; execution argv and paths remain private."""
    enums = {
        'schema': {'meownero-native-windows-ci-check/1', 'meownero-portable-native-mac-check/1'},
        'result': {'FAIL', 'PASS_NATIVE_ARCHIVE_JOURNEY', 'PASS_TRANSLATED_ARCHIVE_JOURNEY', 'INCOMPLETE_NATIVE_ARCHIVE_CONTROLS'},
        'native_architecture': {'i686', 'x86_64', 'aarch64'},
        'package_architecture': {'i686', 'x86_64', 'aarch64'},
        'execution_substrate': {'NATIVE', 'NATIVE_WINDOWS_WOW64', 'ROSETTA_TRANSLATED_MACOS_X86_64'},
        'windows_32bit_os_execution': {'UNTESTED'},
        'console_mode': {'OWNED_NEW_CONSOLE', 'EXISTING_ATTACHED_CONSOLE'},
    }
    def project(row, keys):
        result = {}
        for key in keys:
            if key in row:
                assert type(row[key]) in (int, float, bool) or row[key] is None
                result[key] = row[key]
        return result
    result = project(value, ('wall_seconds', 'resident_limit_bytes', 'peak_resident_bytes',
                            'initial_console_process_count', 'owned_job_created', 'owned_console_freed'))
    for key, allowed in enums.items():
        if key in value:
            assert value[key] in allowed
            result[key] = value[key]
    for key in ('archive_sha256',):
        if key in value:
            assert len(value[key]) == 64 and set(value[key]) <= set('0123456789abcdef')
            result[key] = value[key]
    result['phases'] = []
    for row in value.get('phases', []):
        assert row['name'] in ('exception-probe', 'preflight', 'journey', 'controls')
        phase = project(row, ('pid', 'exit', 'reaped', 'wall_seconds'))
        phase['name'] = row['name']
        result['phases'].append(phase)
    if 'cleanup' in value:
        result['cleanup'] = [project(row, ('pid', 'removed')) for row in value['cleanup']]
    if 'owned_job' in value:
        job = value['owned_job']
        result['owned_job'] = project(job, ('active_processes', 'total_processes', 'peak_committed_bytes', 'memory_limit_bytes'))
        result['owned_job']['children'] = [project(row, ('pid', 'exit')) for row in job.get('children', [])]
    if 'native_exception_probe' in value:
        probe = value['native_exception_probe']
        projected = project(probe, ('exit', 'reaped', 'deadline_seconds', 'exact_success_line', 'cleanup_count_asserted_by_bound_fixture'))
        assert probe['result'] == 'PASS_NATIVE_I686_EXCEPTION_PROBE' and probe['newline'] in ('LF', 'CRLF')
        projected.update(result=probe['result'], newline=probe['newline'])
        for key in ('sha256', 'source_sha256'):
            assert len(probe[key]) == 64 and set(probe[key]) <= set('0123456789abcdef')
            projected[key] = probe[key]
        result['native_exception_probe'] = projected
    if 'native_cli_event' in value:
        result['native_cli_event'] = public_cli_event(value['native_cli_event'])
    return result


class _DarwinTimeval(ctypes.Structure):
    _fields_ = [('tv_sec', ctypes.c_int64), ('tv_usec', ctypes.c_int32)]


class _DarwinExternProc(ctypes.Structure):
    # <sys/proc.h> struct extern_proc, LP64 (x86_64 and arm64 share this layout).
    _fields_ = [('p_starttime', _DarwinTimeval), ('p_vmspace', ctypes.c_void_p), ('p_sigacts', ctypes.c_void_p),
                ('p_flag', ctypes.c_int), ('p_stat', ctypes.c_char), ('p_pid', ctypes.c_int32),
                ('p_oppid', ctypes.c_int32), ('p_dupfd', ctypes.c_int), ('user_stack', ctypes.c_void_p),
                ('exit_thread', ctypes.c_void_p), ('p_debugger', ctypes.c_int), ('sigwait', ctypes.c_int),
                ('p_estcpu', ctypes.c_uint), ('p_cpticks', ctypes.c_int), ('p_pctcpu', ctypes.c_uint32),
                ('p_wchan', ctypes.c_void_p), ('p_wmesg', ctypes.c_void_p), ('p_swtime', ctypes.c_uint),
                ('p_slptime', ctypes.c_uint), ('p_realtimer', _DarwinTimeval * 2), ('p_rtime', _DarwinTimeval),
                ('p_uticks', ctypes.c_uint64), ('p_sticks', ctypes.c_uint64), ('p_iticks', ctypes.c_uint64),
                ('p_traceflag', ctypes.c_int), ('p_tracep', ctypes.c_void_p), ('p_siglist', ctypes.c_int),
                ('p_textvp', ctypes.c_void_p), ('p_holdcnt', ctypes.c_int), ('p_sigmask', ctypes.c_uint32),
                ('p_sigignore', ctypes.c_uint32), ('p_sigcatch', ctypes.c_uint32), ('p_priority', ctypes.c_ubyte),
                ('p_usrpri', ctypes.c_ubyte), ('p_nice', ctypes.c_char), ('p_comm', ctypes.c_char * 17),
                ('p_pgrp', ctypes.c_void_p), ('p_addr', ctypes.c_void_p), ('p_xstat', ctypes.c_ushort),
                ('p_acflag', ctypes.c_ushort), ('p_ru', ctypes.c_void_p)]


class _DarwinPcred(ctypes.Structure):
    _fields_ = [('pc_lock', ctypes.c_char * 72), ('pc_ucred', ctypes.c_void_p), ('p_ruid', ctypes.c_uint32),
                ('p_svuid', ctypes.c_uint32), ('p_rgid', ctypes.c_uint32), ('p_svgid', ctypes.c_uint32),
                ('p_refcnt', ctypes.c_int)]


class _DarwinUcred(ctypes.Structure):
    _fields_ = [('cr_ref', ctypes.c_int32), ('cr_uid', ctypes.c_uint32), ('cr_ngroups', ctypes.c_short),
                ('cr_groups', ctypes.c_uint32 * 16)]


class _DarwinVmspace(ctypes.Structure):
    _fields_ = [('vm_refcnt', ctypes.c_int), ('vm_shm', ctypes.c_void_p), ('vm_sizes', ctypes.c_int32 * 5),
                ('vm_addrs', ctypes.c_void_p * 3)]


class _DarwinEproc(ctypes.Structure):
    # <sys/sysctl.h> struct eproc, with nested _pcred/_ucred/vmspace as declared.
    _fields_ = [('e_paddr', ctypes.c_void_p), ('e_sess', ctypes.c_void_p), ('e_pcred', _DarwinPcred),
                ('e_ucred', _DarwinUcred), ('e_vm', _DarwinVmspace), ('e_ppid', ctypes.c_int32),
                ('e_pgid', ctypes.c_int32), ('e_jobc', ctypes.c_short), ('e_tdev', ctypes.c_int32),
                ('e_tpgid', ctypes.c_int32), ('e_tsess', ctypes.c_void_p), ('e_wmesg', ctypes.c_char * 8),
                ('e_xsize', ctypes.c_int32), ('e_xrssize', ctypes.c_short), ('e_xccount', ctypes.c_short),
                ('e_xswrss', ctypes.c_short), ('e_flag', ctypes.c_int32), ('e_login', ctypes.c_char * 12),
                ('e_spare', ctypes.c_int32 * 4)]


class _DarwinKinfoProc(ctypes.Structure):
    _fields_ = [('kp_proc', _DarwinExternProc), ('kp_eproc', _DarwinEproc)]


DARWIN_PROCESS_STATES = {1: 'I', 2: 'R', 3: 'S', 4: 'T', 5: 'Z'}


def parse_darwin_process_table(raw):
    """Decode sysctl kern.proc.all records into the snapshot row schema."""
    width = ctypes.sizeof(_DarwinKinfoProc)
    assert width == 648 and len(raw) % width == 0, 'KERNEL_PROCESS_TABLE_LAYOUT_MISMATCH'
    table = []
    for offset in range(0, len(raw), width):
        record = _DarwinKinfoProc.from_buffer_copy(raw, offset)
        proc, eproc = record.kp_proc, record.kp_eproc
        table.append((proc.p_pid, eproc.e_ppid, eproc.e_pcred.p_ruid, eproc.e_ucred.cr_uid,
                      (proc.p_starttime.tv_sec, proc.p_starttime.tv_usec),
                      DARWIN_PROCESS_STATES.get(proc.p_stat[0], '?'),
                      proc.p_comm.decode('utf-8', 'replace')))
    return table


def darwin_process_table(pid=None):
    """Read the kernel process table that ps itself starts from (sysctl kern.proc.all).

    Darwin ps then opens every listed task and walks its VM map regions
    (adv_cmds ps/tasks.c get_task_info: task_read_for_pid, mach_vm_region),
    which stalls for seconds behind a starting monerod's address-space changes.
    This table copy reads only process, credential and session fields
    (xnu bsd/kern/kern_sysctl.c fill_user64_eproc/externproc).
    """
    library = ctypes.CDLL(None, use_errno=True)
    call = library.sysctl
    call.argtypes = [ctypes.POINTER(ctypes.c_int), ctypes.c_uint, ctypes.c_void_p,
                     ctypes.POINTER(ctypes.c_size_t), ctypes.c_void_p, ctypes.c_size_t]
    call.restype = ctypes.c_int
    # CTL_KERN, KERN_PROC, then KERN_PROC_ALL as ps uses, or KERN_PROC_PID for one re-read.
    mib = (ctypes.c_int * 4)(1, 14, 0, 0) if pid is None else (ctypes.c_int * 4)(1, 14, 1, pid)
    for _ in range(8):
        size = ctypes.c_size_t(0)
        if call(mib, 4, None, ctypes.byref(size), None, 0) != 0:
            raise OSError(ctypes.get_errno(), 'kern.proc.all size query failed')
        size.value += size.value // 4 + ctypes.sizeof(_DarwinKinfoProc) * 64
        buffer = ctypes.create_string_buffer(size.value)
        if call(mib, 4, buffer, ctypes.byref(size), None, 0) == 0:
            table = parse_darwin_process_table(buffer.raw[:size.value])
            if pid is not None:
                assert all(row[0] == pid for row in table), 'KERNEL_PROCESS_TABLE_LAYOUT_MISMATCH'
                return table
            mine = [row for row in table if row[0] == os.getpid()]
            # Fail closed unless the decoded layout reproduces this process exactly.
            assert len(mine) == 1 and mine[0][1:4] == (os.getppid(), os.getuid(), os.geteuid()), \
                'KERNEL_PROCESS_TABLE_LAYOUT_MISMATCH'
            return table
        if ctypes.get_errno() != 12:  # ENOMEM: the table grew; retry with a fresh size.
            raise OSError(ctypes.get_errno(), 'kern.proc.all read failed')
    raise OSError(12, 'kern.proc.all kept growing')


def kernel_table_output(*, timeout, receipt, context, pid=None):
    """Bound the in-process table read by the same deadline as a ps observer."""
    began, box = time.monotonic(), {}
    cost = {'operation': 'OWNED_PROCESS_TABLE', 'source': 'SYSCTL_KERN_PROC_' + ('ALL' if pid is None else 'PID'),
            'context': context,
            'timeout_seconds': timeout, 'result': 'FAIL', 'began_monotonic': round(began, 6)}

    def read():
        try:
            box['table'] = darwin_process_table(pid)
        except BaseException as error:
            box['error'] = error

    try:
        worker = threading.Thread(target=read, daemon=True)
        worker.start()
        worker.join(timeout)
        if worker.is_alive():
            # A read-only table copy has no process to reap; the deadline still fails.
            cost['result'] = 'TIMEOUT'
            raise subprocess.TimeoutExpired('sysctl kern.proc.all', timeout)
        if 'error' in box:
            raise box['error']
        cost.update(result='PASS', process_rows=len(box['table']))
        return box['table']
    finally:
        cost['elapsed_seconds'] = round(time.monotonic() - began, 6)
        summary = receipt.setdefault('snapshot_cost', {'calls': 0, 'max_elapsed_seconds': 0, 'recent': []})
        summary['calls'] += 1
        summary['max_elapsed_seconds'] = max(summary['max_elapsed_seconds'], cost['elapsed_seconds'])
        summary['recent'] = (summary['recent'] + [cost])[-8:]


def snapshot_output(argv, *, timeout, receipt, context):
    """Time only the owned observer; discard incomplete output as authority."""
    began, observer = time.monotonic(), None
    # The host monotonic clock is shared with the controls harness receipts.
    cost = {'operation': 'OWNED_PROCESS_SNAPSHOT', 'context': context,
            'timeout_seconds': timeout, 'result': 'FAIL', 'began_monotonic': round(began, 6)}
    try:
        observer = subprocess.Popen(argv, stdout=subprocess.PIPE, text=True)
        cost.update(observer_pid=observer.pid, spawn_seconds=round(time.monotonic() - began, 6))
        waiting = time.monotonic()
        try:
            output, _ = observer.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            cost['result'] = 'TIMEOUT'
            raise
        finally:
            cost['communicate_seconds'] = round(time.monotonic() - waiting, 6)
        if observer.returncode:
            raise subprocess.CalledProcessError(observer.returncode, argv)
        cost.update(result='PASS', output_bytes=len(output.encode()), process_rows=len(output.splitlines()))
        return output
    finally:
        first_error = sys.exc_info()[1]
        reaping = time.monotonic()
        try:
            if observer is not None:
                if observer.poll() is None:
                    observer.kill()  # Only our exact Popen child, never an observed PID.
                try:
                    observer.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    observer.stdout.close()
                    observer.wait(timeout=5)
                cost['observer_reaped'] = observer.poll() is not None
                cost['numeric_pid_absent'] = False
                try:
                    os.kill(observer.pid, 0)
                except ProcessLookupError:
                    cost['numeric_pid_absent'] = True
                except PermissionError:
                    pass
                assert cost['observer_reaped'] and cost['numeric_pid_absent'], 'owned observer disappearance unproven'
        except BaseException:
            cost['result'] = 'FAIL'
            receipt.setdefault('cleanup_failure_type', 'OBSERVER_DISAPPEARANCE_UNPROVEN')
            if first_error is None:
                raise
        finally:
            cost.update(reap_seconds=round(time.monotonic() - reaping, 6),
                        elapsed_seconds=round(time.monotonic() - began, 6))
            summary = receipt.setdefault('snapshot_cost', {'calls': 0, 'max_elapsed_seconds': 0, 'recent': []})
            summary['calls'] += 1
            summary['max_elapsed_seconds'] = max(summary['max_elapsed_seconds'], cost['elapsed_seconds'])
            summary['recent'] = (summary['recent'] + [cost])[-8:]


def mac_check(argv, out, public, *, timeout=1500, cleanup_seconds=240,
              supervision_schema='meownero-native-mac-ci-supervision/1',
              failure_label='native Intel archive check'):
    """Allow wrapper cleanup before escalating only recorded, verified children."""
    receipt = {'schema': supervision_schema, 'result': 'FAIL',
               'wrapper_reaped': False, 'cleanup': [], 'signals': [],
               'observer_ruid': os.getuid(), 'observer_euid': os.geteuid(), 'helper_observations': [],
               'unverified_observations': []}
    known, pending, helper_bindings, states, unverified_zombies = {}, [], {}, {}, set()
    rejected_live = {}
    process = None
    snapshot_context = 'INITIAL_OBSERVATION'
    began = time.monotonic()

    def reject(reason, observation=None):
        receipt.setdefault('failure_reason', reason)
        if observation is not None:
            receipt.setdefault('failure_observation', observation)
            if observation['pid'] in rejected_live and observation not in receipt['unverified_observations']:
                receipt['unverified_observations'].append(observation)
        raise AssertionError(reason)

    def helper_file_binding():
        path = Path('/bin/ps')
        info = path.lstat()
        if not (stat.S_ISREG(info.st_mode) and info.st_uid == 0 and
                info.st_mode & stat.S_ISUID and not info.st_mode & 0o022):
            reject('HELPER_SYSTEM_FILE_BINDING_MISMATCH')
        return (info.st_dev, info.st_ino, info.st_mode, sha(path))

    def helper_binding(pid):
        # Darwin ps has its existing setuid bit; never change runner privileges.
        library = ctypes.CDLL('/usr/lib/libproc.dylib', use_errno=True)
        pidpath = library.proc_pidpath
        pidpath.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
        pidpath.restype = ctypes.c_int
        buffer = ctypes.create_string_buffer(4096)
        if pidpath(pid, buffer, len(buffer)) <= 0:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return None  # ps snapshot raced an already exited helper.
            reject('HELPER_KERNEL_EXECUTABLE_QUERY_FAILED')
        if buffer.value != b'/bin/ps':
            reject('HELPER_KERNEL_EXECUTABLE_MISMATCH')
        return helper_file_binding()

    def remember_identity(pid, row):
        observation = {'pid': pid, 'ppid': row[0], 'ruid': row[1], 'euid': row[2],
                       'role': 'OWNED_WRAPPER' if pid == process.pid else 'OWNED_DESCENDANT'}
        # Account for every first observation before validation can reject it.
        # Quarantined identities are never authority for a cleanup signal.
        first_candidate = pid not in known and pid not in rejected_live
        if first_candidate:
            rejected_live[pid] = row
        observation['state_class'] = 'ZOMBIE' if states.get(pid, '').startswith('Z') else 'LIVE'
        if not first_candidate and pid in rejected_live:
            # A previous unverified observation is never ownership authority.
            # Preserve its initial ancestry/UID/start even across PID reuse or
            # privilege changes; only independently proven absence resolves it.
            observation['role'] = 'PERMANENTLY_QUARANTINED_OBSERVATION'
            observation['identity_state'] = ('INITIAL_IDENTITY_UNCHANGED' if row[:4] == rejected_live[pid][:4]
                                             else 'INITIAL_ANCESTRY_UID_OR_START_CHANGED')
            if observation not in receipt['unverified_observations']:
                receipt['unverified_observations'].append(observation)
            return False
        # These immutable fields must pass before every role/euid/state branch.
        # An observed helper cannot escape its binding by dropping privileges.
        if pid in known and row[1:4] != known[pid][:3]:
            reject('REMEMBERED_IMMUTABLE_PROCESS_IDENTITY_CHANGED', observation)
        if pid in helper_bindings and helper_file_binding() != helper_bindings[pid]:
            reject('REMEMBERED_HELPER_SYSTEM_FILE_CHANGED', observation)
        if row[1] != os.getuid():
            reject('REAL_UID_MISMATCH', observation)
        absent = False
        if pid not in known and (states.get(pid, '').startswith('Z') or row[4] == '(ps)'):
            absent = pid_absent(pid, {})
            helper_exit_race = (platform.system() == 'Darwin' and row[4] == '(ps)' and process is not None
                                and row[0] == process.pid and row[2] != os.geteuid())
            if not absent and (helper_exit_race or platform.system() == 'Linux' and states.get(pid, '').startswith('Z')):
                # Timed Popen.wait can sleep before reaping an exited child, and a
                # Darwin helper whose single-process argv query found it gone may
                # still await that reap.
                # https://docs.python.org/3.13/library/subprocess.html#subprocess.Popen.wait
                # Wait read-only for actual absence; infer no executable or
                # ownership, and never extend the phase's existing deadline.
                reaping_began = time.monotonic()
                reaping_end = min(reaping_began + 0.25, began + timeout)
                while not absent and time.monotonic() < reaping_end:
                    time.sleep(min(0.005, max(0, reaping_end - time.monotonic())))
                    absent = pid_absent(pid, {})
                observation['reaping_grace_seconds'] = round(time.monotonic() - reaping_began, 6)
        if absent:
            # A snapshot may precede reaping while inspection follows it. Prove
            # numeric PID absence independently; infer no executable or role.
            observation['role'] = 'ALREADY_ABSENT_UNVERIFIED_SNAPSHOT'
            observation['argv_role'] = 'PS_EXIT_DISPLAY' if row[4] == '(ps)' else 'UNVERIFIED_ZOMBIE'
            observation['absence_proof'] = 'ACTUAL_PID_ABSENCE'
            receipt['unverified_observations'].append(observation)
            return False
        if states.get(pid, '').startswith('Z'):
            # A verified helper may become a zombie before its parent reaps it.
            # Keep its original executable identity and wait for actual absence.
            if pid not in known:
                # Never infer an executable or privileged role from a zombie.
                # Account for its PID until actual absence, but never signal it.
                known[pid] = row[1:]
                unverified_zombies.add(pid)
                observation['role'] = 'UNVERIFIED_OWNED_ZOMBIE'
                receipt['unverified_observations'].append(observation)
                reject('UNVERIFIED_FIRST_ZOMBIE', observation)
            return False
        if pid in unverified_zombies:
            reject('UNVERIFIED_ZOMBIE_BECAME_LIVE', observation)
        if row[2] != os.geteuid():
            try:
                words = shlex.split(row[4])
            except ValueError:
                words = []
            arguments = words[1:]
            ps_arguments = arguments == ['-axo', 'pid=,ppid=,rss='] or (
                len(arguments) in (2, 4) and arguments[0] == '-p' and arguments[1].isdigit() and
                (len(arguments) == 2 or arguments[2:] == ['-o', 'command=']))
            # Darwin can discard argv before exposing the zombie state. Accept
            # its exit display only for this already kernel-bound helper, with
            # unchanged real/effective UID and start identity; bind it again below.
            exit_display = (pid in helper_bindings and row[4] == '(ps)' and
                            row[1:4] == known[pid][:3])
            observation['argv_role'] = ('EXACT_PS_OBSERVER' if words and words[0] in ('ps', '/bin/ps') and ps_arguments
                                        else 'PS_EXIT_DISPLAY' if row[4] == '(ps)' else 'NOT_ALLOWLISTED')
            observation['direct_wrapper_parent'] = row[0] == process.pid
            observation['previously_bound_helper'] = pid in helper_bindings
            if not (platform.system() == 'Darwin' and row[2] == 0 and row[0] == process.pid and
                    ((words and words[0] in ('ps', '/bin/ps') and ps_arguments) or exit_display)):
                # Query only the already descendant-bound UID501/root candidate,
                # for static diagnostics; this never authorizes it or a signal.
                if platform.system() == 'Darwin' and row[2] == 0 and row[0] == process.pid:
                    original_reason = receipt.get('failure_reason')
                    try:
                        diagnostic_binding = helper_binding(pid)
                        observation['kernel_file_role'] = ('ROOT_SUID_SYSTEM_PS' if diagnostic_binding else 'ALREADY_ABSENT')
                        if diagnostic_binding is None and row[4] == '(ps)':
                            # The live ps text snapshot can race argv destruction
                            # and reaping. This proves absence, not helper authority.
                            # Preserve accounting; never register or signal it.
                            observation['role'] = 'ALREADY_ABSENT_UNVERIFIED_PS_EXIT_DISPLAY'
                            receipt['unverified_observations'].append(observation)
                            return False
                    except AssertionError:
                        observation['kernel_file_role'] = 'NOT_VERIFIED_SYSTEM_PS'
                    if original_reason is None:
                        receipt.pop('failure_reason', None)
                    else:
                        receipt['failure_reason'] = original_reason
                reject('EFFECTIVE_UID_NOT_ALLOWLISTED', observation)
            temporary_observation = 'failure_reason' not in receipt
            if temporary_observation:
                receipt['failure_observation'] = observation
            binding = helper_binding(pid)
            if binding is None:
                if temporary_observation:
                    receipt.pop('failure_observation', None)
                return False
            if pid in helper_bindings and (binding != helper_bindings[pid] or row[1:4] != known[pid][:3]):
                reject('REMEMBERED_HELPER_IDENTITY_CHANGED', observation)
            helper_bindings[pid] = binding
            observation['role'] = 'DARWIN_WRAPPER_PS_OBSERVER'
            observation['executable_sha256'] = binding[3]
            if len(receipt['helper_observations']) < 64 and observation not in receipt['helper_observations']:
                receipt['helper_observations'].append(observation)
            if temporary_observation:
                receipt.pop('failure_observation', None)
        known[pid] = row[1:]
        rejected_live.pop(pid, None)
        return True

    def snapshot():
        rows = {}
        states.clear()
        snapshot_began = time.monotonic()
        darwin = platform.system() == 'Darwin'
        operation = 'OWNED_PROCESS_TABLE' if darwin else 'OWNED_PROCESS_SNAPSHOT'
        try:
            if darwin:
                # Darwin ps -ax inspects every task's VM map and stalls behind a
                # starting monerod; read the kernel table instead (same deadline).
                for pid, ppid, ruid, euid, start, state, comm in kernel_table_output(
                        timeout=5, receipt=receipt, context=snapshot_context):
                    # The table carries no argv. '(comm)' is ps's own display
                    # when argv is unavailable, so existing exit-display checks hold.
                    rows[pid] = (ppid, ruid, euid, start, '(' + comm + ')')
                    states[pid] = state
                wrapper = process.pid if process is not None else None
                for pid, row in list(rows.items()):
                    # Only a direct wrapper child with another effective UID is
                    # judged by argv; ps -p inspects that single process only.
                    if row[0] == wrapper and row[2] != os.geteuid() and not states[pid].startswith('Z'):
                        operation = 'OWNED_HELPER_ARGV'
                        try:
                            argv = snapshot_output(['/bin/ps', '-p', str(pid), '-o', 'command='], timeout=5,
                                                   receipt=receipt, context=snapshot_context).strip()
                        except subprocess.CalledProcessError:
                            argv = ''  # Already exited: keep the exit display; absence is proven later.
                        if argv:
                            rows[pid] = row[:4] + (argv,)
                        else:
                            # Pair the exit display with a fresh kernel state for this PID.
                            # A vanished known helper is gone; a vanished first sighting
                            # keeps its row so its actual absence is proven and recorded.
                            fresh = kernel_table_output(timeout=5, receipt=receipt, context=snapshot_context, pid=pid)
                            if not fresh:
                                if pid in known:
                                    rows.pop(pid)
                                    states.pop(pid, None)
                            elif fresh[0][1:5] != row[:4]:
                                reject('HELPER_ROW_CHANGED_DURING_ARGV_QUERY')
                            else:
                                states[pid] = fresh[0][5]
                        operation = 'OWNED_PROCESS_TABLE'
            else:
                output = snapshot_output(['/bin/ps', '-axo', 'pid=,ppid=,ruid=,uid=,lstart=,state=,command='],
                                         timeout=5, receipt=receipt, context=snapshot_context)
                for line in output.splitlines():
                    fields = line.split(None, 10)
                    if len(fields) == 11:
                        rows[int(fields[0])] = (int(fields[1]), int(fields[2]), int(fields[3]), tuple(fields[4:9]), fields[10])
                        states[int(fields[0])] = fields[9]
        except subprocess.TimeoutExpired:
            # check_output kills/reaps only its own helper before raising.
            # Preserve the first failed call without exporting argv or stderr.
            elapsed = round(time.monotonic() - snapshot_began, 3)
            event = {'operation': operation, 'context': snapshot_context,
                     'timeout_seconds': 5, 'elapsed_seconds': elapsed}
            events = receipt.setdefault('snapshot_timeouts', [])
            if len(events) < 64:
                events.append(event)
            if 'failure_type' not in receipt and 'failure_operation' not in receipt:
                receipt['failure_operation'] = event['operation']
                receipt['failure_context'] = snapshot_context
                receipt['failure_timeout_seconds'] = 5
                receipt['failure_elapsed_seconds'] = elapsed
                receipt.setdefault('failure_reason', 'PROCESS_SNAPSHOT_DEADLINE')
            raise
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
                remember_identity(pid, row)
        return rows

    def pid_absent(pid, rows):
        if pid in rows:
            return False
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            return False
        return False

    def remaining():
        rows = remember()
        alive = []
        for pid, identity in known.items():
            if pid in rejected_live or pid in unverified_zombies:
                if not pid_absent(pid, rows):
                    alive.append(pid)
                continue
            if pid in rows:
                if states.get(pid, '').startswith('Z'):
                    if rows[pid][1:4] != identity[:3]:
                        reject('REMEMBERED_ZOMBIE_IDENTITY_CHANGED')
                    alive.append(pid)
                    continue
                if pid in unverified_zombies:
                    reject('UNVERIFIED_ZOMBIE_BECAME_LIVE')
                if rows[pid][1:] != identity:
                    reject('REMEMBERED_PROCESS_IDENTITY_CHANGED', {'pid': pid, 'ppid': rows[pid][0],
                        'ruid': rows[pid][1], 'euid': rows[pid][2], 'role': 'REMEMBERED_DESCENDANT'})
                if pid in helper_bindings:
                    binding = helper_binding(pid)
                    if binding is None:
                        continue
                    if binding != helper_bindings[pid]:
                        reject('REMEMBERED_HELPER_EXECUTABLE_CHANGED')
                alive.append(pid)
        for pid in rejected_live.keys() - known.keys():
            if not pid_absent(pid, rows):
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
            receipt['failure_stage'] = 'OBSERVE_OWNED_DESCENDANTS'
            remember()
            snapshot_context = 'LIVE_OBSERVATION'
            signal.pthread_sigmask(signal.SIG_SETMASK, mask)
            while process.poll() is None:
                remember()
                if pending:
                    receipt['failure_reason'] = 'CI_CANCELLATION'
                    raise RuntimeError('CI cancelled; forward to owned Mac wrapper')
                if time.monotonic() - began >= timeout:
                    receipt['failure_reason'] = 'WRAPPER_DEADLINE'
                    raise subprocess.TimeoutExpired(argv, timeout)
                try:
                    process.wait(timeout=0.25)
                except subprocess.TimeoutExpired:
                    pass
            if process.returncode != 0 or pending:
                reject('WRAPPER_NONZERO_OR_CANCELLED')
            receipt['result'] = 'PASS_WRAPPER_AND_OWNED_CLEANUP'
            receipt.pop('failure_stage', None)
    except BaseException as error:
        receipt['failure_type'] = type(error).__name__
        receipt.setdefault('failure_reason', 'OWNED_SUPERVISION_ERROR')
        receipt['wrapper_exit_before_cleanup'] = process.poll() if process is not None else None
        # Read only the wrapper's already public phase names; never private logs.
        check = out / 'native-check/check-receipt.json'
        if check.is_file() and not check.is_symlink():
            phases = json.loads(check.read_text()).get('phases', [])
            if phases and phases[-1].get('name') in ('preflight', 'journey', 'controls'):
                receipt['failure_phase'] = phases[-1]['name']
        raise
    finally:
        # Repeated cancellation cannot interrupt the bounded cleanup interval.
        snapshot_context = 'OWNED_CLEANUP'
        signal.pthread_sigmask(signal.SIG_BLOCK, set(handlers))
        try:
            if process is not None:
                end = time.monotonic() + cleanup_seconds
                if process.poll() is None:
                    process.send_signal(signal.SIGTERM)
                    receipt['forwarded_sigterm'] = True
                    receipt['forwarded_sigterm_monotonic'] = round(time.monotonic(), 6)
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
                        if pid in rejected_live or pid in unverified_zombies:
                            continue  # Wait for absence; never signal an unverified PID.
                        # Re-read identity immediately before each individual signal.
                        rows = snapshot()
                        if pid in rows:
                            if states.get(pid, '').startswith('Z'):
                                if rows[pid][1:4] != known[pid][:3]:
                                    reject('ZOMBIE_IDENTITY_CHANGED_BEFORE_REAP')
                                continue  # Already exited; only its parent can reap it.
                            if pid in unverified_zombies:
                                reject('UNVERIFIED_ZOMBIE_BECAME_LIVE_BEFORE_SIGNAL')
                            if rows[pid][1:] != known[pid]:
                                reject('PROCESS_IDENTITY_CHANGED_BEFORE_SIGNAL')
                            if pid in helper_bindings:
                                binding = helper_binding(pid)
                                if binding is None:
                                    continue
                                if binding != helper_bindings[pid]:
                                    reject('HELPER_EXECUTABLE_CHANGED_BEFORE_SIGNAL')
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
                receipt['rejected_observation_cleanup'] = [{'pid': pid, 'removed': pid not in alive,
                    'proof': 'ACTUAL_PID_ABSENCE' if pid not in alive else 'PRESENT_UNVERIFIED_NEVER_SIGNALLED'}
                    for pid in sorted(rejected_live)]
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
            try:
                receipt['wall_seconds'] = round(time.monotonic() - began, 3)
                receipt['cancellation_signals'] = pending
                deferred = signal.sigpending() & set(handlers)
                if deferred:
                    receipt['result'] = 'FAIL'
                    receipt.setdefault('failure_reason', 'CANCELLATION_DURING_OWNED_CLEANUP')
                    receipt['deferred_cancellation_signals'] = sorted(int(s) for s in deferred)
                write(public / 'supervision.json', receipt)
                deferred = signal.sigpending() & set(handlers)
                if deferred:
                    receipt['result'] = 'FAIL'
                    receipt.setdefault('failure_reason', 'CANCELLATION_DURING_OWNED_CLEANUP')
                    receipt['deferred_cancellation_signals'] = sorted(int(s) for s in deferred)
                    write(public / 'supervision.json', receipt)
            finally:
                try:
                    for number, handler in handlers.items():
                        signal.signal(number, handler)
                finally:
                    signal.pthread_sigmask(signal.SIG_SETMASK, mask)


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
            assert row['exit'] in ((0, 2) if name == 'controls' else (0,)) and not job.expired, name + ' failed'
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
        if row['architecture'] == 'i686':
            phase('journey', [sys.executable, '-B', ROOT / 'vanguard/run-portable-journey-diagnostic.py',
                '--tester', package / 'tester.py', '--tester-sha256', row['package_helpers']['tester.py'],
                '--diagnostic', out / 'journey-diagnostic.json', '--out', out / 'journey'])
        else:
            phase('journey', [sys.executable, '-B', package / 'tester.py', 'run', '--out', out / 'journey'])
        control_phase = phase('controls', [sys.executable, '-B', ROOT / 'vanguard/test-portable-refusals.py',
                           '--package', package, '--out', out / 'controls'])
        incomplete = control_coverage(json.loads((out / 'controls/controls.json').read_text()))
        assert control_phase['exit'] == (2 if incomplete else 0)
        receipt['result'] = 'INCOMPLETE_NATIVE_ARCHIVE_CONTROLS' if incomplete else 'PASS_NATIVE_ARCHIVE_JOURNEY'
    finally:
        try:
            if job is not None:
                try:
                    receipt['native_cli_event'] = native_cli_event(package, out, row, backend, job) if architecture == 'i686' else {'status': 'NOT_REQUESTED', 'cause': 'UNKNOWN'}
                finally:
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
                lock_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGINT})
                lock_handlers = {number: signal.getsignal(number) for number in (signal.SIGTERM, signal.SIGINT)}
                try:
                    supervision = json.loads((public / 'supervision.json').read_text())
                    assert supervision['wrapper_reaped'] and all(p['removed'] for p in supervision['cleanup'])
                    assert all(p['removed'] for p in supervision.get('rejected_observation_cleanup', [])), 'unverified observation remains; preserve lock'
                    assert 'cleanup_failure_type' not in supervision, 'preserve lock until owned cleanup is verified'
                    assert not lock.is_symlink() and lock.stat().st_uid == os.getuid() and lock.stat().st_ino == lock_identity
                    lock.unlink()
                    proof['owned_lock_removed'] = True
                finally:
                    try:
                        for number, handler in lock_handlers.items():
                            signal.signal(number, handler)
                    finally:
                        signal.pthread_sigmask(signal.SIG_SETMASK, lock_mask)
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
        incomplete = control_coverage(controls)
        assert not incomplete or args.target.startswith('windows-')
        assert controls['release_manifest_sha256'] == row['release_manifest_sha256']
        assert check['result'] == ('INCOMPLETE_NATIVE_ARCHIVE_CONTROLS' if incomplete else 'PASS_NATIVE_ARCHIVE_JOURNEY')
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
            write(public / name, public_check(value) if name == 'check.json' else value)
        proof['result'] = 'INCOMPLETE_NATIVE_ARCHIVE_CONTROLS' if incomplete else 'PASS_NATIVE_ARCHIVE_JOURNEY_AND_TEN_CONTROLS'
    except BaseException as error:
        proof['failure_type'] = type(error).__name__
        raise
    finally:
        receipt_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGINT}) if os.name == 'posix' else None
        receipt_handlers = {number: signal.getsignal(number) for number in (signal.SIGTERM, signal.SIGINT)} if os.name == 'posix' else {}
        try:
            # These are the same explicit public receipts, including honest failure
            # and owned-cleanup evidence. Private phase logs are never exported.
            if check_root is not None:
                for source, name in [('journey-diagnostic.json', 'journey-diagnostic.json'),
                                     ('journey/result.json', 'journey.json'),
                                     ('controls/controls.json', 'controls.json'),
                                     ('check-receipt.json', 'check.json')]:
                    path = check_root / source
                    if path.is_file() and not path.is_symlink():
                        value = json.loads(path.read_text())
                        write(public / name, public_check(value) if name == 'check.json' else
                              public_diagnostic(value) if name == 'journey-diagnostic.json' else value)
            deferred = signal.sigpending() & set(receipt_handlers) if receipt_handlers else set()
            if deferred:
                proof['result'] = 'FAIL'
                proof['failure_reason'] = 'CANCELLATION_DURING_PUBLIC_RECEIPTS'
            write(public / 'ci-receipt.json', proof)
            deferred = signal.sigpending() & set(receipt_handlers) if receipt_handlers else set()
            if deferred:
                proof['result'] = 'FAIL'
                proof['failure_reason'] = 'CANCELLATION_DURING_PUBLIC_RECEIPTS'
                write(public / 'ci-receipt.json', proof)
            print(proof['result'])
        finally:
            try:
                for number, handler in receipt_handlers.items():
                    signal.signal(number, handler)
            finally:
                if receipt_mask is not None:
                    signal.pthread_sigmask(signal.SIG_SETMASK, receipt_mask)



if __name__ == '__main__':
    if os.name == 'posix':
        def cancelled(number, frame):
            raise RuntimeError('native CI cancelled; preserve owned cleanup receipts')
        signal.signal(signal.SIGTERM, cancelled)
        signal.signal(signal.SIGINT, cancelled)
    main()
