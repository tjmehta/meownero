#!/usr/bin/env python3
"""Smoke-test full emission fixtures against literal extracted reward functions."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

from verify import item, verify_source

HERE = Path(__file__).resolve().parent


def main():
    src, out = map(Path, sys.argv[1:])
    source_lock = json.loads((HERE / 'source-lock.json').read_text())
    fixture_lock = json.loads((HERE / 'fixture-source-lock.json').read_text())
    verify_source(src, source_lock)
    verify_source(src, fixture_lock)
    inputs = {**source_lock['sha256'], **fixture_lock['sha256']}
    # Reuse the pinned source's gtest archives; record their bytes explicitly.
    archives = [src / 'build/release/tests/gtest' / name for name in ('libgtest_main.a', 'libgtest.a')]
    results = {'scope': 'full emission fixture; extracted reward functions; not full-node integration',
               'launch_ready': False, 'profiles': [], 'source_inputs': inputs,
               'gtest_archives': {str(p.relative_to(src)): hashlib.sha256(p.read_bytes()).hexdigest() for p in archives},
               'fixture_patch_sha256': hashlib.sha256((HERE / 'selected-unit-fixtures.patch').read_bytes()).hexdigest(),
               'toolchain': subprocess.check_output(['g++', '--version'], text=True)}
    for profile in ('selected-9-90', 'fallback-12-120', 'historical-negative-control'):
        target = out / profile
        target.mkdir()
        paths = ('src/cryptonote_config.h', 'src/cryptonote_basic/cryptonote_basic_impl.cpp',
                 'tests/unit_tests/block_reward.cpp')
        for name in paths:
            dest = target / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src / name, dest)
        patches = [HERE / 'selected-unit-fixtures.patch']
        if profile != 'historical-negative-control':
            patches.insert(0, HERE / (profile + '.patch'))
        for patch in patches:
            subprocess.run(['git', 'apply', '--check', str(patch)], cwd=target, check=True)
            subprocess.run(['git', 'apply', str(patch)], cwd=target, check=True)
        source = (target / paths[1]).read_text()
        code = '#include <cassert>\n#include "cryptonote_config.h"\n#include "int-util.h"\n#define MERROR(x) do {} while (0)\nnamespace cryptonote {\n'
        code += item(source, 'size_t get_min_block_weight(') + '\n'
        code += item(source, 'bool get_block_reward(') + '\n}\n'
        (target / 'reward.cpp').write_text(code)
        subprocess.run(['g++', '-std=c++14', '-O1', '-pthread',
                        '-I', str(target / 'src'), '-I', str(src / 'src'),
                        '-I', str(src / 'contrib/epee/include'), '-I', str(src / 'external/easylogging++'),
                        '-I', str(src / 'tests/gtest/include'),
                        str(target / paths[2]), str(target / 'reward.cpp'),
                        str(src / 'contrib/epee/src/int-util.cpp'), *map(str, archives),
                        '-o', str(target / 'fixture-tests')], check=True)
        run = subprocess.run([str(target / 'fixture-tests'), '--gtest_output=xml:' + str(target / 'tests.xml')],
                             text=True, capture_output=True, timeout=90)
        (target / 'run.log').write_text(run.stdout + run.stderr)
        xml = ET.parse(target / 'tests.xml').getroot()
        failed = [case.attrib['name'] for case in xml.iter('testcase') if case.find('failure') is not None]
        tests = int(xml.attrib['tests'])
        assert tests == 7, tests
        if profile == 'historical-negative-control':
            assert run.returncode != 0
            assert 'selected_reward_spacing_pair' in failed
        else:
            assert run.returncode == 0 and not failed, run.stdout + run.stderr
        for patch in reversed(patches):
            subprocess.run(['git', 'apply', '-R', str(patch)], cwd=target, check=True)
        assert all((target / name).read_bytes() == (src / name).read_bytes() for name in paths)
        results['profiles'].append({'profile': profile, 'tests': tests, 'exit': run.returncode,
                                    'failed_tests': failed, 'reverse_application_exact': True})
    verify_source(src, source_lock)
    verify_source(src, fixture_lock)
    (out / 'summary.json').write_text(json.dumps(results, indent=2) + '\n')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
