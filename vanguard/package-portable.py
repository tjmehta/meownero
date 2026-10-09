#!/usr/bin/env python3
"""Allowlist a Linux tester archive from a successful locked build receipt."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile

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
    assert receipt['result'] == 'BUILT_VERSION_EXECUTED_JOURNEY_UNTESTED' and receipt['cleanup']['removed']
    arch = {'linux-x86_64': 'x86_64', 'linux-aarch64': 'aarch64'}[receipt['target']]
    source = build / 'monero-fcmp'
    out.mkdir(mode=0o700)
    package = out / ('meownero-vanguard-' + arch)
    package.mkdir()
    (package / 'bin').mkdir()
    links, versions = set(), set()
    for name in PROGRAMS:
        binary = source / 'build/vanguard/bin' / name
        assert binary.is_file() and not binary.is_symlink() and binary.stat().st_nlink == 1
        assert sha(binary) == receipt['binaries'][name]['sha256'], 'binary pin mismatch'
        data = binary.read_bytes()[:20]
        assert data[:6] == b'\x7fELF\x02\x01' and int.from_bytes(data[18:20], 'little') == {'x86_64': 62, 'aarch64': 183}[arch]
        dynamic = subprocess.check_output(['readelf', '-d', str(binary)], text=True)
        version = subprocess.check_output(['readelf', '--version-info', str(binary)], text=True)
        links.update(re.findall(r'\(NEEDED\).*\[(.*?)\]', dynamic))
        versions.update(re.findall(r'GLIBC_(\d+\.\d+)', version))
        shutil.copyfile(binary, package / 'bin' / name)
        (package / 'bin' / name).chmod(0o755)
    (package / 'lib').mkdir()
    for library in sorted((build / 'runtime-libs').iterdir()):
        assert library.is_file() and not library.is_symlink() and library.stat().st_nlink == 1
        shutil.copyfile(library, package / 'lib' / library.name)
        version = subprocess.check_output(['readelf', '--version-info', str(library)], text=True)
        versions.update(re.findall(r'GLIBC_(\d+\.\d+)', version))
        dynamic = subprocess.check_output(['readelf', '-d', str(library)], text=True)
        links.update(re.findall(r'\(NEEDED\).*\[(.*?)\]', dynamic))
    system = {'libc.so.6', 'libm.so.6', 'libdl.so.2', 'libpthread.so.0', 'librt.so.1',
              'ld-linux-x86-64.so.2', 'ld-linux-aarch64.so.1'}
    bundled = {p.name for p in (package / 'lib').iterdir()}
    assert links <= system | bundled, 'unbundled dependency: ' + str(links - system - bundled)
    shutil.copyfile(ROOT / 'vanguard/portable-tester.py', package / 'tester.py')
    shutil.copyfile(ROOT / 'docs/vanguard-portable-tester.md', package / 'TESTER.md')
    shutil.copyfile(ROOT / 'vanguard/source-lock.json', package / 'source-lock.json')
    (package / 'launch.sh').write_text('#!/bin/sh\nset -eu\ncd "$(dirname "$0")"\nexec python3 -B ./tester.py "$@"\n')
    (package / 'launch.sh').chmod(0o755)
    # Known license filenames only. No cache, home directory, wallet or database.
    licenses = package / 'licenses'
    licenses.mkdir()
    for tree, prefix in [(source, 'upstream'), (build / 'cargo-home/git/checkouts', 'rust-git'),
                         (build / 'cargo-home/registry/src', 'rust-registry'), (build / 'licenses', 'system')]:
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
    minimum = max(versions, key=lambda v: tuple(map(int, v.split('.'))))
    manifest = {'schema': 'meownero-portable-release/1', 'target': receipt['target'], 'system': 'Linux',
        'architecture': arch, 'binary_format': 'ELF64 little endian', 'upstream_commit': pin['upstream']['commit'],
        'cargo_lock_sha256': pin['rust']['cargo_lock_sha256'], 'submodules': pin['upstream']['submodules'],
        'patches': receipt['patches'], 'rustc': pin['builder']['rustc'], 'builder_image': receipt['builder_image'],
        'minimum_glibc': minimum, 'required_dynamic_libraries': sorted(links), 'bundled_libraries': sorted(bundled),
        'cpu_requirement': 'ARMv8-A with cryptography extension' if arch == 'aarch64' else 'x86-64',
        'minimum_os': 'Linux with glibc ' + minimum + ' or later; distro journeys still untested',
        'status': 'BUILT_UNTESTED', 'native_version_execution': 'builder only', 'native_journey': 'UNTESTED',
        'signing': 'unsigned', 'notarization': 'not applicable',
        'dependency_links': {'source': pin['upstream']['url'], 'rust': 'https://www.rust-lang.org/',
            'boost': 'https://www.boost.org/', 'openssl': 'https://www.openssl.org/',
            'libsodium': 'https://libsodium.org/', 'unbound': 'https://nlnetlabs.nl/projects/unbound/',
            'zeromq': 'https://zeromq.org/'},
        'files': {str(p.relative_to(package)): sha(p) for p in sorted(package.rglob('*')) if p.is_file()}}
    (package / 'release.json').write_text(json.dumps(manifest, indent=2) + '\n')
    archive = out / (package.name + '.tar.gz')
    with tarfile.open(archive, 'w:gz') as stream:
        for path in sorted(package.rglob('*')):
            assert not path.is_symlink(), 'package symlink refused'
            if path.is_file():
                stream.add(path, arcname=str(Path(package.name) / path.relative_to(package)), recursive=False)
    (out / 'SHA256SUMS').write_text(sha(archive) + '  ' + archive.name + '\n')
    print('BUILT_UNTESTED', sha(archive), archive.name)


if __name__ == '__main__':
    main()
