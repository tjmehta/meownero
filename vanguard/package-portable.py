#!/usr/bin/env python3
"""Allowlist Linux or Mac testers from their exact locked build receipts."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import portable_licenses
import portable_provenance

ROOT = Path(__file__).resolve().parent.parent
PROGRAMS = ('monerod', 'monero-wallet-cli', 'monero-wallet-rpc')


def sha(path):
    with path.open('rb') as stream:
        h = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
        return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    build, out = args.build.resolve(), args.out.absolute()
    assert out.parent.is_dir() and not out.exists(), 'fresh output required'
    assert not any(p.is_symlink() for p in (out, *out.parents)), 'symlink output refused'
    receipt = json.loads((build / 'build-receipt.json').read_text())
    pin = json.loads((ROOT / 'vanguard/source-lock.json').read_text())
    assert receipt['source_lock'] == pin, 'source lock mismatch'
    mac = receipt['schema'] == 'meownero-native-mac-build/1'
    if mac:
        assert receipt['result'] == 'BUILT_JOURNEY_UNTESTED' and all(c.get('reaped') for c in receipt['commands'])
        release_target = receipt.get('target', 'macos-aarch64')
        arch = {'macos-aarch64': 'aarch64', 'macos-x86_64': 'x86_64'}[release_target]
    else:
        assert receipt['result'] == 'BUILT_VERSION_EXECUTED_JOURNEY_UNTESTED'
        if receipt['schema'] == 'meownero-docker-source-build/1':
            assert receipt['compiler_execution_substrate'] == 'NATIVE' and receipt['offline_compile'] is True
        else:
            assert receipt['cleanup']['removed']
        release_target = receipt['target']
        arch = {'linux-x86_64': 'x86_64', 'linux-aarch64': 'aarch64'}[release_target]
    source = build / 'monero-fcmp'
    out.mkdir(mode=0o700)
    package = out / ('meownero-vanguard-' + ('macos-' if mac else '') + arch)
    package.mkdir()
    (package / 'bin').mkdir()
    links, versions = set(), set()
    signing_states = {}
    for name in PROGRAMS:
        binary = source / ('build/portable/bin' if mac else 'build/vanguard/bin') / name
        assert binary.is_file() and not binary.is_symlink() and binary.stat().st_nlink == 1
        assert sha(binary) == (receipt['binaries'][name] if mac else receipt['binaries'][name]['sha256']), 'binary pin mismatch'
        data = binary.read_bytes()[:20]
        if mac:
            assert data[:4] == b'\xcf\xfa\xed\xfe' and int.from_bytes(data[4:8], 'little') == {'aarch64': 0x100000c, 'x86_64': 0x1000007}[arch]
            assert int.from_bytes(data[12:16], 'little') == 2
            dynamic = subprocess.check_output(['otool', '-L', str(binary)], text=True)
            links.update(line.strip().split(' (')[0] for line in dynamic.splitlines()[1:])
            assert all(link.startswith(('/usr/lib/', '/System/Library/Frameworks/')) for link in links), 'non-system native library requires bundling'
            version = subprocess.check_output(['vtool', '-show-build', str(binary)], text=True)
            minimum = re.search(r'\bminos\s+(\d+\.\d+(?:\.\d+)?)', version)
            assert minimum, 'missing Mach-O minimum OS'
            versions.add(minimum[1])
            signed = subprocess.run(['codesign', '-dv', str(binary)], capture_output=True, text=True)
            if signed.returncode == 0:
                assert 'Signature=adhoc' in signed.stderr, 'unexpected signing identity'
                subprocess.run(['codesign', '--verify', '--strict', str(binary)], check=True)
                signing_states[name] = 'ad hoc linker signature; no Developer ID'
            else:
                assert arch == 'x86_64' and 'not signed at all' in signed.stderr, 'unverified signing state'
                signing_states[name] = 'unsigned'
            if arch == 'aarch64':
                subprocess.run([str(binary), '--version'], check=True, capture_output=True, timeout=20)
        else:
            assert data[:6] == b'\x7fELF\x02\x01' and int.from_bytes(data[18:20], 'little') == {'x86_64': 62, 'aarch64': 183}[arch]
            dynamic = subprocess.check_output(['readelf', '-d', str(binary)], text=True)
            version = subprocess.check_output(['readelf', '--version-info', str(binary)], text=True)
            links.update(re.findall(r'\(NEEDED\).*\[(.*?)\]', dynamic))
            versions.update(re.findall(r'GLIBC_(\d+\.\d+)', version))
        shutil.copyfile(binary, package / 'bin' / name)
        (package / 'bin' / name).chmod(0o755)
    (package / 'lib').mkdir()
    for library in ([] if mac else sorted((build / 'runtime-libs').iterdir())):
        assert library.is_file() and not library.is_symlink() and library.stat().st_nlink == 1
        shutil.copyfile(library, package / 'lib' / library.name)
        version = subprocess.check_output(['readelf', '--version-info', str(library)], text=True)
        versions.update(re.findall(r'GLIBC_(\d+\.\d+)', version))
        dynamic = subprocess.check_output(['readelf', '-d', str(library)], text=True)
        links.update(re.findall(r'\(NEEDED\).*\[(.*?)\]', dynamic))
    system = {'libc.so.6', 'libm.so.6', 'libdl.so.2', 'libpthread.so.0', 'librt.so.1',
              'ld-linux-x86-64.so.2', 'ld-linux-aarch64.so.1'}
    bundled = {p.name for p in (package / 'lib').iterdir()}
    assert mac or links <= system | bundled, 'unbundled dependency: ' + str(links - system - bundled)
    shutil.copyfile(ROOT / 'vanguard/portable-tester.py', package / 'tester.py')
    shutil.copyfile(ROOT / 'docs/vanguard-portable-tester.md', package / 'TESTER.md')
    shutil.copyfile(ROOT / 'vanguard/source-lock.json', package / 'source-lock.json')
    (package / 'launch.sh').write_text('#!/bin/sh\nset -eu\ncd "$(dirname "$0")"\nexec python3 -B ./tester.py "$@"\n')
    (package / 'launch.sh').chmod(0o755)
    # Known license filenames only. No cache, home directory, wallet or database.
    licenses = package / 'licenses'
    licenses.mkdir()
    for tree, prefix in [(source, 'upstream'), (build / 'cargo-home/git/checkouts', 'rust-git'),
                         (build / 'cargo-home/registry/src', 'rust-registry'), (build / 'licenses', 'system'),
                         (build / 'rust/share/doc/rust', 'rust-toolchain')]:
        if not tree.exists():
            continue
        for path in tree.rglob('*'):
            if any(part in {'build', '.git', 'target'} for part in path.relative_to(tree).parts):
                continue
            if path.name.upper().startswith(('LICENSE', 'COPYING', 'COPYRIGHT')) and path.is_file():
                assert not path.is_symlink(), 'license symlink refused'
                target = licenses / prefix / path.relative_to(tree)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
    coverage = portable_licenses.coverage(build, package, mac, bundled,
                                         depends_static=receipt.get('depends_static_dependencies', False))
    (package / 'license-coverage.json').write_text(json.dumps(coverage, indent=2) + '\n')
    minimum = max(versions, key=lambda v: tuple(map(int, v.split('.'))))
    manifest = {'schema': 'meownero-portable-release/1', 'target': release_target, 'system': 'Darwin' if mac else 'Linux',
        'architecture': arch, 'binary_format': 'Mach-O64 little endian' if mac else 'ELF64 little endian', 'upstream_commit': pin['upstream']['commit'],
        'cargo_lock_sha256': pin['rust']['cargo_lock_sha256'], 'submodules': pin['upstream']['submodules'],
        'patches': receipt.get('patches', []), 'rustc': pin['builder']['rustc'], 'builder_image': receipt.get('builder_image'),
        'required_dynamic_libraries': sorted(links), 'bundled_libraries': sorted(bundled),
        'cpu_requirement': ('Apple Silicon' if arch == 'aarch64' else 'Intel x86-64 Mac; Rosetta translation is separate evidence') if mac else ('ARMv8-A with cryptography extension' if arch == 'aarch64' else 'x86-64'),
        'minimum_os': ('macOS ' if mac else 'Linux with glibc ') + minimum + ' or later; older versions remain untested',
        'status': 'BUILT_UNTESTED', 'native_version_execution': 'UNTESTED' if mac and arch == 'x86_64' else 'builder only', 'native_journey': 'UNTESTED',
        'signing': 'ad hoc linker signature; no Developer ID' if mac and all(s.startswith('ad hoc') for s in signing_states.values()) else 'unsigned', 'notarization': 'not notarized' if mac else 'not applicable',
        'license_coverage': {'file': 'license-coverage.json', 'sha256': sha(package / 'license-coverage.json'),
                             'result': coverage['result']},
        'dependency_links': {'source': pin['upstream']['url'], 'rust': 'https://www.rust-lang.org/',
            'boost': 'https://www.boost.org/', 'openssl': 'https://www.openssl.org/',
            'libsodium': 'https://libsodium.org/', 'unbound': 'https://nlnetlabs.nl/projects/unbound/',
            'zeromq': 'https://zeromq.org/'},
        'files': {str(p.relative_to(package)): sha(p) for p in sorted(package.rglob('*')) if p.is_file()}}
    manifest['minimum_macos' if mac else 'minimum_glibc'] = minimum
    if receipt.get('compiler_execution_substrate') == 'PREEXISTING_QEMU_AMD64_ON_COLIMA_ARM64':
        manifest['compiler_execution_substrate'] = receipt['compiler_execution_substrate']
        manifest['native_version_execution'] = 'UNTESTED'
        manifest['translated_builder_version_execution'] = 'PASS; genuine native journey remains UNTESTED'
    if mac:
        manifest['sdk_version'] = receipt['sdk_version']
        manifest['program_signing'] = signing_states
    (package / 'release.json').write_text(json.dumps(manifest, indent=2) + '\n')
    for path in sorted(package.rglob('*')):
        portable_provenance.refuse_private_paths(str(path.relative_to(package)).encode())
        if path.is_file():
            portable_provenance.refuse_private_paths(path.read_bytes())
    archive = out / (package.name + '.tar.gz')
    def public_owner(info):
        info.uid = info.gid = 0
        info.uname = info.gname = ''
        return info
    with tarfile.open(archive, 'w:gz') as stream:
        for path in sorted(package.rglob('*')):
            assert not path.is_symlink(), 'package symlink refused'
            if path.is_file():
                stream.add(path, arcname=str(Path(package.name) / path.relative_to(package)), recursive=False,
                           filter=public_owner)
    portable_provenance.refuse_private_paths(archive.read_bytes())
    (out / 'SHA256SUMS').write_text(sha(archive) + '  ' + archive.name + '\n')
    print('BUILT_UNTESTED', sha(archive), archive.name)


if __name__ == '__main__':
    main()
