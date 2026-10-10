"""Wrong caps must fail in each exact frozen controller.main before any output."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import traceback
from unittest import mock

root = Path(__file__).resolve().parents[3]
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
cases = []
for kind, number, previous, inputname in [('native-linux-ci', '25', '23', 'linux-build-inputs.json'), ('native-linux-arm-ci', '26', '24', 'linux-arm-build-inputs.json')]:
    payload = root / ('build/tjs1882-2493-' + kind + '-payload' + number)
    old = root / ('build/tjs1882-2493-' + kind + '-payload' + previous)
    helper = payload / 'vanguard/run-portable-linux-ci.py'
    controller_sha = sha(helper)
    assert controller_sha == sha(old / 'vanguard/run-portable-linux-ci.py')
    original = json.loads((payload / ('ci/tjs1882/' + inputname)).read_text())
    for name, digest in original['source_files'].items():
        assert sha(payload / name) == digest
    assert original['source_files']['vanguard/run-portable-linux-ci.py'] == controller_sha
    for field in ['container_memory_bytes', 'container_memory_swap_bytes']:
        spec = importlib.util.spec_from_file_location('exact_ci' + number, helper)
        ci = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ci)
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            inputs = json.loads(json.dumps(original))
            inputs['compile_resource_policy'][field] = 3 * 1024**3
            source = base / 'wrong-policy.json'
            source.write_text(json.dumps(inputs, indent=2) + '\n')
            digest = sha(source)
            out = base / 'output'
            lock_calls, process_calls = [], []
            path_open = Path.open
            def open_path(path, *args, **kwargs):
                if str(path) == '/tmp/meownero-swarm-20260912-heavy.lock':
                    lock_calls.append(True)
                    raise AssertionError('fixture forbids owned lock acquisition')
                return path_open(path, *args, **kwargs)
            def process(*args, **kwargs):
                process_calls.append(True)
                raise AssertionError('fixture forbids Docker or workload launch')
            before = os.umask(0o077)
            try:
                with mock.patch.object(sys, 'argv', [str(helper), '--inputs', str(source), '--inputs-sha256', digest, '--out', str(out)]), mock.patch.object(Path, 'open', open_path), mock.patch.object(ci.subprocess, 'Popen', process), mock.patch.object(ci.subprocess, 'run', process), mock.patch.object(ci.subprocess, 'check_output', process):
                    try:
                        ci.main()
                    except AssertionError as error:
                        assert str(error) == 'architecture-bound compile resource policy mismatch'
                        frames = traceback.extract_tb(error.__traceback__)
                        assert Path(frames[-1].filename).resolve() == helper.resolve()
                        failed_line = frames[-1].lineno
                    else:
                        raise AssertionError('wrong cap accepted')
            finally:
                os.umask(before)
            assert not out.exists() and not (out / 'public').exists()
            assert not lock_calls and not process_calls
            cases.append({'target': original['target'], 'field': field, 'controller_sha256': controller_sha, 'preserved_controller_sha256': sha(old / 'vanguard/run-portable-linux-ci.py'), 'fixture_inputs_sha256': digest, 'fixture_source_pins_verified': len(original['source_files']), 'specific_policy_assertion_line': failed_line, 'output_absent': True, 'public_absent': True, 'lock_open_calls': 0, 'docker_or_workload_calls': 0, 'result': 'REFUSED_AT_POLICY_BEFORE_OUTPUT'})
result = {'schema': 'meownero-linux25-arm26-exact-controller-refusals/1', 'result': 'PASS_FOUR_EXACT_MAIN_CAP_REFUSALS_BEFORE_OUTPUT_LOCK_WORKLOAD', 'cases': cases, 'native_build': 'NOT_STARTED'}
Path(__file__).with_suffix('.json').write_text(json.dumps(result, indent=2) + '\n')
print(result['result'])
