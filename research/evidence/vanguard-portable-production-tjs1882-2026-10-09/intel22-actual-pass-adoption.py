"""Adopt exact retained Intel22 bytes without starting a native workload."""
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import tarfile
import zipfile

root = Path(__file__).resolve().parents[3]
evidence = Path(__file__).parent
parent = root / 'build/tjs1882-2493-parent-ci-run12'
payload = root / 'build/tjs1882-2493-native-ci-payload22'
archive = root / 'build/tjs1882-2493-validate22-only/meownero-vanguard-macos-x86_64.tar.gz'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
expected = {'INTEL22-ACTUAL-ARTIFACT.zip': (3658, 'dbdcc08e3c896bb57d3299a93c542ffa4e4c2d480ea3c800051421c7a098b54a'),
    'INTEL22-PARENT-CI-READBACK.json': (44361, 'cba48d9185da606fba359477b8966359995b142bbbf06edcf9049b5d205fdb88'),
    'INTEL22-ACTUAL-PASS-EVIDENCE-AUDIT.json': (51175, 'dd51ff423a7076de14b09e9c9ceba58641186603f9875ba0036f2a43b4e60f9e')}
for name, (size, digest) in expected.items():
    assert (parent / name).stat().st_size == size and sha(parent / name) == digest
public = {}
with zipfile.ZipFile(parent / 'INTEL22-ACTUAL-ARTIFACT.zip') as stream:
    assert sorted(stream.namelist()) == ['check.json', 'ci-receipt.json', 'controls.json', 'journey.json', 'supervision.json']
    for name in stream.namelist():
        data = stream.read(name)
        assert data == (parent / ('INTEL22-' + name)).read_bytes()
        public[name] = json.loads(data)
inputs = json.loads((payload / 'vanguard/ci-inputs.json').read_text())
row = inputs['targets']['macos-x86_64']
pub = json.loads((payload / 'PUBLICATION.json').read_text())
for name, meta in pub['files'].items():
    assert (payload / name).stat().st_size == meta['bytes'] and sha(payload / name) == meta['sha256']
for name, digest in inputs['source_files'].items():
    assert sha(payload / name) == digest
assert sha(archive) == row['archive_sha256'] and archive.stat().st_size == row['archive_bytes']
with tarfile.open(archive) as stream:
    members = stream.getmembers()
    assert all(m.isfile() and not PurePosixPath(m.name).is_absolute() and '..' not in PurePosixPath(m.name).parts for m in members)
    assert len({m.name for m in members}) == len(members)
    prefix = row['package_name'] + '/'
    assert all(m.name.startswith(prefix) for m in members)
    manifest_bytes = stream.extractfile(prefix + 'release.json').read()
    assert hashlib.sha256(manifest_bytes).hexdigest() == row['release_manifest_sha256']
    release = json.loads(manifest_bytes)
    assert {m.name for m in members} == {prefix + name for name in release['files']} | {prefix + 'release.json'}
    for name, digest in release['files'].items():
        assert hashlib.sha256(stream.extractfile(prefix + name).read()).hexdigest() == digest
    for name, digest in row['package_helpers'].items():
        assert release['files'][name] == digest
    for name, digest in row['program_sha256'].items():
        assert release['files']['bin/' + name] == digest
