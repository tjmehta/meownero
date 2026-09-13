#!/usr/bin/env python3
"""Read-only verification/collection of the completed historical clean15 pair."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

IMAGE = 'sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e'
FROZEN = '6f74c265453e138cea3b3936542ef410ff3f0396ae561a8aa9a9f3eae7c3518e'
HEAD = '7410c04bab0e304112710d63c3225c110bd8b4de'
TREE = '4db958cb96d72943c5c2433bd5f4a8f730037148'
RECEIPTS = ('BUILDER_IMAGE_ID', 'packages.txt', 'SHA256SUMS', 'SOURCE_REVISIONS',
            'SUBMODULES', 'INPUT_SHA256SUMS', 'VERSIONS')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    if path.is_symlink():
        return hashlib.sha256(os.readlink(path).encode()).hexdigest()
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def command(*args):
    return subprocess.check_output(args, text=True, env=dict(os.environ, GIT_OPTIONAL_LOCKS='0'))


def read_manifest(path):
    rows = {}
    for line in path.read_text().splitlines():
        h, name = line.split('  ', 1)
        require(re.fullmatch('[0-9a-f]{64}', h) and not Path(name).is_absolute()
                and '..' not in Path(name).parts and name not in rows, 'invalid manifest: ' + str(path))
        rows[name] = h
    return rows


def verify_manifest(root, rows):
    for name, expected in rows.items():
        require(digest(root / name) == expected, 'hash mismatch: ' + str(root / name))


def verify_run(run, expected):
    """Also used before incremental copies; expected is a collected receipt directory."""
    for name in RECEIPTS:
        require((run / name).read_bytes() == (expected / name).read_bytes(), 'receipt mismatch: ' + name)
    require((run / 'BUILDER_IMAGE_ID').read_text().strip() == IMAGE, 'builder mismatch')
    src = run / 'monero'
    require(command('git', '-C', str(src), 'rev-parse', 'HEAD', 'HEAD^{tree}').splitlines()
            == [HEAD, TREE], 'source revision mismatch')
    require(not command('git', '-C', str(src), 'status', '--porcelain', '--untracked-files=no'), 'dirty source')
    require(command('git', '-C', str(src), 'submodule', 'status', '--recursive')
            == (run / 'SUBMODULES').read_text(), 'submodule mismatch')
    require(all(line.startswith(' ') for line in (run / 'SUBMODULES').read_text().splitlines()), 'uninitialized submodule')
    verify_manifest(src / 'build/release/bin', read_manifest(run / 'SHA256SUMS'))
    if (expected / 'source-files.sha256').exists():
        verify_manifest(src, read_manifest(expected / 'source-files.sha256'))
        verify_manifest(src, read_manifest(expected / 'build-files.sha256'))
    return src


def collect(base, out):
    require(not any(out.iterdir()), 'evidence output must be empty')
    frozen = base / 'frozen-inputs-15'
    require(digest(frozen / 'SHA256SUMS') == FROZEN, 'frozen manifest mismatch')
    verify_manifest(frozen, read_manifest(frozen / 'SHA256SUMS'))
    require((base / 'resume-once/reproduction.exit').read_text().strip() == '0', 'reproduction did not pass')
    require('PASS: independent source builds match in the recorded builder image.' in
            (base / 'resume-once/reproduction.log').read_text(), 'missing comparison success')
    first = base / 'reproduction/first'
    packages = command('dpkg-query', '-W', '-f=${binary:Package}=${Version}\n')
    require(packages == (first / 'packages.txt').read_text(), 'live builder packages mismatch')
    summary = dict(status='PASS_SAME_IMAGE_CLEAN15', profile='historical-0.9-120',
                   builder_image=IMAGE, frozen_manifest_sha256=FROZEN, runs={})
    for name in ('first', 'second'):
        run = base / 'reproduction' / name
        src = verify_run(run, first)
        verify_manifest(frozen / 'chain', read_manifest(run / 'INPUT_SHA256SUMS'))
        wanted = {'upstream.lock', *(str(p.relative_to(frozen / 'chain')) for p in (frozen / 'chain/patches').glob('*.patch'))}
        require(set(read_manifest(run / 'INPUT_SHA256SUMS')) == wanted and len(wanted) == 16, 'not exact fifteen-patch input set')
        versions = command('c++', '--version') + command('cmake', '--version')
        for binary in ('monerod', 'monero-wallet-cli', 'monero-wallet-rpc'):
            versions += command(str(src / 'build/release/bin' / binary), '--version')
        require(versions == (run / 'VERSIONS').read_text(), 'live version mismatch')
        log = (base / 'reproduction' / (name + '.log')).read_text()
        passed = [int(n) for n in re.findall(r'\[  PASSED  \] (\d+) tests\.', log)]
        require(passed == [24, 10, 10] and '[  FAILED  ]' not in log, 'unexpected test receipt')
        require('PASS: explicit RPC update modes fail closed' in log and
                'PASS: donate is disabled on all three networks' in log, 'authority tests missing')
        dest = out / name
        dest.mkdir()
        for receipt in RECEIPTS:
            shutil.copyfile(run / receipt, dest / receipt)
        shutil.copyfile(base / 'reproduction' / (name + '.log'), dest / 'build-and-tests.log')
        for file in ('cmake.log', 'make.log', 'CMakeCache.txt'):
            shutil.copyfile(src / 'build/release' / file, dest / file)
        files = command('git', '-C', str(src), 'ls-files', '--recurse-submodules', '-z').split('\0')
        (dest / 'source-files.sha256').write_text(''.join(f'{digest(src / p)}  {p}\n' for p in sorted(files) if p))
        build_files = sorted(p for p in (src / 'build').rglob('*') if p.is_file() or p.is_symlink())
        (dest / 'build-files.sha256').write_text(''.join(f'{digest(p)}  {p.relative_to(src)}\n' for p in build_files))
        summary['runs'][name] = dict(receipts_match=True, actual_binaries=read_manifest(run / 'SHA256SUMS'),
            actual_source_head=HEAD, actual_source_tree=TREE, actual_versions_match=True,
            logged_test_pass_counts=passed, authority_checks_passed=True,
            tracked_files=len([p for p in files if p]), build_files=len(build_files),
            test_binary_sha256={p: digest(src / 'build/release/tests/unit_tests' / p)
                               for p in ('unit_tests', 'meow_difficulty_floor_tests')})
    require((out / 'first/source-files.sha256').read_bytes() == (out / 'second/source-files.sha256').read_bytes(), 'tracked source bytes differ')
    require(summary['runs']['first']['test_binary_sha256'] == summary['runs']['second']['test_binary_sha256'], 'test executable hashes differ')
    for name in ('SHA256SUMS',):
        shutil.copyfile(frozen / name, out / ('frozen-' + name))
    for name in ('reproduction.exit', 'reproduction.log', 'run.sh'):
        shutil.copyfile(base / 'resume-once' / name, out / name)
    summary['limits'] = ['same immutable image/host; no independent toolchain reconstruction',
                         'logged build-time test selection, not a newly executed full unit suite',
                         'historical issuance only; no selected binary/capacity/FCMP claim',
                         'build-file hashes are collection-time inventory, not original signed build attestations']
    (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    collect(args.run_root, args.output)
