#!/usr/bin/env python3
"""Linux-runnable checks for the Darwin kernel process-table observer.

Covers the kinfo_proc decoding, the fail-closed layout guard and the bounded
deadline. Native Darwin reads are qualified only by native macOS jobs.
"""
import ctypes
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time

spec = importlib.util.spec_from_file_location('table_observer', Path(__file__).with_name('run-portable-ci.py'))
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)


def record(pid, ppid, ruid, euid, sec, usec, stat, comm):
    value = ci._DarwinKinfoProc()
    value.kp_proc.p_pid, value.kp_proc.p_stat, value.kp_proc.p_comm = pid, bytes([stat]), comm
    value.kp_proc.p_starttime.tv_sec, value.kp_proc.p_starttime.tv_usec = sec, usec
    value.kp_eproc.e_ppid, value.kp_eproc.e_pcred.p_ruid, value.kp_eproc.e_ucred.cr_uid = ppid, ruid, euid
    return bytes(value)


def main():
    checks = {}
    # Independently derived LP64 <sys/sysctl.h> offsets (extern_proc 296 + eproc 352).
    K, E, P, U = ci._DarwinKinfoProc, ci._DarwinExternProc, ci._DarwinPcred, ci._DarwinUcred
    eproc = K.kp_eproc.offset
    checks['layout_offsets'] = (ctypes.sizeof(K), E.p_starttime.offset, E.p_stat.offset, E.p_pid.offset,
        E.p_comm.offset, eproc + ci._DarwinEproc.e_pcred.offset + P.p_ruid.offset,
        eproc + ci._DarwinEproc.e_ucred.offset + U.cr_uid.offset, eproc + ci._DarwinEproc.e_ppid.offset) == \
        (648, 0, 36, 40, 243, 392, 420, 560)
    raw = record(4242, 1, 501, 0, 1762585200, 123456, 2, b'ps') + record(4243, 4242, 501, 501, 1762585201, 7, 5, b'monerod')
    table = ci.parse_darwin_process_table(raw)
    checks['decode_rows'] = table == [(4242, 1, 501, 0, (1762585200, 123456), 'R', 'ps'),
                                      (4243, 4242, 501, 501, (1762585201, 7), 'Z', 'monerod')]
    try:
        ci.parse_darwin_process_table(raw[:-8])
        checks['truncated_table_refused'] = False
    except AssertionError as error:
        checks['truncated_table_refused'] = str(error) == 'KERNEL_PROCESS_TABLE_LAYOUT_MISMATCH'
    original = ci.darwin_process_table
    try:
        ci.darwin_process_table = lambda pid=None: (time.sleep(2), table)[1]
        receipt, began = {}, time.monotonic()
        try:
            ci.kernel_table_output(timeout=0.3, receipt=receipt, context='TEST')
            checks['deadline_enforced'] = False
        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - began
            cost = receipt['snapshot_cost']['recent'][-1]
            checks['deadline_enforced'] = elapsed < 1.0 and cost['result'] == 'TIMEOUT' and cost['timeout_seconds'] == 0.3
        ci.darwin_process_table = lambda pid=None: table
        receipt = {}
        checks['pass_receipt'] = (ci.kernel_table_output(timeout=5, receipt=receipt, context='TEST') == table and
            receipt['snapshot_cost']['recent'][-1]['result'] == 'PASS' and
            receipt['snapshot_cost']['recent'][-1]['process_rows'] == 2)

        def broken(pid=None):
            raise AssertionError('KERNEL_PROCESS_TABLE_LAYOUT_MISMATCH')
        ci.darwin_process_table = broken
        receipt = {}
        try:
            ci.kernel_table_output(timeout=5, receipt=receipt, context='TEST')
            checks['layout_error_propagates'] = False
        except AssertionError:
            checks['layout_error_propagates'] = receipt['snapshot_cost']['recent'][-1]['result'] == 'FAIL'
    finally:
        ci.darwin_process_table = original
    failed = sorted(name for name, ok in checks.items() if not ok)
    print(json.dumps({'result': 'PASS' if not failed else 'FAIL', 'failed': failed, 'checks': checks,
                      'evidence': 'LINUX_DECODE_AND_DEADLINE_ONLY_NOT_NATIVE_DARWIN'}, indent=2))
    return 0 if not failed else 1


if __name__ == '__main__':
    raise SystemExit(main())
