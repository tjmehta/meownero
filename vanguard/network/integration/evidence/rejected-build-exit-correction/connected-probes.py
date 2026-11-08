"""Writer rerun of Platform F1 connected probes; Docker/native effects substituted."""
import base64
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

RUN = Path(__file__).parent
ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / 'vanguard/network'))
import test_direct_profile as fixture

r = fixture.r
raw = b'{"three_production_binaries":{"status":"PASS","binaries":{}}}'
results = []
controller_output = io.StringIO()


def scenario(name, **options):
    case = fixture.Direct('test_entry_has_no_retired_facility_imports')
    case.setUp()
    acquire = r.acquire_lock

    def isolated_lock():
        assert r.g.LOCK == case.lock, 'refuse any original heavy-lock access'
        info = case.lock.stat()
        assert r.g.LOCK_ID == (info.st_dev, info.st_ino)
        return acquire()

    try:
        with patch.object(r, 'acquire_lock', isolated_lock), contextlib.redirect_stdout(controller_output):
            code, receipt, events = case.exercise(
                mutate_build=lambda path: path.write_bytes(raw), **options)
        diagnostics = json.loads((case.output / 'evidence/build-diagnostics.json').read_text())
        retained = diagnostics.get('rejected_build', {})
        observation = dict(
            name=name, controller_exit=code, result=receipt['result'],
            started_phases=events.count('start'),
            failure_phase=receipt.get('failure_phase'),
            phase_diagnostics=receipt['phase_diagnostics'],
            build_rejection_key_path=receipt.get('build_rejection_key_path'),
            rejected_key_paths=receipt.get('rejected_key_paths'),
            retained_payload=retained.get('payload'),
            retained_key_path=retained.get('key_path'),
            retained_sha256=retained.get('sha256'),
            retained_size_bytes=retained.get('size_bytes'),
            retained_exact_bytes=(retained.get('payload') == 'RETAINED' and
                                  base64.b64decode(retained['bytes_base64']) == raw),
            staging_removed=not (case.output / 'staging').exists(),
            cleanup={key: value['status'] for key, value in receipt['rows']['cleanup.json'].items()},
            expected='Rejected build bytes and trusted path retained on failed pre-runtime build')
        assert code == 1 and events.count('start') == 1
        assert observation['staging_removed']
        assert receipt['rejected_key_paths']['build.json'] == 'build.json.three_production_binaries.binaries.monerod'
        assert retained.get('key_path') == receipt['rejected_key_paths']['build.json']
        assert receipt['build_rejection_key_path'] == retained['key_path']
        assert retained['sha256'] == fixture.c.digest(raw) and retained['size_bytes'] == len(raw)
        assert all(row['status'] == 'PASS' for row in receipt['rows']['cleanup.json'].values())
        assert 'runtime' not in receipt['phase_diagnostics']
        assert not (case.output/'public/build.json').exists()
        results.append(observation)
    finally:
        case.doCleanups()


scenario('successful_container_rejected_by_build_gate')
scenario('nonzero_build_cli_and_container', failed_phase='build')
scenario('nonzero_container_with_zero_build_cli', failed_phase='build', container_exit_only=True)
scenario('raised_build_command', raised_phase='build')

# Compare the unchanged producer bytes through baseline and candidate readers.
# Never call baseline main or acquire a host lock.
baseline_source = subprocess.check_output([
    'git', 'show', 'bf6acfba8cf0d649ec5c29480387bdd5327f8837:vanguard/network/run-profile.py'])
with tempfile.TemporaryDirectory(prefix='TJS-2504-platform-reader-') as tmp:
    directory = Path(tmp)
    source = directory / 'baseline.py'
    source.write_bytes(baseline_source)
    spec = importlib.util.spec_from_file_location('platform_baseline_reader', source)
    old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)
    path = directory / 'build.json'
    path.write_bytes((ROOT / 'vanguard/network/integration/evidence/elf-witness-correction/historical-emitted-build.json').read_bytes())
    try:
        old.read_public_rows(path, old.public_shapes())
        baseline_refused = False
    except ValueError:
        baseline_refused = True
    candidate = r.read_public_rows(path, r.public_shapes())
    assert baseline_refused
    assert len(candidate['three_production_binaries']['binaries']) == 3
    results.append(dict(name='same_historical_ELF_payload_reader_differential',
                        baseline_refused=baseline_refused, candidate_accepted=True,
                        baseline_main_or_lock_invoked=False))

failed = [value['name'] for value in results if 'retained_exact_bytes' in value and
          not value['retained_exact_bytes']]
packet = dict(base_commit='00261c88c441cb471c3eda3480ec6488a723fdec',
              candidate_runner_sha256=fixture.c.digest((fixture.c.HERE/'run-profile.py').read_bytes()),
              native_execution='NOT_RUN', docker='SUBSTITUTED',
              host_locks='DISPOSABLE_ONLY; every acquisition checked',
              scenarios=results, unmet_retention_scenarios=failed,
              verdict='FAIL_WRITER_CONNECTED_PROBES' if failed else 'PASS_WRITER_CONNECTED_PROBES')
(RUN / 'connected-probe-results.json').write_text(json.dumps(packet, indent=2) + '\n')
(RUN / 'connected-probe-controller.log').write_text(controller_output.getvalue())
print(json.dumps(packet, indent=2))
raise SystemExit(1 if failed else 0)
