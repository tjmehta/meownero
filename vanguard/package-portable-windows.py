#!/usr/bin/env python3
"""Package actual cross-built PE programs; keep every Windows journey UNTESTED."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import zipfile
import portable_licenses

ROOT = Path(__file__).resolve().parent.parent
PROGRAMS = ('monerod', 'monero-wallet-cli', 'monero-wallet-rpc')
MACHINES = {'windows-i686': (0x14c, 0x10b, 'i686'), 'windows-x86_64': (0x8664, 0x20b, 'x86_64'), 'windows-aarch64': (0xaa64, 0x20b, 'aarch64')}
SYSTEM_DLLS = {'kernel32.dll', 'advapi32.dll', 'bcrypt.dll', 'crypt32.dll', 'dbghelp.dll',
               'dnsapi.dll', 'iphlpapi.dll', 'msvcrt.dll', 'ntdll.dll', 'ole32.dll', 'oleaut32.dll',
               'rpcrt4.dll', 'secur32.dll', 'shell32.dll', 'shlwapi.dll', 'user32.dll', 'userenv.dll',
               'version.dll', 'winhttp.dll', 'ws2_32.dll', 'ucrtbase.dll', 'mswsock.dll', 'bcryptprimitives.dll'}


def sha(path):
    assert path.is_file() and not path.is_symlink() and path.stat().st_nlink == 1, 'unsafe package input'
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--objdump', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    build, out = args.build.resolve(), args.out.absolute()
    assert out.parent.is_dir() and not out.exists() and not any(p.is_symlink() for p in (out, *out.parents))
    receipt = json.loads((build / 'build-receipt.json').read_text())
    pin = json.loads((ROOT / 'vanguard/source-lock.json').read_text())
    assert receipt['source_lock'] == pin and receipt['schema'] == 'meownero-windows-cross-build/1'
    assert receipt['result'] == 'BUILT_UNTESTED' and receipt['containers'] and all(c['removed'] for c in receipt['containers'])
    machine, optional, arch = MACHINES[receipt['target']]
    out.mkdir(mode=0o700)
    package = out / ('meownero-vanguard-windows-' + arch)
    package.mkdir()
    binary_dir = package / 'bin'
    binary_dir.mkdir()
    audit, required = {}, set()

    def inspect(path):
        with path.open('rb') as stream:
            assert stream.read(2) == b'MZ', 'DOS header missing'
            stream.seek(60)
            offset = int.from_bytes(stream.read(4), 'little')
            stream.seek(offset)
            header = stream.read(26)
        assert header[:4] == b'PE\0\0' and int.from_bytes(header[4:6], 'little') == machine and int.from_bytes(header[24:26], 'little') == optional, 'PE architecture mismatch'
        text = subprocess.check_output([str(args.objdump), '-p', str(path)], text=True, timeout=30)
        security = re.search(r'Entry 4\s+([0-9a-fA-F]+)\s+([0-9a-fA-F]+)', text)
        assert security and int(security[1], 16) == 0 and int(security[2], 16) == 0, 'unexpected PE signing state'
        delayed = re.search(r'Entry d\s+([0-9a-fA-F]+)\s+([0-9a-fA-F]+)', text, re.I)
        assert delayed and int(delayed[1], 16) == 0 and int(delayed[2], 16) == 0, 'unmapped delayed-import dependency'
        imports = set(re.findall(r'DLL Name:\s+(\S+)', text))
        assert imports and not re.search(r'Delay Import.*(?:corrupt|invalid)', text, re.I), 'missing or invalid import inventory'
        audit[path.name] = {'sha256': sha(path), 'machine': machine, 'imports': sorted(imports),
                            'objdump_sha256': hashlib.sha256(text.encode()).hexdigest()}
        required.update(name.lower() for name in imports)

    for name in PROGRAMS:
        source = build / 'monero-fcmp/build/portable/bin' / (name + '.exe')
        assert sha(source) == receipt['binaries'][name]['sha256'], 'built program hash mismatch'
        shutil.copyfile(source, binary_dir / source.name)
        inspect(binary_dir / source.name)
    if receipt.get('abi_helper_sha256'):
        probe = receipt.get('exception_probe')
        assert probe, 'required i686 exception cross-probe missing'
        assert receipt['target'] == 'windows-i686' and probe['native_execution'] == 'UNTESTED'
        assert probe['file'] == 'i686-exception-probe.exe' and sha(build / probe['file']) == probe['sha256'], 'exception probe hash mismatch'
        assert sha(build / 'i686-exception-probe.cpp') == probe['source_sha256'], 'exception fixture hash mismatch'
        shutil.copyfile(build / probe['file'], binary_dir / probe['file'])
        inspect(binary_dir / probe['file'])
    candidates = {}
    for prefix in (build / 'toolchain', build / 'llvm'):
        for path in prefix.rglob('*.dll'):
            if path.is_file() and not path.is_symlink():
                candidates.setdefault(path.name.lower(), []).append(path)
    bundled = set()
    while True:
        missing = required - SYSTEM_DLLS - bundled
        # API-set imports are supplied by Windows 10+, not redistributable DLLs.
        missing = {name for name in missing if not name.startswith(('api-ms-win-', 'ext-ms-win-'))}
        if not missing:
            break
        for name in sorted(missing):
            matches = []
            for path in candidates.get(name, []):
                with path.open('rb') as stream:
                    stream.seek(60)
                    offset = int.from_bytes(stream.read(4), 'little')
                    stream.seek(offset + 4)
                    if int.from_bytes(stream.read(2), 'little') == machine:
                        matches.append(path)
            assert matches and len({sha(path) for path in matches}) == 1, 'missing or ambiguous same-target DLL: ' + name
            shutil.copyfile(matches[0], binary_dir / name)
            inspect(binary_dir / name)
            bundled.add(name)
    crt_imports = sorted(name for name in required if name in {'msvcrt.dll', 'ucrtbase.dll'} or name.startswith('api-ms-win-crt-'))
    if receipt['target'] == 'windows-aarch64':
        assert crt_imports and 'msvcrt.dll' not in crt_imports, 'ARM64 requires the pinned UCRT closure'
    else:
        assert crt_imports == ['msvcrt.dll'], 'GNU target requires the pinned MSVCRT closure'
    for source, target in [('vanguard/portable-tester.py', 'tester.py'), ('vanguard/portable_windows.py', 'portable_windows.py'), ('docs/vanguard-portable-tester.md', 'TESTER.md'), ('vanguard/source-lock.json', 'source-lock.json')]:
        shutil.copyfile(ROOT / source, package / target)
    shutil.copyfile(build / 'build-receipt.json', package / 'BUILD.json')
    shutil.copyfile(build / 'compiler.txt', package / 'COMPILER.txt')
    if receipt.get('abi_helper_sha256'):
        assert receipt['target'] == 'windows-i686', 'unexpected ABI adaptation target'
        assert sha(build / 'i686-unwind.py') == receipt['abi_helper_sha256'], 'ABI helper hash mismatch'
        assert sha(build / 'cached-build-receipt.json') == receipt['cached_build']['receipt_sha256'], 'cached provenance hash mismatch'
        adaptation = json.loads((build / 'i686-unwind-adaptation.json').read_text())
        assert adaptation['archive_before_sha256'] == 'a936650965fda87e81acd6e4319fea4a362d606d1251fe2f8ce6a4442382e547', 'ABI input differs from the retained exact probe'
        assert adaptation['all_other_archive_bytes_unchanged'] and adaptation['before'] == 2 and adaptation['after'] == 105
        assert sha(build / 'monero-fcmp/build/portable/src/fcmp_pp/fcmp_pp_rust/libfcmp_pp_rust.a') == adaptation['archive_after_sha256'], 'adapted Rust archive changed'
        assert any(p.get('receipt_sha256') == sha(build / 'i686-unwind-adaptation.json') for p in receipt['patches']), 'missing ABI proof binding'
        evidence = package / 'build-evidence'
        evidence.mkdir()
        names = ['i686-unwind.py', 'i686-unwind-adaptation.json', 'cached-build-receipt.json', 'i686-exception-probe.cpp', 'i686-exception-probe.map']
        names += [program + suffix for program in PROGRAMS for suffix in ('.map', '.symbols')]
        for name in names:
            shutil.copyfile(build / name, evidence / name)
    (package / 'launch.cmd').write_text('@echo off\r\ncd /d "%~dp0"\r\npy -3 -B tester.py %*\r\nexit /b %errorlevel%\r\n')
    licenses = package / 'licenses'
    licenses.mkdir()
    for tree, prefix in [(build / 'monero-fcmp', 'upstream'), (build / 'cargo-home/git/checkouts', 'rust-git'),
                         (build / 'cargo-home/registry/src', 'rust-registry'), (build / 'licenses', 'system'),
                         (build / 'rust/share/doc/rust', 'rust-toolchain')]:
        if tree.exists():
            for path in tree.rglob('*'):
                if any(part in {'build', '.git', 'target'} for part in path.relative_to(tree).parts):
                    continue
                if path.is_file() and path.name.upper().startswith(('LICENSE', 'COPYING', 'COPYRIGHT')):
                    target = licenses / prefix / path.relative_to(tree)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(path, target)
    coverage = portable_licenses.coverage(build, package, True, (), windows=True)
    # Conservatively retain every signed Ubuntu toolchain package notice, or the
    # exact LLVM distribution notice tree. No unknown runtime is silently ignored.
    if receipt['target'] != 'windows-aarch64':
        packages = []
        for deb in sorted((build / 'downloads').glob('*.deb')):
            name, version = deb.name.split('_')[:2]
            copyright = build / 'toolchain/usr/share/doc' / name / 'copyright'
            assert copyright.exists(), 'missing toolchain notice: ' + name
            target = licenses / 'toolchain' / (name + '-copyright')
            target.parent.mkdir(exist_ok=True)
            shutil.copyfile(copyright, target)
            texts = {str(target.relative_to(package)): sha(target)}
            for license_name in sorted(set(re.findall(r'/usr/share/common-licenses/([A-Za-z0-9.-]+)', target.read_text()))):
                license_name = license_name.rstrip('.')
                full = Path('/usr/share/common-licenses') / license_name
                assert full.is_file(), 'missing toolchain full license text: ' + license_name
                dest = licenses / 'toolchain' / ('COPYING-common-' + license_name)
                shutil.copyfile(full, dest)
                texts[str(dest.relative_to(package))] = sha(dest)
            packages.append({'component': name, 'version': version, 'source': 'signed Ubuntu noble package indices retained in build/apt-lists', 'source_archive_sha256': sha(deb), 'texts': texts})
        assert packages, 'missing signed toolchain package coverage'
        coverage['components'].extend(packages)
    else:
        texts = {}
        for path in (build / 'llvm').rglob('*'):
            if path.is_file() and path.name.upper().startswith(('LICENSE', 'COPYING', 'COPYRIGHT')):
                target = licenses / 'llvm-mingw' / path.relative_to(build / 'llvm')
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
                texts[str(target.relative_to(package))] = sha(target)
        assert texts, 'missing LLVM/CRT toolchain notices'
        coverage['components'].append({'component': 'LLVM-MinGW UCRT', 'version': '20261006', 'source_archive_sha256': sha(build / 'downloads/llvm.tar.xz'), 'texts': texts})
    (package / 'license-coverage.json').write_text(json.dumps(coverage, indent=2) + '\n')
    manifest = {'schema': 'meownero-portable-release/1', 'target': receipt['target'], 'system': 'Windows', 'architecture': arch,
        'binary_format': 'PE32' if arch == 'i686' else 'PE32+', 'minimum_os': 'Windows 10 version 1709 or later; native execution UNTESTED',
        'upstream_commit': pin['upstream']['commit'], 'cargo_lock_sha256': pin['rust']['cargo_lock_sha256'],
        'submodules': pin['upstream']['submodules'], 'rustc': pin['builder']['rustc'], 'patches': receipt['patches'],
        'signing': 'unsigned; no Authenticode credential used', 'notarization': 'not applicable', 'status': 'BUILT_UNTESTED',
        'c_runtime': 'UCRT' if receipt['target'] == 'windows-aarch64' else 'MSVCRT with static POSIX MinGW runtimes',
        'c_runtime_imports': crt_imports,
        'compiler_inventory': {'file': 'COMPILER.txt', 'sha256': sha(package / 'COMPILER.txt')},
        'native_version_execution': 'UNTESTED', 'native_journey': 'UNTESTED', 'python_requirement': 'CPython 3.13 or later',
        'bundled_libraries': sorted(bundled), 'required_dynamic_libraries': sorted(required), 'pe_audit': audit,
        'build_receipt': {'file': 'BUILD.json', 'sha256': sha(package / 'BUILD.json')},
        'license_coverage': {'file': 'license-coverage.json', 'sha256': sha(package / 'license-coverage.json'), 'result': coverage['result']},
        'files': {str(path.relative_to(package)): sha(path) for path in sorted(package.rglob('*')) if path.is_file()}}
    if receipt.get('exception_probe'):
        manifest['native_exception_probe'] = {'file': 'bin/i686-exception-probe.exe', 'native_execution': 'UNTESTED', 'required_for_native_acceptance': True}
    if receipt.get('compiler_execution_substrate') == 'PREEXISTING_QEMU_AMD64_ON_COLIMA_ARM64':
        manifest['compiler_execution_substrate'] = receipt['compiler_execution_substrate']
    (package / 'release.json').write_text(json.dumps(manifest, indent=2) + '\n')
    archive = out / (package.name + '.zip')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as stream:
        for path in sorted(package.rglob('*')):
            if path.is_file():
                stream.write(path, str(Path(package.name) / path.relative_to(package)))
    (out / 'SHA256SUMS').write_text(sha(archive) + '  ' + archive.name + '\n')
    print('BUILT_UNTESTED', sha(archive), archive.name)


if __name__ == '__main__':
    main()
