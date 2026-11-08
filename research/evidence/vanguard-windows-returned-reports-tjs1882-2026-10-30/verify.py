#!/usr/bin/env python3
"""Inspect the three immutable returned reports against diagnostics-v2 bytes.

Usage: python3 -B verify.py BUNDLE_ZIP REPORT_DIRECTORY OUTPUT_JSON
Reports are bounded JSON data, never extracted or executed. Only the reviewed
bundle's pure public projectors and coverage function are evaluated below.
This verifies tester evidence, not a new Windows execution or acceptance.
"""
import ast
import copy
import hashlib
import io
import json
import math
from pathlib import Path
import re
import stat
import sys
import zipfile

BUNDLE_SHA = 'bedd371bc042ec2b893e45693083eae64637ca1a1f496933f2f90a5bf6f38034'
MANIFEST_SHA = '46489d0ac6cea2e023506f4c893176d4d6d7de68580b19aa0c2c5d52bc364c65'
EXPECTED = {
    'arm-report-v2.zip': (3326, '394294d5dc1465f2eae52e256bdce9281d72ab3f31c4ab33f3e095c01fa8f2ea'),
    'intel-report-v2.zip': (4498, '0e31a52562f6d771c05480aa170b487f7f141ddbaae9f8b2f7064366341740af'),
    'intel-report3-v2.zip': (4487, 'e2ade0040cc727141850971990b566651c720db272227c5e79dee3518410173c'),
}
PREFIX = 'meownero-windows-test/'
sha = lambda b: hashlib.sha256(b).hexdigest()


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        assert key not in result, 'duplicate JSON key'
        result[key] = value
    return result


def load(raw):
    def invalid_constant(_):
        raise AssertionError('nonfinite JSON constant')
    return json.loads(raw, object_pairs_hook=unique_pairs, parse_constant=invalid_constant)


def keys(value, allowed):
    assert set(value) == set(allowed.split()), 'unexpected or missing public fields'


def public_values(value):
    # Bounded privacy scan supplements the exact schemas/projectors below.
    if isinstance(value, dict):
        for key, child in value.items():
            assert not re.search(r'seed|mnemonic|password|secret|address|argv|stderr|stdout|token|url|path', key, re.I)
            public_values(child)
    elif isinstance(value, list):
        for child in value:
            public_values(child)
    elif isinstance(value, str):
        assert len(value) <= 256
        assert not re.search(r'/home/|/Users/|[A-Za-z]:\\|https?://|Bearer\s', value, re.I)
    elif isinstance(value, float):
        assert math.isfinite(value)
    else:
        assert value is None or type(value) in (bool, int)


def read_report(path):
    raw = path.read_bytes()
    assert (len(raw), sha(raw)) == EXPECTED[path.name]
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        infos = archive.infolist()
        expected = {'bundle-receipt.json', 'public/ci-receipt.json', 'public/check.json',
                    'public/journey.json', 'public/controls.json'}
        if path.name != 'arm-report-v2.zip':
            expected.add('public/journey-diagnostic.json')
        assert len(infos) == len(expected) and {i.filename for i in infos} == expected
        assert sum(i.file_size for i in infos) <= 12 * 1024**2
        documents = {}
        for info in infos:
            assert not info.flag_bits & 1 and not info.is_dir()
            assert stat.S_IFMT(info.external_attr >> 16) in (0, stat.S_IFREG)
            assert info.file_size <= 2 * 1024**2
            documents[info.filename] = load(archive.read(info))  # validates CRC, no extraction
            public_values(documents[info.filename])
        return documents


def functions(controller):
    # No imports, module initializers, main, subprocess or native calls execute.
    wanted = {'public_check', 'public_cli_event', 'public_capacity', 'public_diagnostic', 'control_coverage'}
    selected = [n for n in ast.parse(controller).body if isinstance(n, ast.FunctionDef) and n.name in wanted]
    namespace = {'math': math}
    exec(compile(ast.Module(body=selected, type_ignores=[]), '<verified-pure-projectors>', 'exec'), namespace)
    return namespace


