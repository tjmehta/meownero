#!/usr/bin/env python3
"""Run inside the immutable builder capped at 512 MiB; no compiler or network."""
import copy
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
stage = runpy.run_path(str(HERE / 'stage-profile-build.py'))
merge = runpy.run_path(str(HERE / 'merge-native-results.py'))['merge']


def refused(label, call):
    try:
        call()
    except (ValueError, subprocess.CalledProcessError):
        print('PASS refusal:', label, flush=True)
    else:
        raise AssertionError('accepted ' + label)


with tempfile.TemporaryDirectory() as tmp:
    out = Path(tmp)
    old = ET.parse('/old/full-native.xml').getroot()
    # Archived failing XML supplies the actual pinned GTest format. Clearing failures
    # here constructs synthetic merger inputs, never test or build success evidence.
    groups = [copy.deepcopy(g) for g in old]
    for group in groups:
        group.set('failures', '0')
        for case in group:
            for failure in list(case):
                case.remove(failure)
    expected = ''.join(g.attrib['name'] + '.\n' + ''.join('  ' + c.attrib['name'] + '\n' for c in g) for g in groups)
    (out / 'native-expected.txt').write_text(expected)
    for phase, dns in [('full-native-offline', False), ('dns', True)]:
        root = ET.Element('testsuites', failures='0')
        root.extend(g for g in groups if (g.attrib['name'] in ('DNSResolver', 'AddressFromURL')) == dns)
        root.set('tests', str(len(root.findall('./testsuite/testcase'))))
        ET.ElementTree(root).write(out / (phase + '.xml'))
    merge(out)
    assert ET.parse(out / 'full-native.xml').getroot().attrib['tests'] == '1237'
    print('PASS synthetic pinned XML exact coverage: 1237', flush=True)
    dns_path = out / 'dns.xml'
    baseline = dns_path.read_bytes()
    for kind in ('missing', 'extra', 'duplicate', 'failure', 'error', 'skipped', 'notrun', 'suppressed', 'count', 'phase-failure', 'empty-phase'):
        root = ET.fromstring(baseline)
        case = root[0][0]
        if kind == 'missing':
            root[0].remove(case); root.set('tests', str(int(root.attrib['tests']) - 1))
        elif kind == 'extra':
            case.set('name', 'unexpected')
        elif kind == 'duplicate':
            root[0].append(copy.deepcopy(case)); root.set('tests', str(int(root.attrib['tests']) + 1))
        elif kind in ('failure', 'error', 'skipped'):
            ET.SubElement(case, kind)
        elif kind in ('notrun', 'suppressed'):
            case.set('status' if kind == 'notrun' else 'result', kind)
        elif kind == 'count':
            root.set('tests', '1')
        elif kind == 'phase-failure':
            root.set('failures', '1')
        else:
            root.clear(); root.set('tests', '0')
        ET.ElementTree(root).write(dns_path)
        refused(kind, lambda: merge(out))
    dns_path.write_bytes(baseline)
    for text in ('', expected + 'DNSResolver.\n  IPv4Success\n', '  orphan\n'):
        (out / 'native-expected.txt').write_text(text)
        refused('invalid expected selection', lambda: merge(out))

os.environ['MEOW_PROFILE_SOURCE_ONLY'] = '1'
original = Path('/original')
receipts = Path('/receipts')
issuance = Path('/issuance')
stage['original_source'](original, receipts)
print('PASS exact original source/submodules/full frozen manifest', flush=True)
with tempfile.TemporaryDirectory() as tmp:
    base = Path(tmp)
    for profile in ('selected-9-90', 'fallback-12-120'):
        out = base / profile
        src = out / 'source'
        src.mkdir(parents=True)
        stage['stage'](original, receipts, issuance, issuance / 'selected-unit-fixtures.patch', profile, src, out)
        receipt = json.loads((out / 'profile-inputs.json').read_text())
        assert receipt['source_only'] and not receipt['build_completed']
        assert not (src / 'build').exists()
        refused('nonempty staging', lambda: stage['stage'](original, receipts, issuance, issuance / 'selected-unit-fixtures.patch', profile, src, out))
        for patch in ('gamma-fixture.patch', 'fixtures.patch', 'issuance.patch'):
            subprocess.run(['git', '-C', str(src), 'apply', '-R', str(out / patch)], check=True)
        stage['original_source'](src, receipts)
        print('PASS staging and all overlays reverse byte-exact:', profile, flush=True)
        (src / 'build').mkdir()
        refused('inherited build in source-only mode', lambda: stage['original_source'](src, receipts))
        (src / 'build').rmdir()
        (src / 'dirty').write_text('dirty')
        refused('dirty source', lambda: stage['original_source'](src, receipts))
        (src / 'dirty').unlink()
        fixture_path = src / 'tests/unit_tests/block_reward.cpp'
        fixture_path.write_text(fixture_path.read_text() + '\n')
        lock = json.loads((issuance / 'fixture-source-lock.json').read_text())
        refused('original fixture source hash', lambda: stage['PROVENANCE']['verify_manifest'](src, lock['sha256']))
        shutil.rmtree(out)
