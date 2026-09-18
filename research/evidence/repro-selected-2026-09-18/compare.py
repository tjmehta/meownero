#!/usr/bin/env python3
"""TJS-40: independently compare two clean source-only profile builds and the prior receipts.

Re-hashes actual executables; never trusts a runner's success line. Read-only.
Usage: compare.py RUN-ROOT [--evidence OUT-DIR]
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

IMAGE = 'sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e'
HEAD = '7410c04bab0e304112710d63c3225c110bd8b4de'
TREE = '4db958cb96d72943c5c2433bd5f4a8f730037148'
BINARIES = ('build/release/bin/monerod', 'build/release/bin/monero-wallet-cli', 'build/release/bin/monero-wallet-rpc',
            'build/release/tests/unit_tests/unit_tests', 'build/release/tests/unit_tests/meow_difficulty_floor_tests')
RECEIPTS = ('BUILDER_IMAGE_ID', 'SHA256SUMS', 'VERSIONS', 'packages.txt', 'source.diff', 'issuance.patch',
            'fixtures.patch', 'gamma-fixture.patch', 'fixture-source-lock.json', 'gamma-fixture-source-lock.json',
            'native-expected.txt', 'dns-network-scope.txt')
EXPECTED_TESTS = {'consensus': 24, 'difficulty': 10, 'floor': 10, 'full-native-offline': 1228, 'dns': 9, 'full-native': 1237}
PROFILES = {'selected-9-90': (90, 9_000_000_000_000), 'fallback-12-120': (120, 12_000_000_000_000)}
# Fields of result.json that are allowed to differ between two builds of the same profile.
VOLATILE = {'tests', 'build_completed'}


def sha256(path: Path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def git(*args, cwd):
    return subprocess.check_output(['git', *args], cwd=cwd, text=True, env=dict(os.environ, GIT_OPTIONAL_LOCKS='0'))


def check(findings, ok, message):
    findings.append({'ok': bool(ok), 'check': message})
    return bool(ok)


def read_sums(path: Path):
    return {line.split('  ', 1)[1]: line.split('  ', 1)[0] for line in path.read_text().splitlines() if line.strip()}


def inspect_build(out: Path, profile: str, findings):
    rec = {'path': str(out)}
    for name in ('build.exit', 'offline.exit', 'dns.exit', 'container.exit'):
        value = (out / name).read_text().strip() if (out / name).exists() else None
        rec[name] = value
        check(findings, value == '0', f'{out.name}: {name} == 0 (got {value})')
    check(findings, (out / 'BUILDER_IMAGE_ID').read_text().strip() == IMAGE, f'{out.name}: BUILDER_IMAGE_ID is the immutable builder')
    result = json.loads((out / 'result.json').read_text())
    rec['result'] = result
    target, reward = PROFILES[profile]
    check(findings, result['profile'] == profile and result['target_seconds'] == target and result['reward_atomic'] == reward,
          f'{out.name}: profile/target/reward == {profile}/{target}/{reward}')
    check(findings, result['source_only'] is True and result['historical_head'] == HEAD and result['historical_tree'] == TREE,
          f'{out.name}: source-only staging from historical {HEAD[:9]}/{TREE[:9]}')
    check(findings, result['capacity_normalization_enforced'] is False and result['fcmp_verified'] is False,
          f'{out.name}: receipt records no capacity normalization and no FCMP verification')
    # Actual executables, re-hashed here.
    src = out / 'source'
    actual = {b: sha256(src / b) for b in BINARIES}
    rec['actual_sha256'] = actual
    recorded = read_sums(out / 'SHA256SUMS')
    check(findings, recorded == actual, f'{out.name}: re-hashed executables match the runner SHA256SUMS')
    # Source tree state: pinned HEAD plus exactly the frozen overlay diff.
    head_tree = git('rev-parse', 'HEAD', 'HEAD^{tree}', cwd=src).splitlines()
    check(findings, head_tree == [HEAD, TREE], f'{out.name}: staged source HEAD/tree are the pinned historical revision')
    live_diff = git('diff', '--binary', cwd=src)
    check(findings, live_diff == (out / 'source.diff').read_text(), f'{out.name}: live tracked diff equals frozen source.diff')
    changed = git('diff', '--name-only', cwd=src).splitlines()
    check(findings, set(changed) == set(result['changed_file_sha256']), f'{out.name}: changed tracked files are exactly the overlay set {sorted(changed)}')
    check(findings, all(sha256(src / p) == h for p, h in result['changed_file_sha256'].items()),
          f'{out.name}: overlay file hashes match the receipt')
    untracked = git('status', '--porcelain', '--untracked-files=no', cwd=src).splitlines()
    check(findings, all(line.startswith(' M ') for line in untracked), f'{out.name}: only modifications, no tracked deletions/renames')
    # Tests: counts and zero failures, from XML not logs.
    tests = {}
    for name, expected in EXPECTED_TESTS.items():
        root = ET.parse(out / f'{name}.xml').getroot()
        n, fails, errs = int(root.attrib['tests']), int(root.attrib['failures']), int(root.attrib.get('errors', 0))
        tests[name] = {'tests': n, 'failures': fails, 'errors': errs}
        check(findings, n == expected and fails == 0 and errs == 0, f'{out.name}: {name} {n}/{expected} tests, {fails} failures, {errs} errors')
    rec['tests'] = tests
    # Resource caps and events.
    rec['cgroup'] = {f: (out / f'cgroup-{f}').read_text().strip() for f in ('memory.max', 'memory.swap.max', 'cpu.max', 'memory.peak', 'memory.events')}
    events = dict(line.split() for line in rec['cgroup']['memory.events'].splitlines())
    # --memory=4g --memory-swap=4g => memory.max 4 GiB and memory.swap.max 0 (no swap); --cpus=2 => 200000/100000.
    check(findings, rec['cgroup']['memory.max'] == '4294967296' and rec['cgroup']['memory.swap.max'] == '0'
          and rec['cgroup']['cpu.max'] == '200000 100000', f'{out.name}: cgroup caps 4 GiB / no swap / 2 CPUs')
    check(findings, events.get('max', '0') == '0' and events.get('oom', '0') == '0' and events.get('oom_kill', '0') == '0',
          f'{out.name}: no memory-limit/OOM events ({rec["cgroup"]["memory.events"].replace(chr(10), ", ")})')
    # ccache: launcher was configured but disabled; the make log must show no cache hits.
    run_log = (out / 'run.log').read_text()
    check(findings, 'ccache' not in (out / 'make.log').read_text().lower().replace('ccache_disable', ''), f'{out.name}: make.log carries no ccache activity')
    rec['run_log_sha256'] = sha256(out / 'run.log')
    rec['receipt_sha256'] = {r: sha256(out / r) for r in RECEIPTS}
    rec['versions'] = (out / 'VERSIONS').read_text()
    rec['packages_sha256'] = sha256(out / 'packages.txt')
    return rec


def compare_pair(profile, first, second, findings):
    pair = {}
    same = first['actual_sha256'] == second['actual_sha256']
    pair['executables_identical'] = same
    check(findings, same, f'{profile}: all five executables hash identically across first and second clean builds')
    for r in RECEIPTS:
        check(findings, first['receipt_sha256'][r] == second['receipt_sha256'][r], f'{profile}: receipt {r} identical across builds')
    a = {k: v for k, v in first['result'].items() if k not in VOLATILE}
    b = {k: v for k, v in second['result'].items() if k not in VOLATILE}
    check(findings, a == b, f'{profile}: result.json identical across builds apart from test timings')
    return pair


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('run', type=Path)
    ap.add_argument('--evidence', type=Path)
    ap.add_argument('--prior', type=Path, default=Path('build/recovery-network-20260913'))
    args = ap.parse_args()
    run = args.run.resolve()
    findings = []
    report = {'run_root': str(run), 'builder_image': IMAGE, 'historical_head': HEAD, 'historical_tree': TREE,
              'inputs_manifest_sha256': sha256(run / 'INPUT_SHA256SUMS'), 'profiles': {}}
    frozen_packages = run / 'inputs/research/evidence/clean15-2026-09-12/first/packages.txt'
    frozen_packages_sha = sha256(frozen_packages)
    prior = {'selected-9-90': 'selected-9-90-launch-01', 'fallback-12-120': 'fallback-12-120-run-01'}
    for profile in PROFILES:
        builds = {}
        for cell in ('first', 'second'):
            out = run / profile / cell
            if not (out / 'build.exit').exists():
                check(findings, False, f'{profile}/{cell}: build did not complete (no build.exit)')
                continue
            builds[cell] = inspect_build(out, profile, findings)
            check(findings, builds[cell]['packages_sha256'] == frozen_packages_sha, f'{profile}/{cell}: live package manifest equals the frozen clean15 image manifest')
        entry = {'builds': builds}
        if len(builds) == 2:
            entry['pair'] = compare_pair(profile, builds['first'], builds['second'], findings)
        prior_sums = args.prior / prior[profile] / 'output/SHA256SUMS'
        if prior_sums.exists() and builds:
            p = read_sums(prior_sums)
            any_build = next(iter(builds.values()))
            entry['prior_2026_09_13_identical'] = p == any_build['actual_sha256']
            check(findings, p == any_build['actual_sha256'], f'{profile}: hashes equal the September 13 recovered binaries ({prior[profile]}) — same host/image, different day')
            entry['prior_2026_09_13_sha256'] = p
        report['profiles'][profile] = entry
    report['checks'] = findings
    report['all_ok'] = all(f['ok'] for f in findings)
    report['status'] = 'PASS_SAME_HOST_SAME_IMAGE_PAIRS' if report['all_ok'] else 'FAIL_OR_INCOMPLETE'
    report['limits'] = [
        'same host, same immutable builder image; not an independently reconstructed toolchain (apt versions are unpinned in chain/Dockerfile)',
        'source-only staging from the reconstructed historical clean15 source plus the existing selected/fallback overlays; no monetary or consensus change',
        'native CI selection retains the three documented exclusions (ban.subnet, http_server.response_soft_limit, notify.works); DNS phase uses bridge networking',
        'no runtime, capacity-normalization, FCMP, loaded-network, wallet/fee/aggregate or launch-readiness claim',
    ]
    print(json.dumps(report, indent=2))
    if args.evidence:
        ev = args.evidence.resolve()
        ev.mkdir(parents=True, exist_ok=True)
        if any(ev.iterdir()):
            raise SystemExit('evidence directory must be empty')
        (ev / 'summary.json').write_text(json.dumps(report, indent=2) + '\n')
        for name in ('INPUT_SHA256SUMS', 'driver.sh', 'driver.log', 'driver.exit', 'compare.py'):
            if (run / name).exists():
                shutil.copy2(run / name, ev / name)
        shutil.copytree(run / 'freeze', ev / 'freeze', ignore=shutil.ignore_patterns('builder-image-inspect.json'))
        shutil.copy2(run / 'freeze/builder-image-inspect.json', ev / 'freeze/builder-image-inspect.json')
        for profile in PROFILES:
            for cell in ('first', 'second'):
                out = run / profile / cell
                if not out.exists():
                    continue
                dst = ev / profile / cell
                dst.mkdir(parents=True)
                for item in out.iterdir():
                    if item.is_file() and item.name != 'make.log' and item.suffix not in ('.cid',):
                        shutil.copy2(item, dst / item.name)
                # make.log is large; keep its hash and tail
                (dst / 'make.log.sha256').write_text(sha256(out / 'make.log') + '  make.log\n')
                if (run / f'{profile}/{cell}.launch.log').exists():
                    shutil.copy2(run / f'{profile}/{cell}.launch.log', ev / profile / f'{cell}.launch.log')
        rows = []
        for p in sorted(x for x in ev.rglob('*') if x.is_file() and x.name != 'MANIFEST.sha256'):
            rows.append(f'{sha256(p)}  {p.relative_to(ev)}')
        (ev / 'MANIFEST.sha256').write_text('\n'.join(rows) + '\n')
    raise SystemExit(0 if report['all_ok'] else 1)


if __name__ == '__main__':
    main()
