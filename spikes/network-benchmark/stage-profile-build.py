#!/usr/bin/env python3
"""Validate and stage one isolated profile; runs inside the guarded builder."""
import argparse
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
PROVENANCE = runpy.run_path(str(HERE / 'clean15-provenance.py'))
require = PROVENANCE['require']
digest = PROVENANCE['digest']


def patch_paths(patch):
    output = subprocess.check_output(['git', 'apply', '--numstat', str(patch)], cwd='/tmp', text=True)
    paths = {line.split('\t', 2)[2] for line in output.splitlines()}
    require(paths and all(not Path(p).is_absolute() and '..' not in Path(p).parts for p in paths), 'invalid patch paths')
    return paths


def validate_fixture(patch):
    paths = patch_paths(patch)
    require('tests/unit_tests/block_reward.cpp' in paths, 'fixture must update historical block_reward.cpp')
    require(all(p.startswith('tests/unit_tests/') for p in paths), 'fixture may change only tests/unit_tests/')
    return paths


def original_source(historical, receipts):
    if os.environ.get('MEOW_PROFILE_SOURCE_ONLY') != '1':
        return PROVENANCE['verify_run'](historical, receipts)
    # Reconstruct from pinned tracked source when the ephemeral build cache is gone.
    require(not (historical / 'build').exists(), 'source-only mode refuses inherited build outputs')
    require(PROVENANCE['command']('git', '-C', str(historical), 'rev-parse', 'HEAD', 'HEAD^{tree}').splitlines()
            == [PROVENANCE['HEAD'], PROVENANCE['TREE']], 'source-only revision mismatch')
    require(not PROVENANCE['command']('git', '-C', str(historical), 'status', '--porcelain', '--untracked-files=all'), 'dirty source-only input')
    require(PROVENANCE['command']('git', '-C', str(historical), 'submodule', 'status', '--recursive')
            == (receipts / 'SUBMODULES').read_text(), 'source-only submodule mismatch')
    PROVENANCE['verify_manifest'](historical, PROVENANCE['read_manifest'](receipts / 'source-files.sha256'))
    return historical