stage['original_source'](original, receipts)
print('PASS original source preserved after staging/refusals', flush=True)

# Exercise the real shell runner with fake Docker/tee processes, never a nested
# daemon. The actual guard function supplies flags; only resource waiting is omitted.
guard = Path('/chain/network-build-guard.sh').read_text()
wrapper = 'docker() {' + guard.split('docker() {', 1)[1].split('\n}', 1)[0] + '\n}'
runner = HERE / 'build-profile.sh'
direct = subprocess.run(['bash', str(runner), '--locked'], capture_output=True, text=True)
assert direct.returncode == 2 and 'wrapper missing' in direct.stderr
print('PASS direct --locked without guard wrapper refused', flush=True)
for wait in ('0', 'invalid', '9999999999999999999999999999999999999', '3601'):
    result = subprocess.run(['bash', '/chain/network-build-guard.sh', 'false'],
                            env=dict(os.environ, MEOW_NETWORK_WAIT_SECONDS=wait), capture_output=True)
    assert result.returncode == 2
print('PASS zero/invalid/large/out-of-range resource waits refused', flush=True)
with tempfile.TemporaryDirectory() as tmp:
    base = Path(tmp)
    stubs = base / 'bin'
    stubs.mkdir()
    (stubs / 'docker').write_text('''#!/usr/bin/python3
import json,os,pathlib,sys
args=sys.argv[1:]; root=pathlib.Path(os.environ['CASE'])
if args[:2]==['image','inspect']:
 print('sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e')
elif args[0]=='run':
 sys.stdin.read()
 count=root/'count'; n=int(count.read_text())+1 if count.exists() else 1; count.write_text(str(n))
 (root/('args'+str(n)+'.json')).write_text(json.dumps(args))
 assert not (root/'output/build.exit').exists(), 'premature final receipt'
 print('synthetic docker output')
 sys.exit(int(os.environ['OFFLINE_EXIT' if n==1 else 'DNS_EXIT']))
''')
    (stubs / 'tee').write_text('''#!/bin/bash
/usr/bin/tee "$@"
if [[ ${1##*/} == run.log ]]; then exit "$OFFLINE_TEE"; fi
exit "$DNS_TEE"
''')
    for stub in stubs.iterdir():
        stub.chmod(0o755)
    for index, (offline, offline_tee, dns, dns_tee) in enumerate(((0,0,0,0), (9,0,0,0), (0,7,0,0), (9,7,0,0), (0,0,9,0), (0,0,0,7))):
        case = base / str(index)
        case.mkdir()
        env = dict(os.environ, PATH=str(stubs)+':'+os.environ['PATH'], CASE=str(case),
                   OFFLINE_EXIT=str(offline), OFFLINE_TEE=str(offline_tee), DNS_EXIT=str(dns), DNS_TEE=str(dns_tee))
        script = wrapper + '''
export -f docker
export MEOW_JOBS=1
exec 9>/tmp/meownero-swarm-20260912-heavy.lock
flock 9
bash "$1" --locked /original /issuance selected-9-90 /issuance/selected-unit-fixtures.patch "$2"
'''
        result = subprocess.run(['bash', '-c', script, 'test', str(runner), str(case / 'output')], env=env, capture_output=True, text=True)
        wanted = offline or offline_tee or dns or dns_tee
        assert result.returncode == wanted, result.stdout + result.stderr
        out = case / 'output'
        assert int((out / 'build.exit').read_text()) == wanted
        assert int((out / 'offline.exit').read_text()) == (offline or offline_tee)
        assert (out / 'dns.exit').exists() == (not (offline or offline_tee))
        for path in case.glob('args*.json'):
            args = json.loads(path.read_text())
            assert all(flag in args for flag in ('--memory=4g', '--memory-swap=4g', '--cpus=2'))
            assert args[args.index('--network')+1] == ('none' if path.stem == 'args1' else 'bridge')
            assert '-p' not in args and '--publish' not in args
        print('PASS real runner command caps/network, phase/final receipts, Docker/tee exits:', (offline, offline_tee, dns, dns_tee), flush=True)
