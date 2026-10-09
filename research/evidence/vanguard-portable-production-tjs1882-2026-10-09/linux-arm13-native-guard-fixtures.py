"""Adverse qualification metadata must fail before any build or lock claim."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

root = Path(__file__).resolve().parents[3]
payload = root / 'build/tjs1882-3175-native-linux-arm-ci-payload13'
source = payload / 'vanguard/run-portable-linux-ci.py'
inputs = payload / 'ci/tjs1882/linux-arm-build-inputs.json'
digest = hashlib.sha256(inputs.read_bytes()).hexdigest()
spec = importlib.util.spec_from_file_location('arm_ci', source)
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)
original_read = Path.read_text
cases = []
with tempfile.TemporaryDirectory(prefix='linux-arm13-guards-', dir='/storage/data/meownero-tjs1882-3175') as tmp:
    for name in ('not-github', 'runner-x64', 'process-x64', 'wrong-glibc', 'wrong-distro',
                 'docker-x64', 'other-container', 'missing-cpu-crypto', 'low-memory', 'low-disk'):
        out = Path(tmp) / name
        calls = []

        def read(path, *args, **kwargs):
            if str(path) == '/etc/os-release':
                return 'ID=ubuntu\nVERSION_ID=' + ('24.04' if name == 'wrong-distro' else '22.04') + '\n'
            if str(path) == '/proc/cpuinfo':
                return 'Features : ' + ('fp asimd' if name == 'missing-cpu-crypto' else 'aes pmull sha1 sha2') + '\n'
            if str(path) == '/proc/meminfo':
                return 'MemAvailable: ' + ('1024' if name == 'low-memory' else str(8 * 1024**2)) + ' kB\n'
            return original_read(path, *args, **kwargs)

        def command(argv, **kwargs):
            calls.append(argv[:3])
            if argv == ['getconf', 'GNU_LIBC_VERSION']:
                return 'glibc ' + ('2.38' if name == 'wrong-glibc' else '2.35') + '\n'
            if argv[:2] == ['docker', 'info']:
                return 'linux ' + ('x86_64' if name == 'docker-x64' else 'aarch64') + '\n'
            if argv == ['docker', 'ps', '-q']:
                return 'UNRELATED_EXISTING_CONTAINER\n' if name == 'other-container' else ''
            raise AssertionError('unexpected command past qualification guard')

        env = {'GITHUB_ACTIONS': 'false' if name == 'not-github' else 'true',
               'RUNNER_OS': 'Linux', 'RUNNER_ARCH': 'X64' if name == 'runner-x64' else 'ARM64'}
        argv = ['ci', '--inputs', str(inputs), '--inputs-sha256', digest, '--out', str(out)]
        with patch.dict(os.environ, env), patch.object(sys, 'argv', argv), \
             patch.object(ci.platform, 'system', lambda: 'Linux'), \
             patch.object(ci.platform, 'machine', lambda: 'x86_64' if name == 'process-x64' else 'aarch64'), \
             patch.object(Path, 'read_text', read), patch.object(ci.subprocess, 'check_output', command), \
             patch.object(ci.shutil, 'disk_usage', lambda p: SimpleNamespace(free=(9 if name == 'low-disk' else 50) * 1024**3)):
            try:
                ci.main()
                raise AssertionError('adverse qualification accepted')
            except AssertionError:
                pass
        receipt = json.loads((out / 'public/ci-receipt.json').read_text())
        assert receipt['result'] == 'FAIL' and receipt['failure_type'] == 'AssertionError'
        assert not receipt['phases'] and 'native_runner' not in receipt
        assert 'owned_ephemeral_lock_removed' not in receipt
        cases.append({'case': name, 'result': 'REFUSED_BEFORE_BUILD_OR_LOCK',
                      'actual_runner_qualification': 'NOT_PROBED_METADATA_INJECTED',
                      'allowed_read_command_count': len(calls), 'build_or_remove_commands': 0})
result = {'schema': 'meownero-linux-arm13-native-guard-fixtures/1',
          'result': 'PASS_TEN_ADVERSE_NATIVE_ABI_CPU_CAPACITY_WORKLOAD_REFUSALS',
          'controller_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
          'inputs_sha256': digest, 'cases': cases, 'actual_ARM_runner_qualification': 'UNTESTED'}
Path(__file__).with_suffix('.json').write_text(json.dumps(result, indent=2) + '\n')
print(result['result'])
