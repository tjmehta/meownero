#!/usr/bin/env python3
"""Assemble sanitized i68635 and ARM13 successors without rebuilding programs."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from portable_provenance import refuse_private_paths, successor_archive

ROOT = Path(__file__).resolve().parent.parent
I686_INPUTS = 'a49c9c833e624c6e8abce07224f715ae6d40b345f18554b77164f4e4e7c77f2f'
ARM_CONTROLLER = '7a04b1ff20735ecae4d8ec14bef6e84a017b758020d06a68d77eadd8bafdc382'
ARCHIVES = {'windows-i686': '3a0a34d874184165a83f9025cdabd18b67b19fa862c57cfac5b04d21d736e745',
            'windows-aarch64': 'fff26ea94928d2756cbf4b4b59bd2277a685e980d482cf389c8be405617ae15d'}


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def check_bundle(bundle):
    for path in bundle.rglob('*'):
        if path.is_file():
            refuse_private_paths(path.relative_to(bundle).as_posix().encode())
            refuse_private_paths(path.read_bytes())


def successor_helpers(lane, inputs, target, bindings):
    """Apply the reviewed delta to each frozen lane, preserving its own guards."""
    source = bindings['source_revision']
    assert len(source) == 40 and set(source) <= set('0123456789abcdef')
    provenance = {'source_revision': source, 'baseline_revision': bindings['baseline_revision'], 'files': {}}
    for name, expected in bindings['files'].items():
        assert name in {'run-portable-ci.py', 'run-portable-journey-diagnostic.py', 'test-portable-refusals.py'}
        path = 'vanguard/' + name
        data = subprocess.check_output(['git', 'show', source + ':' + path], cwd=ROOT)
        assert hashlib.sha256(data).hexdigest() == expected
        original = (lane / path).read_bytes() if (lane / path).exists() else None
        if name == 'run-portable-ci.py':
            patch = bindings['controller_patches'][target]
            delta = subprocess.check_output(['git', 'show', source + ':' + patch['path']], cwd=ROOT)
            assert hashlib.sha256(delta).hexdigest() == patch['sha256']
            with tempfile.TemporaryDirectory(prefix='tjs1882-helper-delta-') as folder:
                frozen = Path(folder) / path
                frozen.parent.mkdir()
                frozen.write_bytes(original)
                subprocess.run(['git', 'apply', '--check', '-'], input=delta, cwd=folder, check=True)
                subprocess.run(['git', 'apply', '-'], input=delta, cwd=folder, check=True)
                data = frozen.read_bytes()
            assert hashlib.sha256(data).hexdigest() == bindings['controllers'][target]
        elif original is not None:
            assert hashlib.sha256(original).hexdigest() == bindings['predecessors'][name]
        (lane / path).write_bytes(data)
        inputs['source_files'][path] = hashlib.sha256(data).hexdigest()
        provenance['files'][path] = {'predecessor_sha256': hashlib.sha256(original).hexdigest() if original else None,
                                    'successor_sha256': inputs['source_files'][path]}
    return provenance


def main():
    if sys.flags.optimize:
        raise RuntimeError('Python optimization is refused for hash-bound assembly')
    parser = argparse.ArgumentParser(description=__doc__, epilog='Example: python vanguard/make-windows-test-bundle.py --out build/windows-test-bundle')
    parser.add_argument('--out', type=Path, required=True, help='New output directory; collisions are refused')
    parser.add_argument('--i686-handoff', type=Path, default=ROOT / 'build/tjs1882-run2fb8c59d-i68635-publication-handoff/i68635-frozen-source-handoff.json')
    parser.add_argument('--i686-parts', type=Path, default=ROOT / 'build/tjs1882-2493-native-ci-payload21')
    parser.add_argument('--arm-payload', type=Path, default=ROOT / 'build/tjs1882-8027288d-arm13-native-payload')
    parser.add_argument('--helper-bindings', type=Path, default=ROOT / 'vanguard/windows-test-successor.json')
    args = parser.parse_args()
    args.out.mkdir()
    bundle = args.out / 'meownero-windows-test'
    bundle.mkdir()
    for source, destination in [('windows-test-bundle.py', 'windows-test-bundle.py'),
                                ('windows-test-bundle.cmd', 'RUN-TEST.cmd'), ('WINDOWS-TEST.md', 'READ-ME.md')]:
        shutil.copyfile(ROOT / 'vanguard' / source, bundle / destination)
    manifest = {'schema': 'meownero-windows-test-bundle/1', 'issue': 'TJS-1882',
                'program_status': 'BUILT_UNTESTED', 'bundle_status': 'AWAITING_INDEPENDENT_REVIEW',
                'source_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                'lanes': {}, 'files': {}}
    handoff = json.loads(args.i686_handoff.read_text())
    helper_bindings = json.loads(args.helper_bindings.read_text())
    manifest['helper_bindings'] = helper_bindings
    manifest['helper_bindings_sha256'] = sha(args.helper_bindings)
    for target, name in [('windows-i686', 'i68635'), ('windows-aarch64', 'arm13')]:
        lane = bundle / name
        (lane / 'vanguard').mkdir(parents=True)
        if target == 'windows-i686':
            omitted = {'vanguard/tester-profile.json', 'vanguard/tester.py', 'vanguard/run-portable-mac-check.py'}
            for destination, binding in handoff['source_bindings'].items():
                if not destination.startswith('vanguard/') or destination in omitted:
                    continue
                data = subprocess.check_output(['git', 'show', binding['commit'] + ':' + binding['path']], cwd=ROOT)
                expected = handoff['files'][destination]
                assert len(data) == expected['bytes'] and hashlib.sha256(data).hexdigest() == expected['sha256']
                (lane / destination).write_bytes(data)
            assert sha(lane / 'vanguard/ci-inputs.json') == I686_INPUTS
            # Windows uses the archive's tester. These three host/Mac-only inputs
            # are not called by its Windows branch. Preserve controller bytes,
            # but remove unused host profile data from the distributable.
            adapted = json.loads((lane / 'vanguard/ci-inputs.json').read_text())
            for path in omitted:
                del adapted['source_files'][path]
            (lane / 'vanguard/ci-inputs.json').write_text(json.dumps(adapted, indent=2) + '\n')
            parts_root = args.i686_parts
        else:
            for path in (args.arm_payload / 'vanguard').iterdir():
                if path.is_file():
                    shutil.copyfile(path, lane / 'vanguard' / path.name)
            assert sha(lane / 'vanguard/run-portable-ci.py') == ARM_CONTROLLER
            parts_root = args.arm_payload
        inputs = json.loads((lane / 'vanguard/ci-inputs.json').read_text())
        for path, expected in inputs['source_files'].items():
            assert sha(lane / path) == expected
        row = inputs['targets'][target]
        original_inputs_sha256 = sha(lane / 'vanguard/ci-inputs.json')
        helper_provenance = successor_helpers(lane, inputs, target, helper_bindings)
        archive = bundle / (Path(row['archive_name']).stem + '-sanitized-v1.zip')
        with tempfile.TemporaryDirectory(prefix='tjs1882-original-') as folder:
            original = Path(folder) / row['archive_name']
            with original.open('xb') as stream:
                for part in row['parts']:
                    path = parts_root / part['path']
                    assert path.stat().st_size == part['bytes'] and sha(path) == part['sha256']
                    with path.open('rb') as source:
                        shutil.copyfileobj(source, stream)
            assert original.stat().st_size == row['archive_bytes'] and sha(original) == row['archive_sha256'] == ARCHIVES[target]
            rewrite = successor_archive(original, archive)
        with zipfile.ZipFile(archive) as stream:
            release_bytes = stream.read(row['package_name'] + '/release.json')
            release = json.loads(release_bytes)
        row.update(archive_name=archive.name, archive_bytes=archive.stat().st_size,
                   archive_sha256=sha(archive), release_manifest_sha256=hashlib.sha256(release_bytes).hexdigest())
        if 'native_exception_probe' in row:
            row['native_exception_probe']['files'] = {
                name: release['files'][name] for name in row['native_exception_probe']['files']}
        row['parts'] = []
        with archive.open('rb') as stream:
            while data := stream.read(8 * 1024**2):
                row['parts'].append({'path': 'ci/tjs1882/packages/' + target + '/' + archive.name
                                    + '.part-' + str(len(row['parts']) + 1).zfill(4),
                                    'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
        (lane / 'vanguard/ci-inputs.json').write_text(json.dumps(inputs, indent=2) + '\n')
        manifest['lanes'][target] = {'root': name, 'archive': archive.name,
                                    'inputs_sha256': sha(lane / 'vanguard/ci-inputs.json'),
                                    'pre_successor_inputs_sha256': original_inputs_sha256,
                                    'helper_successor': helper_provenance,
                                    'provenance_rewrite': rewrite}
        if target == 'windows-i686':
            manifest['lanes'][target]['input_adaptation'] = {
                'original_inputs_sha256': I686_INPUTS, 'removed_unused_source_bindings': sorted(omitted),
                'controller': 'HASH_BOUND_DIAGNOSTIC_SUCCESSOR', 'archive': 'SANITIZED_SUCCESSOR',
                'historical_byte_audit_scope': 'UNCHANGED_PROGRAM_BYTES_ONLY'}
    manifest['files'] = {path.relative_to(bundle).as_posix(): sha(path)
                         for path in sorted(bundle.rglob('*')) if path.is_file()}
    (bundle / 'bundle.json').write_text(json.dumps(manifest, indent=2) + '\n')
    # Scan the complete tree recursively before a deliverable ZIP can exist.
    check_bundle(bundle)
    output = args.out / 'meownero-windows-test-sanitized-v1.zip'
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_STORED) as archive:
        for path in sorted(bundle.rglob('*')):
            if path.is_file():
                info = zipfile.ZipInfo(path.relative_to(args.out).as_posix(), date_time=(2026, 10, 29, 0, 0, 0))
                info.create_system = 3
                info.external_attr = (stat.S_IFREG | 0o644) << 16
                archive.writestr(info, path.read_bytes())
    refuse_private_paths(output.read_bytes())
    (args.out / 'SHA256SUMS').write_text(sha(output) + '  ' + output.name + '\n')
    print(json.dumps({'archive': str(output), 'bytes': output.stat().st_size, 'sha256': sha(output)}))


if __name__ == '__main__':
    main()
