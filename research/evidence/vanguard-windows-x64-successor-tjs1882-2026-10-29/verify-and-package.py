#!/usr/bin/env python3
"""Create and verify the provenance-only x64 successor; no Windows execution.

Usage: python3 -B verify-and-package.py ORIGINAL_ZIP NEW_OUTPUT NEW_EVIDENCE
Uses the existing reviewed portable_provenance helper, then checks the exact
two-member transformation independently of that helper's returned inventory.
"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import stat
import subprocess
import sys
import tempfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'vanguard'))
from portable_provenance import (PLACEHOLDER, home_prefixes, refuse_private_paths,
                                 replace_home, successor_archive)

ORIGINAL = '859d4644815b4c990cca093c6d74bb077e6ab74f267236ed84746d5b6cf690d0'
PREFIX = 'meownero-vanguard-windows-x86_64/'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def payload(path):
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        infos = archive.infolist()
        assert len(infos) == len({info.filename for info in infos})
        for info in infos:
            name = PurePosixPath(info.filename)
            assert name.parts and not name.is_absolute() and '..' not in name.parts
            assert '\\' not in info.filename and ':' not in info.filename
            assert info.filename.startswith(PREFIX) and stat.S_ISREG(info.external_attr >> 16)
        return {info.filename: archive.read(info) for info in infos}


def main():
    assert not sys.flags.optimize, 'optimized Python refused'
    started = time.monotonic()
    original, output, evidence = map(Path, sys.argv[1:])
    assert sha(original.read_bytes()) == ORIGINAL
    old = payload(original)
    try:
        refuse_private_paths(original.read_bytes())
    except ValueError as error:
        assert str(error) == 'PRIVATE_HOME_PREFIX_IN_DISTRIBUTABLE'
    else:
        raise AssertionError('known-bad original was accepted')
    output.mkdir()
    evidence.mkdir()
    archive = output / 'meownero-vanguard-windows-x86_64-sanitized-v1.zip'
    rewrite = successor_archive(original, archive)
    new = payload(archive)
    assert old.keys() == new.keys()
    changed = sorted(name[len(PREFIX):] for name in old if old[name] != new[name])
    assert changed == ['BUILD.json', 'release.json']
    # Independently calculate the permitted semantic changes, without relying
    # on successor_archive's declared list or binding updates.
    for name in changed:
        before, after = old[PREFIX + name], new[PREFIX + name]
        actual = json.loads(after)
        record = actual.pop('distribution_rewrite')
        expected = json.loads(replace_home(before.decode()))
        updates = []
        if name == 'release.json':
            for field, value in expected['files'].items():
                if value == sha(old[PREFIX + 'BUILD.json']):
                    expected['files'][field] = sha(new[PREFIX + 'BUILD.json'])
                    updates.append('/files/' + field)
            expected['build_receipt']['sha256'] = sha(new[PREFIX + 'BUILD.json'])
            updates.append('/build_receipt/sha256')
        assert actual == expected
        assert record['original_member_sha256'] == sha(before)
        assert record['original_archive_sha256'] == ORIGINAL
        assert record['home_prefix_placeholder'] == PLACEHOLDER
        assert record['meaning'] == 'DISTRIBUTION_COPY_NOT_ORIGINAL_EXECUTION_BYTES'
        assert sorted(row['field'] for row in record['binding_updates']) == sorted(updates)
        for row in record['binding_updates']:
            assert row['original_sha256'] == sha(old[PREFIX + 'BUILD.json'])
            assert row['successor_sha256'] == sha(new[PREFIX + 'BUILD.json'])
    release = json.loads(new[PREFIX + 'release.json'])
    assert set(release['files']) == {name[len(PREFIX):] for name in new if name != PREFIX + 'release.json'}
    for name, expected in release['files'].items():
        assert sha(new[PREFIX + name]) == expected
    assert release['build_receipt']['sha256'] == sha(new[PREFIX + 'BUILD.json'])
    assert release['status'] == 'BUILT_UNTESTED' and release['native_journey'] == 'UNTESTED'
    assert release['upstream_commit'] == 'e151643c5269c83bf24a83b2548e2493876026b2'
    programs = {}
    for name in ('monerod.exe', 'monero-wallet-cli.exe', 'monero-wallet-rpc.exe'):
        data = new[PREFIX + 'bin/' + name]
        assert data == old[PREFIX + 'bin/' + name] and data[:2] == b'MZ'
        offset = int.from_bytes(data[60:64], 'little')
        assert data[offset:offset + 4] == b'PE\0\0'
        assert int.from_bytes(data[offset + 4:offset + 6], 'little') == 0x8664
        assert int.from_bytes(data[offset + 24:offset + 26], 'little') == 0x20b
        programs[name] = sha(data)
    credentials = [value.encode() for key, value in os.environ.items()
                   if re.search(r'(TOKEN|KEY|PASSWORD|SECRET|CREDENTIAL)', key) and len(value) >= 16]
    for data in [archive.read_bytes(), *new.values()]:
        refuse_private_paths(data)
        assert not any(value in data for value in credentials), 'current credential value found'
    saved = archive.read_bytes()
    try:
        successor_archive(original, archive)
    except FileExistsError:
        pass
    else:
        raise AssertionError('output collision not refused')
    assert archive.read_bytes() == saved
    # An actual clean extraction and the unchanged packaged entrypoint's
    # wrong-platform refusal. This cannot observe a Windows-native journey.
    with tempfile.TemporaryDirectory(prefix='tjs1882-x64-successor-') as folder:
        with zipfile.ZipFile(archive) as stream:
            stream.extractall(folder)
        extracted = Path(folder) / PREFIX
        for name, expected in release['files'].items():
            assert sha((extracted / name).read_bytes()) == expected
        assert platform.system() == 'Linux', 'this refusal witness requires Linux'
        check = subprocess.run([sys.executable, '-B', str(extracted / 'tester.py'), 'preflight'],
                               capture_output=True, text=True, timeout=60)
        assert check.returncode != 0 and 'wrong operating system' in check.stderr
        assert not list(extracted.glob('.tester.lock*'))
        (evidence / 'wrong-platform-refusal.json').write_text(json.dumps({
            'exit': check.returncode, 'reason': 'wrong operating system',
            'windows_execution': 'NOT_RUN', 'owned_extraction': 'REMOVED_ON_CONTEXT_EXIT'}, indent=2) + '\n')
    parts = []
    with archive.open('rb') as stream:
        while data := stream.read(8 * 1024**2):
            name = archive.name + '.part-' + str(len(parts) + 1).zfill(4)
            (output / name).write_bytes(data)
            parts.append({'file': name, 'bytes': len(data), 'sha256': sha(data)})
    assert sha(b''.join((output / row['file']).read_bytes() for row in parts)) == sha(saved)
    report = {'schema': 'meownero-windows-x64-provenance-successor/1',
              'issue': 'TJS-1882', 'run_id': os.environ.get('PAPERCLIP_RUN_ID'),
              'source_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'helper_sha256': sha((ROOT / 'vanguard/portable_provenance.py').read_bytes()),
              'verifier_sha256': sha(Path(__file__).read_bytes()), 'python': sys.version,
              'original_archive_sha256': ORIGINAL,
              'archive': {'file': archive.name, 'bytes': len(saved), 'sha256': sha(saved)},
              'release_manifest_sha256': sha(new[PREFIX + 'release.json']),
              'rewritten_members': changed, 'unchanged_members': len(new) - len(changed),
              'all_other_member_bytes': 'IDENTICAL', 'program_sha256': programs,
              'safe_regular_members': len(new), 'release_file_bindings': len(release['files']),
              'provenance_semantic_comparison': 'PASS', 'private_home_scan': 'ABSENT_UTF8_UTF16',
              'known_bad_original_refusal': 'PASS', 'collision_preservation': 'PASS',
              'clean_extraction': 'PASS', 'packaged_wrong_platform_refusal': 'PASS',
              'current_credential_values_checked': len(credentials), 'current_credential_values_found': False,
              'native_windows_execution_this_run': 'NOT_RUN',
              'native_acceptance': 'AWAITING_SCOPED_REVIEW_OF_SUCCESSOR_AND_UNCHANGED_BYTE_BINDING',
              'historical_witness': 'Server2025 x64, run37998310375; unchanged program/helper bytes only',
              'parts': parts, 'provenance_rewrite': rewrite,
              'duration_seconds': time.monotonic() - started}
    assert sha(original.read_bytes()) == ORIGINAL
    (output / 'SHA256SUMS').write_text(sha(saved) + '  ' + archive.name + '\n' +
        ''.join(row['sha256'] + '  ' + row['file'] + '\n' for row in parts))
    (evidence / 'verification.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in ('archive', 'rewritten_members', 'unchanged_members',
                                                  'safe_regular_members', 'native_windows_execution_this_run')}))


if __name__ == '__main__':
    main()