def stage(historical, receipts, issuance, fixture, profile, source, output):
    require(profile in ('selected-9-90', 'fallback-12-120'), 'unsupported profile')
    require(not any(source.iterdir()), 'staging source must be empty')
    fixture_paths = validate_fixture(fixture)
    require(digest(fixture) == '360acc9ea7bd014225aa20ad93bee19c5f5444d126b36f93ffed0f913030f0e7',
            'fixture differs from coordinator-approved smoke-tested patch')
    monetary = issuance / (profile + '.patch')
    require(patch_paths(monetary) == {'src/cryptonote_config.h', 'src/cryptonote_basic/cryptonote_basic_impl.cpp'}, 'unexpected issuance patch paths')
    original = original_source(historical, receipts)
    lock = json.loads((issuance / 'source-lock.json').read_text())
    require(lock['source_commit'] == PROVENANCE['HEAD'], 'issuance source lock commit mismatch')
    PROVENANCE['verify_manifest'](original, lock['sha256'])
    fixture_lock_path = issuance / 'fixture-source-lock.json'
    fixture_lock = json.loads(fixture_lock_path.read_text())
    require(fixture_lock['source_commit'] == PROVENANCE['HEAD'] and
            set(fixture_lock['sha256']) == {'tests/unit_tests/block_reward.cpp'}, 'unexpected fixture source lock')
    PROVENANCE['verify_manifest'](original, fixture_lock['sha256'])
    shutil.copyfile(fixture_lock_path, output / 'fixture-source-lock.json')
    require(subprocess.check_output(['dpkg-query', '-W', '-f=${binary:Package}=${Version}\n'])
            == (receipts / 'packages.txt').read_bytes(), 'builder package mismatch')
    gamma_lock_path = issuance / 'gamma-fixture-source-lock.json'
    gamma_lock = json.loads(gamma_lock_path.read_text())
    require(gamma_lock['source_commit'] == PROVENANCE['HEAD'], 'gamma source lock mismatch')
    PROVENANCE['verify_manifest'](original, gamma_lock['sha256'])
    gamma_patch = issuance / 'selected-gamma-fixture.patch'
    require(patch_paths(gamma_patch) == {'tests/unit_tests/output_selection.cpp'}, 'unexpected gamma patch paths')
    fixture_paths |= patch_paths(gamma_patch)
    shutil.copyfile(gamma_lock_path, output / 'gamma-fixture-source-lock.json')
    # Preserve absolute /src CMake paths and mtimes for safe incremental reuse.
    # Reflinks are independent COW copies; ordinary copies are the fallback.
    subprocess.run(['cp', '-a', '--reflink=auto', str(original) + '/.', str(source)], check=True)
    for patch, name in ((monetary, 'issuance.patch'), (fixture, 'fixtures.patch'), (gamma_patch, 'gamma-fixture.patch')):
        frozen = output / name
        shutil.copyfile(patch, frozen)
        subprocess.run(['git', '-C', str(source), 'apply', '--check', str(frozen)], check=True)
        subprocess.run(['git', '-C', str(source), 'apply', str(frozen)], check=True)
    observed = runpy.run_path(str(HERE / 'check-readiness.py'))['validate_profile'](source, profile)
    require('constant_is_0_9_meow' not in (source / 'tests/unit_tests/block_reward.cpp').read_text(),
            'historical reward fixture remains; coordinator fixture update required')
    # Inherited executables must never be mistaken for newly compiled artifacts.
    for binary in ('bin/monerod', 'bin/monero-wallet-cli', 'bin/monero-wallet-rpc',
                   'tests/unit_tests/unit_tests', 'tests/unit_tests/meow_difficulty_floor_tests'):
        (source / 'build/release' / binary).unlink(missing_ok=True)
    changed = PROVENANCE['command']('git', '-C', str(source), 'diff', '--name-only').splitlines()
    require(set(changed) <= fixture_paths | patch_paths(monetary), 'unexpected tracked source changes')
    for path in changed:
        if (source / path).is_file():
            (source / path).touch()
    (output / 'source.diff').write_text(PROVENANCE['command']('git', '-C', str(source), 'diff', '--binary'))
    receipt = dict(scope=('fresh selected source build, not a reproduction pair' if os.environ.get('MEOW_PROFILE_SOURCE_ONLY') == '1' else 'incremental disposable copy, not clean reproduction'), profile=profile,
                   source_only=os.environ.get('MEOW_PROFILE_SOURCE_ONLY') == '1',
                   historical_head=PROVENANCE['HEAD'], historical_tree=PROVENANCE['TREE'],
                   builder_image=PROVENANCE['IMAGE'], copied_with='cp -a --reflink=auto; no hard-link copy',
                   issuance_sha256=digest(output / 'issuance.patch'), fixture_sha256=digest(output / 'fixtures.patch'),
                   source_lock_sha256=digest(issuance / 'source-lock.json'),
                   fixture_source_lock_sha256=digest(fixture_lock_path),
                   gamma_fixture_sha256=digest(gamma_patch), gamma_source_lock_sha256=digest(gamma_lock_path),
                   changed_file_sha256={p: digest(source / p) for p in changed if (source / p).is_file()},
                   target_seconds=observed['DIFFICULTY_TARGET_V2'], reward_atomic=observed['MEOW_BLOCK_REWARD'],
                   build_completed=False, capacity_normalization_enforced=False, fcmp_verified=False)
    (output / 'profile-inputs.json').write_text(json.dumps(receipt, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('historical', 'receipts', 'issuance', 'fixture', 'source', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--profile', required=True)
    args = parser.parse_args()
    stage(args.historical, args.receipts, args.issuance, args.fixture, args.profile, args.source, args.output)
