#!/usr/bin/env python3
"""Run the frozen Windows tester and export its public receipts.

Examples: python windows-test-bundle.py
          python windows-test-bundle.py --prepare-only --target windows-i686
"""
import argparse
import contextlib
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import runpy
import shutil
import sys
import uuid
import zipfile

ROOT = Path(__file__).resolve().parent
PUBLIC = ('ci-receipt.json', 'check.json', 'journey.json', 'controls.json',
          'journey-diagnostic.json')


class Refused(Exception):
    pass


def require(condition, reason):
    if not condition:
        raise Refused(reason)


def safe_file(path):
    require(path.is_file() and not path.is_symlink() and path.stat().st_nlink == 1,
            'UNSAFE_OR_MISSING_FILE')
    require(not any(p.is_symlink() or p.is_junction() for p in (path, *path.parents)),
            'REDIRECTED_PATH')
    return path


def digest(path):
    with safe_file(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def relative(root, name):
    path = PurePosixPath(name)
    require(path.parts and not path.is_absolute() and '..' not in path.parts
            and '\\' not in name and ':' not in name, 'UNSAFE_MANIFEST_PATH')
    return root.joinpath(*path.parts)


def choose_target(process_machine, native_machine):
    require(process_machine == 0, 'INSTALL_NATIVE_PYTHON_EMULATED_PROCESS_REFUSED')
    require(native_machine in (0x8664, 0xaa64), 'REQUIRES_X64_OR_ARM64_WINDOWS')
    return 'windows-i686' if native_machine == 0x8664 else 'windows-aarch64'


def native_target():
    require(os.name == 'nt' and platform.python_implementation() == 'CPython',
            'REQUIRES_WINDOWS_CPYTHON')
    require(sys.version_info >= (3, 13) and ctypes.sizeof(ctypes.c_void_p) == 8,
            'INSTALL_NATIVE_64BIT_CPYTHON_3_13_OR_LATER')
    # https://learn.microsoft.com/en-us/windows/win32/api/wow64apiset/nf-wow64apiset-iswow64process2
    kernel = ctypes.WinDLL('kernel32', use_last_error=True, winmode=0x800)
    current = kernel.GetCurrentProcess
    current.restype, current.argtypes = wintypes.HANDLE, ()
    query = kernel.IsWow64Process2
    query.restype = wintypes.BOOL
    query.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.USHORT), ctypes.POINTER(wintypes.USHORT))
    process, native = wintypes.USHORT(), wintypes.USHORT()
    require(query(current(), ctypes.byref(process), ctypes.byref(native)), 'ARCHITECTURE_QUERY_FAILED')
    return choose_target(process.value, native.value)


def stage(root, manifest, target, work):
    lane = manifest['lanes'][target]
    source = relative(root, lane['root'])
    inputs_path = source / 'vanguard/ci-inputs.json'
    require(digest(inputs_path) == lane['inputs_sha256'], 'INPUT_MANIFEST_HASH_MISMATCH')
    inputs = json.loads(inputs_path.read_text())
    row = inputs['targets'][target]
    for name, expected in inputs['source_files'].items():
        require(digest(relative(source, name)) == expected, 'FROZEN_CONTROLLER_HASH_MISMATCH')
    for path in source.rglob('*'):
        if path.is_file():
            destination = work / path.relative_to(source)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(safe_file(path), destination)
    archive = relative(root, lane['archive'])
    require(archive.stat().st_size == row['archive_bytes'] and digest(archive) == row['archive_sha256'],
            'FROZEN_ARCHIVE_HASH_MISMATCH')
    with archive.open('rb') as stream:
        for part in row['parts']:
            path = relative(work, part['path'])
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as output:
                remaining = part['bytes']
                while remaining:
                    data = stream.read(min(remaining, 1024 * 1024))
                    require(data, 'ARCHIVE_TRUNCATED')
                    output.write(data)
                    remaining -= len(data)
            require(digest(path) == part['sha256'], 'FROZEN_PART_HASH_MISMATCH')
        require(not stream.read(1), 'ARCHIVE_HAS_EXTRA_BYTES')
    return lane, row


