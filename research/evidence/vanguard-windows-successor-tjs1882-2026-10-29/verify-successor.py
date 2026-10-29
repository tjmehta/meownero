#!/usr/bin/env python3
"""Verify exact successor bytes against the original bundle, then run byte checks.

Usage: python3 -B verify-successor.py FINAL_ZIP ORIGINAL_ZIP NEW_EVIDENCE_DIRECTORY
No Windows execution is claimed by this Linux check.
"""
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import time
import zipfile


def sha(data):
    return hashlib.sha256(data).hexdigest()


def payload(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert archive.testzip() is None
        names = archive.namelist()
        assert len(set(names)) == len(names)
        for info in archive.infolist():
            path = PurePosixPath(info.filename)
            assert path.parts and not path.is_absolute() and '..' not in path.parts
            assert '\\' not in info.filename and ':' not in info.filename
            assert stat.S_ISREG(info.external_attr >> 16)
        return {name: archive.read(name) for name in names}


def main():
    started = time.monotonic()
    final_path, original_path, out = map(Path, sys.argv[1:])
    out.mkdir()
    final_bytes, original_bytes = final_path.read_bytes(), original_path.read_bytes()
    assert sha(original_bytes) == '69b182c744e3e7eb00dcfb0b8e3fe6770f7b23441dea1df7408e9c695aa1064b'
    original, final = payload(original_bytes), payload(final_bytes)
    prefix = 'meownero-windows-test/'
    manifest = json.loads(final[prefix + 'bundle.json'])
    for name, expected in manifest['files'].items():
        assert sha(final[prefix + name]) == expected
    for name in ['windows-test-bundle.py', 'RUN-TEST.cmd']:
        assert original[prefix + name] == final[prefix + name]
    private_pattern = re.compile(rb'/(?:home|Users)/' + re.escape(Path.home().name.encode()) + rb'/')
    credentials = [value.encode() for key, value in os.environ.items()
                   if re.search(r'(TOKEN|KEY|PASSWORD|SECRET|CREDENTIAL)', key) and len(value) >= 16]
    scanned = 0

    def clean(data):
        nonlocal scanned
        scanned += 1
        assert not private_pattern.search(data), 'private home path'
        for value in credentials:
            assert value not in data, 'current credential value'

    clean(final_bytes)
    for name, data in final.items():
        clean(name.encode())
        clean(data)
    lanes = {}
    for target, lane in manifest['lanes'].items():
        old_name = 'meownero-vanguard-' + target + '.zip'
        old_archive = original[prefix + old_name]
        new_archive = final[prefix + lane['archive']]
        old, new = payload(old_archive), payload(new_archive)
        assert old.keys() == new.keys()
        root = old_name[:-4] + '/'
        changed = {name[len(root):] for name in old if old[name] != new[name]}
        expected = {'BUILD.json', 'release.json'}
        if target == 'windows-i686':
            expected |= {'build-evidence/' + name for name in (
                'cached-build-receipt.json', 'pre-exception-probe-build-receipt.json',
                'i686-exception-probe-input.json', 'i686-exception-probe-cross.py',
                'i686-exception-probe-cross-receipt.json')}
        assert changed == expected
        for name, data in new.items():
            clean(name.encode())
            clean(data)
            if name.endswith('.json') and name[len(root):] in changed:
                record = json.loads(data)['distribution_rewrite']
                assert record['original_member_sha256'] == sha(old[name])
                assert record['original_archive_sha256'] == sha(old_archive)
                assert record['meaning'] == 'DISTRIBUTION_COPY_NOT_ORIGINAL_EXECUTION_BYTES'
            elif name.endswith('i686-exception-probe-cross.py'):
                assert sha(old[name]).encode() in data
                assert sha(old_archive).encode() in data
        release = json.loads(new[root + 'release.json'])
        assert set(release['files']) == {name[len(root):] for name in new if name != root + 'release.json'}
        for name, expected_sha in release['files'].items():
            assert sha(new[root + name]) == expected_sha
        assert release['build_receipt']['sha256'] == sha(new[root + 'BUILD.json'])
        if target == 'windows-i686':
            evidence = root + 'build-evidence/'
            build = json.loads(new[root + 'BUILD.json'])
            pre = json.loads(new[evidence + 'pre-exception-probe-build-receipt.json'])
            inputs = json.loads(new[evidence + 'i686-exception-probe-input.json'])
            cross = json.loads(new[evidence + 'i686-exception-probe-cross-receipt.json'])
            assert build['cached_build']['receipt_sha256'] == pre['cached_build']['receipt_sha256'] == sha(new[evidence + 'cached-build-receipt.json'])
            assert inputs['source_build_receipt_sha256'] == sha(new[evidence + 'pre-exception-probe-build-receipt.json'])
            assert cross['input_manifest_sha256'] == sha(new[evidence + 'i686-exception-probe-input.json'])
            assert cross['script_sha256'] == sha(new[evidence + 'i686-exception-probe-cross.py'])
            assert build['exception_probe']['cross_receipt_sha256'] == sha(new[evidence + 'i686-exception-probe-cross-receipt.json'])
            assert cross['inputs_archive_sha256'] == json.loads(old[evidence + 'i686-exception-probe-cross-receipt.json'])['inputs_archive_sha256']
        ci_name = prefix + lane['root'] + '/vanguard/ci-inputs.json'
        ci = json.loads(final[ci_name])
        row = ci['targets'][target]
        assert sha(final[ci_name]) == lane['inputs_sha256']
        assert row['archive_name'] == lane['archive'] and old_name != row['archive_name']
        assert row['archive_bytes'] == len(new_archive) and row['archive_sha256'] == sha(new_archive)
        assert row['release_manifest_sha256'] == sha(new[root + 'release.json'])
        offset = 0
        for part in row['parts']:
            data = new_archive[offset:offset + part['bytes']]
            assert len(data) == part['bytes'] and sha(data) == part['sha256']
            offset += part['bytes']
        assert offset == len(new_archive)
        for name, expected_sha in row.get('native_exception_probe', {}).get('files', {}).items():
            assert sha(new[root + name]) == expected_sha
        for name, expected_sha in ci['source_files'].items():
            key = prefix + lane['root'] + '/' + name
            assert sha(final[key]) == expected_sha
            assert original[key] == final[key]
        lanes[target] = {'archive': lane['archive'], 'bytes': len(new_archive), 'sha256': sha(new_archive),
                         'changed_members': sorted(changed), 'unchanged_members': len(new) - len(changed),
                         'all_other_member_bytes': 'IDENTICAL', 'release_input_part_bindings': 'PASS'}
    extract = out / 'extracted'
    with zipfile.ZipFile(final_path) as archive:
        archive.extractall(extract)
    root = extract / 'meownero-windows-test'
    checks = []

    def run(label, args, expected_exit, expected_result, reason=None):
        env = dict(os.environ, GITHUB_RUN_ID='SENTINEL_RUN_DO_NOT_EXPORT', GITHUB_SHA='SENTINEL_COMMIT_DO_NOT_EXPORT')
        process = subprocess.run([sys.executable, '-B', str(root / 'windows-test-bundle.py'), *args],
                                 capture_output=True, text=True, timeout=180, env=env)
        log = (process.stdout + process.stderr).replace(str(Path.home()) + '/', '/BUILD_HOME/')
        (out / (label + '.log')).write_text(log)
        (out / (label + '-process.json')).write_text(json.dumps({'exit': process.returncode}))
        marker = 'Share only this report: '
        report_line = next(line for line in process.stdout.splitlines() if line.startswith(marker))
        report = Path(report_line[len(marker):])
        shutil.copyfile(report, out / (label + '-report.zip'))
        data = report.read_bytes()
        with zipfile.ZipFile(report) as archive:
            receipt = json.loads(archive.read('bundle-receipt.json'))
            for name in archive.namelist():
                content = archive.read(name)
                assert b'SENTINEL_RUN_DO_NOT_EXPORT' not in content and b'SENTINEL_COMMIT_DO_NOT_EXPORT' not in content
        assert process.returncode == expected_exit and receipt['result'] == expected_result, process.stdout
        if reason:
            assert receipt['reason'] == reason
        checks.append({'check': label, 'exit': process.returncode, 'result': receipt['result'],
                       'reason': receipt.get('reason'), 'report_sha256': sha(data)})

    for target in lanes:
        run(target, ['--prepare-only', '--target', target], 0, 'PASS_INPUT_BYTES_ONLY_NATIVE_EXECUTION_UNTESTED')
    run('non-windows-refusal', [], 1, 'NOT_RUN', 'REQUIRES_WINDOWS_CPYTHON')
    inputs_path = root / 'i68635/vanguard/ci-inputs.json'
    saved = inputs_path.read_bytes()
    try:
        inputs_path.write_bytes(saved + b' ')
        run('tampered-input-refusal', ['--prepare-only', '--target', 'windows-i686'], 1, 'NOT_RUN', 'BUNDLE_HASH_MISMATCH')
    finally:
        inputs_path.write_bytes(saved)
    result = {'schema': 'meownero-windows-successor-verification/1',
              'source_revision': manifest['source_revision'], 'python': sys.version,
              'bundle': {'bytes': len(final_bytes), 'sha256': sha(final_bytes)}, 'lanes': lanes, 'checks': checks,
              'safe_regular_outer_members': len(final), 'outer_file_bindings': len(manifest['files']),
              'private_home_scan': 'ABSENT', 'current_credential_values_checked': len(credentials),
              'current_credential_values_found': False, 'scanned_items': scanned,
              'windows_execution': 'NOT_RUN_NO_QUALIFIED_WINDOWS_RUNTIME',
              'duration_seconds': time.monotonic() - started}
    (out / 'verification.json').write_text(json.dumps(result, indent=2) + '\n')
    shutil.rmtree(extract)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