def validate(documents, lane, row, projectors, target):
    outer = documents['bundle-receipt.json']
    ci = documents['public/ci-receipt.json']
    check = documents['public/check.json']
    journey = documents['public/journey.json']
    controls = documents['public/controls.json']
    arm = target == 'windows-aarch64'
    result = 'INCOMPLETE_NATIVE_ARCHIVE_CONTROLS' if arm else 'PASS_NATIVE_ARCHIVE_JOURNEY_AND_TEN_CONTROLS'
    keys(outer, 'schema result bundle_manifest_sha256 prepare_only native_acceptance private_data_exported target archive_sha256 controller_sha256')
    assert outer['schema'] == 'meownero-windows-test-bundle-report/1'
    assert outer['result'] == ci['result'] == result
    assert outer['target'] == ci['target'] == target
    assert outer['bundle_manifest_sha256'] == MANIFEST_SHA
    assert outer['prepare_only'] is False and outer['private_data_exported'] is False
    assert outer['native_acceptance'] == 'REQUIRES_INDEPENDENT_REVIEW'
    assert outer['controller_sha256'] == lane['controller_sha256']
    assert outer['archive_sha256'] == ci['archive_sha256'] == row['archive_sha256']
    assert ci['inputs_sha256'] == lane['inputs_sha256']
    keys(ci, 'schema target result inputs_sha256 archive_sha256 github_run_id github_sha python os process_architecture parts_archive_and_helper_binding'
         + ('' if arm else ' execution_substrate windows_32bit_os_execution'))
    assert ci['schema'] == 'meownero-private-native-ci/1'
    assert ci['github_run_id'] is None and ci['github_sha'] is None
    assert ci['parts_archive_and_helper_binding'] == 'PASS'
    assert ci['process_architecture'] == ('ARM64' if arm else 'AMD64')
    assert '64 bit (' + ci['process_architecture'] + ')' in ci['python']
    assert ci['os'].startswith('Windows-11-')
    assert check == projectors['public_check'](check), 'unprojected check data'
    assert check['schema'] == 'meownero-native-windows-ci-check/1'
    assert check['native_architecture'] == ('aarch64' if arm else 'x86_64')
    assert check['package_architecture'] == row['architecture'] == ('aarch64' if arm else 'i686')
    assert check['execution_substrate'] == journey['execution_substrate'] == ('NATIVE' if arm else 'NATIVE_WINDOWS_WOW64')
    assert check['result'] == ('INCOMPLETE_NATIVE_ARCHIVE_CONTROLS' if arm else 'PASS_NATIVE_ARCHIVE_JOURNEY')
    assert check['windows_32bit_os_execution'] == 'UNTESTED'
    assert check['native_cli_event'] == {'status': 'NOT_REQUESTED', 'cause': 'UNKNOWN'}
    if arm:
        assert 'native_qualification' in check  # projector checks all ARM qualification fields
    else:
        assert ci['execution_substrate'] == 'NATIVE_WINDOWS_WOW64'
        assert ci['windows_32bit_os_execution'] == 'UNTESTED'
        probe = check['native_exception_probe']
        assert probe['sha256'] == row['native_exception_probe']['files']['bin/i686-exception-probe.exe']
        assert probe['source_sha256'] == row['native_exception_probe']['files']['build-evidence/i686-exception-probe.cpp']
        assert probe['exit'] == 0 and probe['reaped'] is True and probe['exact_success_line'] is True
        assert check['capacity_admission']['status'] == 'READY'
    expected_phases = ['preflight', 'journey', 'controls'] if arm else ['exception-probe', 'preflight', 'journey', 'controls']
    assert [p['name'] for p in check['phases']] == expected_phases
    for phase in check['phases']:
        assert phase['reaped'] is True and phase['exit'] == (2 if arm and phase['name'] == 'controls' else 0)
    assert check['owned_job']['children'] == [{k: p[k] for k in ('pid', 'exit')} for p in check['phases']]
    keys(journey, 'schema result upstream_commit architecture release_manifest_sha256 program_sha256 cleanup payments native_processes execution_substrate receive_atomic restore_matches subsequent_spend_atomic cli_open_restored_wallet owned_job_cleanup owned_job wall_seconds')
    assert journey['schema'] == 'meownero-portable-journey/1' and journey['result'] == 'PASS_NATIVE_JOURNEY'
    assert journey['upstream_commit'] == 'e151643c5269c83bf24a83b2548e2493876026b2'
    assert journey['architecture'] == row['architecture']
    assert journey['release_manifest_sha256'] == controls['release_manifest_sha256'] == row['release_manifest_sha256']
    assert journey['program_sha256'] == row['program_sha256']
    assert journey['receive_atomic'] == 5000000000000 and journey['subsequent_spend_atomic'] == 2000000000000
    assert all(journey[k] is True for k in ('restore_matches', 'cli_open_restored_wallet', 'owned_job_cleanup'))
    assert len(journey['payments']) == 2
    for payment, amount in zip(journey['payments'], (5000000000000, 2000000000000)):
        keys(payment, 'tx_hash amount_atomic rct_type carrot_outputs')
        assert re.fullmatch('[0-9a-f]{64}', payment['tx_hash'])
        assert payment['amount_atomic'] == amount and payment['rct_type'] == 7 and payment['carrot_outputs'] is True
    assert [p['name'] for p in journey['native_processes']] == ['daemon', 'sender', 'receiver', 'restored']
    for process in journey['native_processes']:
        keys(process, 'name pid binary_sha256 bundled_library_sha256')
        assert process['binary_sha256'] == row['program_sha256']['monerod' if process['name'] == 'daemon' else 'monero-wallet-rpc']
        assert process['bundled_library_sha256'] == {}
        assert any(c['name'] == process['name'] and c['pid'] == process['pid'] for c in journey['cleanup'])
    assert [p['name'] for p in journey['cleanup']] == ['cli', 'restored', 'receiver', 'sender', 'daemon']
    for child in journey['cleanup']:
        keys(child, 'name pid exit removed')
        assert child['removed'] is True and type(child['exit']) is int
    assert next(c for c in journey['cleanup'] if c['name'] == 'cli')['exit'] == 0
    assert sorted(journey['owned_job']['children'], key=lambda p: p['pid']) == sorted(
        [{k: p[k] for k in ('pid', 'exit')} for p in journey['cleanup']], key=lambda p: p['pid'])
    for job in [journey['owned_job'], check['owned_job']]:
        keys(job, 'active_processes total_processes peak_committed_bytes memory_limit_bytes children')
        assert job['active_processes'] == 0 and job['memory_limit_bytes'] == 4294967296
        assert 0 < job['peak_committed_bytes'] <= job['memory_limit_bytes']
        for child in job['children']:
            keys(child, 'pid exit')
    keys(controls, 'schema result release_manifest_sha256 cases')
    assert controls['schema'] == 'meownero-portable-controls/2'
    assert projectors['control_coverage'](controls) is arm
    for case in controls['cases']:
        if case['case'].endswith('-owned-cleanup'):
            keys(case, 'case signal removed process_count')
            assert case['signal'] == ('CTRL_BREAK_EVENT' if case['case'].startswith('cancelled') else 'WINDOWS_JOB_TIMER')
        elif case.get('status') != 'NOT_EXECUTED':
            keys(case, 'case refused' + (' sentinel_preserved' if case['case'] == 'collision-preservation' else ''))
    if not arm:
        diagnostic = documents['public/journey-diagnostic.json']
        assert diagnostic == projectors['public_diagnostic'](diagnostic), 'unprojected diagnostic data'
        assert diagnostic['tester_sha256'] == row['package_helpers']['tester.py']
        assert diagnostic['result'] == 'PASS_BOUND_JOURNEY_CALL' and diagnostic['phase'] == 'VERIFY_OWNED_CLEANUP'
        assert diagnostic['journey_public_receipt_exists'] is True and 'first_failure' not in diagnostic
        assert diagnostic['native_cli']['exit'] == 0 and diagnostic['native_cli']['exit_class'] == 'SUCCESS'
        assert diagnostic['native_cli']['pid'] == journey['cleanup'][0]['pid']
        assert [p['operation'] for p in diagnostic['funding_operations']] == ['generateblocks', 'refresh', 'get_balance']
        for operation in diagnostic['funding_operations']:
            assert operation['outcome'] == 'PASS' and operation['socket_timeout_seconds'] == 90
            assert operation['journey_deadline_seconds'] == 1200
            assert abs(operation['journey_elapsed_at_start_seconds'] + operation['journey_remaining_at_start_seconds'] - 1200) < .00001