def export_report(path, receipt, public):
    """Only the reviewed controller's fixed public JSON files may leave the run."""
    with zipfile.ZipFile(path, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('bundle-receipt.json', json.dumps(receipt, indent=2) + '\n')
        for name in PUBLIC:
            source = public / name
            if source.exists():
                safe_file(source)
                require(source.stat().st_size <= 2 * 1024**2, 'PUBLIC_RECEIPT_TOO_LARGE')
                value = json.loads(source.read_text())
                archive.writestr('public/' + name, json.dumps(value, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--prepare-only', action='store_true', help='Check exact bytes; starts no tester programs')
    parser.add_argument('--target', choices=('windows-i686', 'windows-aarch64'),
                        help='Select bytes for --prepare-only; runtime always detects the native machine')
    args = parser.parse_args()
    require(not sys.flags.optimize, 'PYTHON_OPTIMIZATION_REFUSED')
    require(args.prepare_only or args.target is None, 'TARGET_OVERRIDE_ONLY_FOR_BYTE_CHECKS')
    require(not any(p.is_symlink() or p.is_junction() for p in (ROOT, *ROOT.parents)), 'REDIRECTED_BUNDLE')
    manifest = json.loads(safe_file(ROOT / 'bundle.json').read_text())
    # A fresh directory is never reused or overwritten. Private files stay here.
    session = ROOT / ('run-' + uuid.uuid4().hex)
    session.mkdir(mode=0o700)
    receipt = {'schema': 'meownero-windows-test-bundle-report/1', 'result': 'NOT_RUN',
               'bundle_manifest_sha256': digest(ROOT / 'bundle.json'), 'prepare_only': args.prepare_only,
               'native_acceptance': 'REQUIRES_INDEPENDENT_REVIEW', 'private_data_exported': False}
    report = session / 'report.zip'
    try:
        for name, expected in manifest['files'].items():
            require(digest(relative(ROOT, name)) == expected, 'BUNDLE_HASH_MISMATCH')
        target = (args.target or 'windows-i686') if args.prepare_only else native_target()
        receipt['target'] = target
        require(shutil.disk_usage(session).free >= 10 * 1024**3, 'REQUIRES_10_GIB_FREE_DISK')
        work = session / 'controller'
        work.mkdir(mode=0o700)
        lane, row = stage(ROOT, manifest, target, work)
        receipt['archive_sha256'] = row['archive_sha256']
        receipt['controller_sha256'] = digest(work / 'vanguard/run-portable-ci.py')
        receipt['result'] = 'FAIL'
        sys.argv = [str(work / 'vanguard/run-portable-ci.py'), '--inputs', str(work / 'vanguard/ci-inputs.json'),
                    '--inputs-sha256', lane['inputs_sha256'], '--target', target, '--out', str(session / 'output')]
        if args.prepare_only:
            sys.argv.append('--prepare-only')
        # https://docs.python.org/3.13/library/runpy.html#runpy.run_path
        # Same process preserves the controller's own console, Jobs and finalizers.
        saved_environment = {key: os.environ.pop(key, None) for key in ('GITHUB_RUN_ID', 'GITHUB_SHA')}
        try:
            with (session / 'private-controller.log').open('w') as log:
                with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                    runpy.run_path(sys.argv[0], run_name='__main__')
        finally:
            for key, value in saved_environment.items():
                if value is not None:
                    os.environ[key] = value
        result = json.loads((session / 'output/public/ci-receipt.json').read_text())['result']
        expected = 'PASS_INPUT_BYTES_ONLY_NATIVE_EXECUTION_UNTESTED' if args.prepare_only else 'PASS_NATIVE_ARCHIVE_JOURNEY_AND_TEN_CONTROLS'
        require(result == expected, 'CONTROLLER_DID_NOT_PASS')
        receipt['result'] = result
    except BaseException as error:
        receipt['failure_type'] = type(error).__name__
        if isinstance(error, Refused):
            receipt['reason'] = str(error)
    finally:
        export_report(report, receipt, session / 'output/public')
    print('Result:', receipt['result'])
    if 'reason' in receipt:
        print('Reason:', receipt['reason'])
    print('Share only this report:', report)
    print('SHA256:', digest(report))
    print('Keep the run folder local. It can contain disposable wallets and private logs.')
    return 0 if receipt['result'].startswith('PASS_') else 1


if __name__ == '__main__':
    sys.dont_write_bytecode = True
    raise SystemExit(main())
