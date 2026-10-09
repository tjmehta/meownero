#!/usr/bin/env python3
"""Exercise omitted notices, unmapped libraries and corrupted depends inputs."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import portable_licenses as licenses


def refused(action, expected):
    try:
        action()
    except (AssertionError, FileNotFoundError) as error:
        assert expected in str(error), str(error)
    else:
        raise AssertionError('missing license input was accepted')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--package', type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((args.package / 'release.json').read_text())
    assert manifest['system'] == 'Linux'
    with tempfile.TemporaryDirectory(prefix='tjs1882-license-controls-') as tmp:
        package = Path(tmp) / 'package'
        shutil.copytree(args.package / 'licenses', package / 'licenses')
        check = lambda bundled=manifest['bundled_libraries']: licenses.coverage(args.build, package, False, bundled)
        assert check()['result'] == 'PASS_LINKED_DEPENDENCY_COVERAGE'
        for name in ['COPYRIGHT-libssl3t64', 'COPYING-common-LGPL-2.1']:
            path = package / 'licenses/system' / name
            data = path.read_bytes()
            path.unlink()
            refused(check, name)
            path.write_bytes(data)
        refused(lambda: check(manifest['bundled_libraries'] + ['lib-new-unmapped.so.1']), 'unmapped shipped dependency')
        bad = Path(tmp) / 'bad-build'
        depends = bad / 'monero-fcmp/contrib/depends'
        (depends / 'packages').mkdir(parents=True)
        (depends / 'sources').mkdir()
        recipe = args.build / 'monero-fcmp/contrib/depends/packages/boost.mk'
        shutil.copyfile(recipe, depends / 'packages/boost.mk')
        (depends / 'sources/boost-1.91.0-1-b2-nodocs.tar.gz').write_bytes(b'corrupt archive')
        refused(lambda: licenses.retain_depends(bad), 'depends source checksum mismatch')

        # Cover notice loss even when another license for that crate survives.
        for prefix in ['rust-registry', 'rust-git']:
            tree = package / 'licenses' / prefix
            moved = package / (prefix + '-saved')
            tree.rename(moved)
            refused(check, 'missing Rust notice tree')
            moved.rename(tree)
        notice = next((package / 'licenses/rust-registry').rglob('LICENSE-MIT'))
        data = notice.read_bytes()
        notice.unlink()
        refused(check, str(notice))
        notice.write_bytes(data)

        # Exercise the real archive-producing command on an owned minimal build.
        # The source binaries stay byte-preserved; no mutation of retained caches.
        build = Path(tmp) / 'build'
        source = build / 'monero-fcmp'
        source.mkdir(parents=True)
        for rel in manifest['files']:
            if rel.startswith('licenses/upstream/'):
                relative = Path(rel).relative_to('licenses/upstream')
                original = args.build / 'monero-fcmp' / relative
                if original.is_file():
                    dest = source / relative
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(original, dest)
        for relative in ['external/easylogging++/easylogging++.h', 'external/qrcodegen/QrCode.hpp',
                         'src/fcmp_pp/fcmp_pp_rust/Cargo.lock']:
            dest = source / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(args.build / 'monero-fcmp' / relative, dest)
        for link in (args.build / 'monero-fcmp/build/vanguard').rglob('link.txt'):
            dest = source / link.relative_to(args.build / 'monero-fcmp')
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(link, dest)
        shutil.copytree(args.build / 'monero-fcmp/build/vanguard/bin', source / 'build/vanguard/bin')
        for relative in ['runtime-libs', 'licenses', 'cargo-home']:
            shutil.copytree(args.build / relative, build / relative,
                            ignore=shutil.ignore_patterns('.git', 'target', 'cache', 'index', 'db'))
        for relative in ['build-receipt.json', 'dependencies.txt']:
            shutil.copyfile(args.build / relative, build / relative)
        scenarios = [('both-source-trees', 'cargo-home', 'missing Rust source tree'),
                     ('registry-source-tree', 'cargo-home/registry/src', 'missing Rust source tree'),
                     ('git-source-tree', 'cargo-home/git/checkouts', 'missing Rust source tree')]
        registry_crate = next((build / 'cargo-home/registry/src').rglob('Cargo.toml')).parent
        scenarios.append(('one-registry-crate', str(registry_crate.relative_to(build)), 'required Rust crate missing'))
        git_crate = next((build / 'cargo-home/git/checkouts').rglob('crypto/fcmps/Cargo.toml')).parent
        scenarios.append(('one-git-crate', str(git_crate.relative_to(build)), 'required Rust crate missing'))
        for label, relative, expected in scenarios:
            tree = build / relative
            moved = Path(tmp) / (label + '-saved')
            tree.rename(moved)
            out = Path(tmp) / label
            result = subprocess.run([sys.executable, '-B', str(licenses.ROOT / 'vanguard/package-portable.py'),
                                     '--build', str(build), '--out', str(out)], capture_output=True, text=True, timeout=60)
            assert result.returncode != 0 and expected in result.stderr, result.stderr
            assert not list(out.rglob('*.tar.gz')), 'refused package emitted an archive'
            moved.rename(tree)
            print('PASS_REFUSAL', label, flush=True)
    print('PASS_LICENSE_CONTROLS: four native controls, two missing notice trees, one missing dual-license text, five real packager Rust-cache refusals')


if __name__ == '__main__':
    main()