def main():
    assert not sys.flags.optimize
    bundle_path, report_root, output = map(Path, sys.argv[1:])
    raw = bundle_path.read_bytes()
    assert len(raw) == 164120029 and sha(raw) == BUNDLE_SHA
    rows = []
    negative = []
    parent_raw = (report_root / 'parent-report-verification.json').read_bytes()
    parent = load(parent_raw)
    with zipfile.ZipFile(io.BytesIO(raw)) as bundle:
        manifest_raw = bundle.read(PREFIX + 'bundle.json')
        assert sha(manifest_raw) == MANIFEST_SHA
        manifest = load(manifest_raw)
        for name in EXPECTED:
            documents = read_report(report_root / name)
            target = documents['bundle-receipt.json']['target']
            lane = dict(manifest['lanes'][target])
            root = PREFIX + lane['root'] + '/'
            controller = bundle.read(root + 'vanguard/run-portable-ci.py')
            lane['controller_sha256'] = sha(controller)
            assert lane['controller_sha256'] == manifest['helper_bindings']['controllers'][target]
            inputs_raw = bundle.read(root + 'vanguard/ci-inputs.json')
            assert sha(inputs_raw) == lane['inputs_sha256']
            inputs = load(inputs_raw)
            for filename, digest in inputs['source_files'].items():
                assert sha(bundle.read(root + filename)) == digest
            row = inputs['targets'][target]
            archive_raw = bundle.read(PREFIX + lane['archive'])
            assert len(archive_raw) == row['archive_bytes'] and sha(archive_raw) == row['archive_sha256']
            with zipfile.ZipFile(io.BytesIO(archive_raw)) as package:
                package_root = row['package_name'] + '/'
                release_raw = package.read(package_root + 'release.json')
                assert sha(release_raw) == row['release_manifest_sha256']
                for program, digest in row['program_sha256'].items():
                    exe = package.read(package_root + 'bin/' + program + '.exe')
                    assert sha(exe) == digest and exe[:2] == b'MZ'
                    pe = int.from_bytes(exe[60:64], 'little')
                    assert exe[pe:pe+4] == b'PE\x00\x00'
                    assert int.from_bytes(exe[pe+4:pe+6], 'little') == (0xaa64 if target == 'windows-aarch64' else 0x14c)
                for helper, digest in row['package_helpers'].items():
                    assert sha(package.read(package_root + helper)) == digest
            projectors = functions(controller)
            validate(documents, lane, row, projectors, target)
            summary = next(r for r in parent['reports'] if r['filename'] == name)
            outer, check = documents['bundle-receipt.json'], documents['public/check.json']
            for key in ('target', 'result', 'bundle_manifest_sha256', 'archive_sha256', 'controller_sha256'):
                assert summary[key] == outer[key]
            assert summary['inputs_sha256'] == lane['inputs_sha256']
            assert (summary['zip_bytes'], summary['zip_sha256']) == EXPECTED[name]
            assert summary['json_members'] == list(documents)
            assert summary['cases'] == documents['public/controls.json']['cases']
            assert summary['journey_result'] == documents['public/journey.json']['result']
            assert summary['control_result'] == documents['public/controls.json']['result']
            assert summary['native_architecture'] == check['native_architecture']
            assert summary['package_architecture'] == check['package_architecture']
            assert summary['owned_active_processes'] == check['owned_job']['active_processes'] == 0
            funding = documents.get('public/journey-diagnostic.json', {}).get('funding_operations')
            assert summary['funding_operations'] == funding
            rows.append({**{k: summary[k] for k in ('filename', 'source_message_id', 'source_timestamp', 'zip_bytes', 'zip_sha256')},
                'target': target, 'result': outer['result'], 'native_architecture': check['native_architecture'],
                'package_architecture': check['package_architecture'], 'execution_substrate': check['execution_substrate'],
                'release_manifest_sha256': row['release_manifest_sha256'], 'program_sha256': row['program_sha256'],
                'controller_sha256': lane['controller_sha256'], 'inputs_sha256': lane['inputs_sha256'],
                'nested_archive_sha256': row['archive_sha256'], 'json_members': list(documents),
                'completed_controls': 9 if target == 'windows-aarch64' else 10,
                'unexecuted_controls': ['symlink-directory'] if target == 'windows-aarch64' else [],
                'control_phase_exit': check['phases'][-1]['exit'], 'cleanup_active_processes': 0,
                'funding_operations': funding, 'private_data_exported': False,
                'validation': 'PASS_EXACT_BINDINGS_OUTCOMES_PUBLIC_SCHEMA_AND_REPORTED_CLEANUP',
                'independent_acceptance': 'PENDING_EXISTING_REVIEWER'})
            mutations = [('wrong-manifest', lambda d: d['bundle-receipt.json'].update(bundle_manifest_sha256='0'*64)),
                         ('active-owned-process', lambda d: d['public/check.json']['owned_job'].update(active_processes=1)),
                         ('wrong-program-architecture', lambda d: d['public/check.json'].update(package_architecture='x86_64'))]
            if target == 'windows-aarch64':
                mutations += [('false-full-pass', lambda d: d['bundle-receipt.json'].update(result='PASS_NATIVE_ARCHIVE_JOURNEY_AND_TEN_CONTROLS')),
                              ('false-refused-skip', lambda d: d['public/controls.json']['cases'][4].update(refused=True))]
            else:
                mutations += [('private-diagnostic-field', lambda d: d['public/journey-diagnostic.json'].update(private_marker='SYNTHETIC_NEGATIVE_CONTROL'))]
            for label, mutate in mutations:
                changed = copy.deepcopy(documents)
                mutate(changed)
                try:
                    validate(changed, lane, row, projectors, target)
                except AssertionError:
                    negative.append({'report': name, 'mutation': label, 'result': 'REJECTED_EXPECTED'})
                else:
                    raise AssertionError('negative control accepted: ' + label)
    result = {'schema': 'meownero-returned-windows-report-validation/1',
        'result': 'PASS_THREE_RETURNED_REPORT_VALIDATIONS', 'bundle_bytes': len(raw), 'bundle_sha256': BUNDLE_SHA,
        'bundle_manifest_sha256': MANIFEST_SHA, 'candidate_source_revision': '6836e5e1b14e66292cb0393b9f8ba0d1b8ab0dec',
        'parent_verification_sha256': sha(parent_raw), 'reports': rows, 'sensitivity_checks': negative,
        'privacy_scope': 'Exact public fields, pure-projector equality, bounded value scan; no private member. Not a universal secret detector.',
        'evidence_scope': 'Tester-produced reports; writer inspected bytes on Linux. No fresh native execution or independent acceptance.',
        'host_independence': 'UNKNOWN_NOT_ATTESTED', 'intel_original_timeout_root_cause': 'UNKNOWN',
        'standalone_32bit_windows': 'UNTESTED_BY_THESE_REPORTS', 'native_x64_programs': 'UNTESTED_BY_THESE_REPORTS',
        'seven_target_release': 'OPEN'}
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(result['result'], len(rows), 'reports;', len(negative), 'expected negative rejections')


if __name__ == '__main__':
    main()
