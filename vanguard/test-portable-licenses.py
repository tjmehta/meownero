#!/usr/bin/env python3
"""Exercise omitted notices, unmapped libraries and corrupted depends inputs."""
import argparse
import json
from pathlib import Path
import shutil
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
    print('PASS_LICENSE_CONTROLS: missing library notice, referenced full text, unknown library, changed source archive')


if __name__ == '__main__':
    main()
