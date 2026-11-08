#!/usr/bin/env python3
"""Inspect final successor bytes and preserved lane contracts, without execution."""
import argparse
import ast
import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile
from portable_provenance import refuse_private_paths

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('archive', type=Path)
parser.add_argument('--previous', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
sha = lambda data: hashlib.sha256(data).hexdigest()

def members(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        assert z.testzip() is None
        result = {n: z.read(n) for n in z.namelist()}
        assert len(result) == len(z.namelist())
        return result

def functions(data):
    source = data.decode(); lines = source.splitlines(True)
    return {n.name: ''.join(lines[n.lineno-1:n.end_lineno]) for n in ast.parse(source).body if isinstance(n, ast.FunctionDef)}

raw = args.archive.read_bytes(); refuse_private_paths(raw)
files = members(raw); previous = members(args.previous.read_bytes()); prefix = 'meownero-windows-test/'
manifest = json.loads(files[prefix + 'bundle.json'])
assert set(manifest['files']) == {n[len(prefix):] for n in files if n != prefix + 'bundle.json'}
for name, digest in manifest['files'].items(): assert sha(files[prefix + name]) == digest
lanes = {}
for target, lane in manifest['lanes'].items():
    root = prefix + lane['root'] + '/'
    inputs = json.loads(files[root + 'vanguard/ci-inputs.json'])
    assert sha(files[root + 'vanguard/ci-inputs.json']) == lane['inputs_sha256']
    row = inputs['targets'][target]; archive = files[prefix + lane['archive']]
    assert sha(archive) == row['archive_sha256'] and len(archive) == row['archive_bytes']
    old_lane = json.loads(previous[prefix + 'bundle.json'])['lanes'][target]
    assert archive == previous[prefix + old_lane['archive']], 'packaged tester/program/provenance changed unexpectedly'
    package = members(archive); package_root = row['package_name'] + '/'
    release_raw = package[package_root + 'release.json']; release = json.loads(release_raw)
    assert sha(release_raw) == row['release_manifest_sha256']
    for name, digest in release['files'].items(): assert sha(package[package_root + name]) == digest
    for name, digest in row['package_helpers'].items(): assert sha(package[package_root + name]) == digest
    for name, digest in row['program_sha256'].items(): assert sha(package[package_root + 'bin/' + name + '.exe']) == digest
    offset = 0
    for part in row['parts']:
        data = archive[offset:offset+part['bytes']]; assert sha(data) == part['sha256']; offset += part['bytes']
    assert offset == len(archive)
    for name, digest in inputs['source_files'].items(): assert sha(files[root + name]) == digest
    controller = files[root + 'vanguard/run-portable-ci.py']
    assert sha(controller) == manifest['helper_bindings']['controllers'][target]
    old_functions = functions(previous[root + 'vanguard/run-portable-ci.py']); new_functions = functions(controller)
    changed = {n for n in old_functions if old_functions[n] != new_functions[n]}
    assert changed == {'public_diagnostic', 'public_check', 'windows_check', 'main'}
    assert set(new_functions) - set(old_functions) == {'control_coverage'}
    assert 'windows_arm64_qualification' in new_functions if target == 'windows-aarch64' else 'wait_journey_capacity' in new_functions
    for name in ('test-portable-refusals.py', 'run-portable-journey-diagnostic.py'):
        assert sha(files[root + 'vanguard/' + name]) == manifest['helper_bindings']['files'][name]
    lanes[target] = {'controller_sha256': sha(controller), 'inputs_sha256': lane['inputs_sha256'],
        'archive_sha256': sha(archive), 'release_manifest_sha256': sha(release_raw),
        'packaged_testers_programs_and_provenance': 'BYTE_IDENTICAL_TO_PREVIOUS_SANITIZED_BUNDLE',
        'unaffected_controller_functions': 'BYTE_IDENTICAL', 'changed_controller_functions': sorted(changed),
        'native_acceptance': 'NOT_RUN_LINUX_HOST'}
result = {'result': 'PASS_EXACT_SUCCESSOR_BINDINGS_AND_PRESERVED_GUARDS', 'archive': args.archive.name,
    'bytes': len(raw), 'sha256': sha(raw), 'bundle_manifest_sha256': sha(files[prefix + 'bundle.json']),
    'helper_source_revision': manifest['helper_bindings']['source_revision'], 'lanes': lanes,
    'private_home_path_scan': 'PASS_RECURSIVE', 'native_windows_execution': 'NOT_RUN'}
args.out.write_text(json.dumps(result, indent=2) + '\n'); print(json.dumps(result, indent=2))