ci, journey, check, controls, supervisor = (public[n] for n in ['ci-receipt.json', 'journey.json', 'check.json', 'controls.json', 'supervision.json'])
assert ci['github_run_id'] == '38014113675' and ci['github_sha'] == 'cc5fd6248287d5fec0ffe2d4bb728102c28b783c'
assert ci['inputs_sha256'] == sha(payload / 'vanguard/ci-inputs.json')
assert ci['archive_sha256'] == check['archive_sha256'] == row['archive_sha256']
assert ci['result'] == 'PASS_NATIVE_ARCHIVE_JOURNEY_AND_TEN_CONTROLS'
assert ci['process_architecture'] == 'x86_64' and ci['owned_lock_removed']
assert check['execution_substrate'] == journey['execution_substrate'] == 'NATIVE'
assert journey['upstream_commit'] == inputs['upstream_commit'] and journey['architecture'] == 'x86_64'
assert journey['release_manifest_sha256'] == controls['release_manifest_sha256'] == row['release_manifest_sha256']
assert journey['program_sha256'] == row['program_sha256']
assert journey['result'] == 'PASS_NATIVE_JOURNEY' and journey['receive_atomic'] == 5 * 10**12
assert journey['subsequent_spend_atomic'] == 2 * 10**12 and journey['restore_matches'] and journey['cli_open_restored_wallet']
assert len(journey['payments']) == 2 and all(p['rct_type'] == 7 and p['carrot_outputs'] for p in journey['payments'])
assert len(journey['cleanup']) == 5 and all(p['exit'] == 0 and p['removed'] for p in journey['cleanup'])
assert controls['result'] == 'PASS_REFUSALS' and len(controls['cases']) == 10
assert all(p.get('refused') or p.get('removed') for p in controls['cases'])
assert check['result'] == 'PASS_NATIVE_ARCHIVE_JOURNEY' and check['peak_resident_bytes'] < check['resident_limit_bytes'] == 4 * 1024**3
assert [p['name'] for p in check['phases']] == ['preflight', 'journey', 'controls']
assert all(p['exit'] == 0 and p['reaped'] for p in check['phases'])
assert supervisor['result'] == 'PASS_WRAPPER_AND_OWNED_CLEANUP' and supervisor['wrapper_reaped']
assert all(p['removed'] for p in supervisor['cleanup']) and not supervisor['signals']
spec = importlib.util.spec_from_file_location('exact_intel22', payload / 'vanguard/run-portable-ci.py')
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
assert helper.public_check(check) == check
for value in public.values():
    def safe_keys(value):
        if isinstance(value, dict):
            assert not set(value) & {'argv', 'stdout', 'stderr', 'message', 'traceback', 'seed', 'wallet_path'}
            for item in value.values():
                safe_keys(item)
        elif isinstance(value, list):
            for item in value:
                safe_keys(item)
    safe_keys(value)
result = {'schema': 'meownero-writer-intel22-actual-pass-adoption/1', 'result': 'PASS_EXACT_RECORDED_NATIVE_EVIDENCE_ADOPTED',
    'native_acceptance_by_original_reviewer': 'PENDING', 'full_seven_target_release': 'OPEN',
    'actual_run': '38014113675', 'job': '114100503403', 'github_sha': ci['github_sha'],
    'native_host': {'os': ci['os'], 'python': ci['python'], 'architecture': ci['process_architecture']},
    'archive': {'path': str(archive.relative_to(root)), 'bytes': archive.stat().st_size, 'sha256': sha(archive),
        'release_manifest_sha256': row['release_manifest_sha256'], 'safe_members': len(members), 'internal_hashes_verified': len(release['files'])},
    'inputs_sha256': ci['inputs_sha256'], 'source_evidence_commit': pub['source_evidence_commit'],
    'program_sha256': row['program_sha256'], 'public_members': {n: {'bytes': (parent / ('INTEL22-' + n)).stat().st_size,
        'sha256': sha(parent / ('INTEL22-' + n))} for n in public},
    'parent_audit_sha256': expected['INTEL22-ACTUAL-PASS-EVIDENCE-AUDIT.json'][1],
    'journey': 'PASS_5_RECEIVE_2_LATER_SPEND_FCMP7_CARROT_RESTORE_NATIVE_CLI', 'ten_controls': 'PASS',
    'cleanup_qualification': 'KNOWN_PIDS_ABSENT_BY_COMPLETE_PS_OMISSION_REJECTED_OBSERVATIONS_NUMERIC_ABSENT_NO_GLOBAL_KERNEL_ABSENCE_CLAIM',
    'latency_cause_of_historical20': 'UNKNOWN_SUCCESS22_DOES_NOT_EXPLAIN_IT',
    'owned_native_work_started': False, 'other_OS_minimum_signing_notarization_download_rebuild_delivery': 'UNCONFIRMED'}
Path(__file__).with_suffix('.json').write_text(json.dumps(result, indent=2) + '\n')
print(result['result'], len(members), 'archive members and five public receipts')
